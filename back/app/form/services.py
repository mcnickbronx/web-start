"""Логика модуля «Заявки».

Путь заявки: сайт берёт описание формы с токеном → загружает файлы по этому токену →
отправляет заявку с тем же токеном. Токен подписан ключом проекта: в нём код формы,
время выдачи и хеш ответа на капчу. Он одноразовый — заявку с ним примут один раз.

Бот получает тот же ответ, что и человек, но его заявка сохраняется со статусом «спам»,
и письмо по ней не уходит. Бот не узнаёт, что его поймали, а ложное срабатывание видно
в админке.
"""
import logging
import uuid
from datetime import timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from fastapi import HTTPException
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from core import upload
from core.bridge import with_sync
from core.errors import field_error
from form import captcha, conf, models, models_async
from form.schemas import FormRequestIn
from form.tasks import recipient_list, send_request_email
from form.visit import detect_channel, parse_utm
from user import models_async as user_models_async

logger = logging.getLogger(__name__)

TOKEN_SALT = "form.token"
Status, EmailStatus = models.FormRequest.Status, models.FormRequest.EmailStatus


# --- Токен формы -------------------------------------------------------------------------

def issue_token(form_type: models_async.FormType) -> dict:
    """Токен для открытой формы и вопрос капчи, если он нужен."""
    token_id = str(uuid.uuid4())
    payload = {"id": token_id, "code": form_type.code, "time": int(timezone.now().timestamp())}
    question = None
    if form_type.is_captcha and conf.CAPTCHA_PROVIDER == "numeric":
        question, payload["answer"] = captcha.create_question(token_id)
    return {"token": signing.dumps(payload, salt=TOKEN_SALT), "captcha_question": question}


def read_token(token: str) -> dict:
    try:
        return signing.loads(token, salt=TOKEN_SALT, max_age=conf.TOKEN_LIFETIME)
    except signing.SignatureExpired as exc:
        raise HTTPException(406, "Форма устарела, обновите страницу") from exc
    except signing.BadSignature as exc:
        raise HTTPException(406, "Форма повреждена, обновите страницу") from exc


async def _form_by_token(payload: dict) -> models_async.FormType:
    form_type = await models_async.FormType.get_or_none(code=payload["code"], is_active=True)
    if form_type is None:
        raise HTTPException(406, "Форма больше не принимает заявки")
    return form_type


# --- Описание формы ------------------------------------------------------------------------

async def get_form_detail(code: str) -> dict:
    """Всё, что нужно сайту, чтобы нарисовать форму: капча, файлы, токен. Нет формы — 404."""
    form_type = await models_async.FormType.get(code=code, is_active=True)
    return {
        "code": form_type.code,
        "name": form_type.name,
        "is_contact_required": form_type.is_contact_required,
        "required_field_list": required_field_list(form_type),
        "is_captcha": form_type.is_captcha,
        "captcha_provider": conf.CAPTCHA_PROVIDER if form_type.is_captcha else None,
        "captcha_client_key": conf.SMARTCAPTCHA_CLIENT_KEY if form_type.is_captcha and conf.CAPTCHA_PROVIDER == "yandex" else None,
        "is_file": form_type.is_file,
        "file_count_max": form_type.file_count_max if form_type.is_file else 0,
        "file_extension_list": conf.FILE_EXTENSION_LIST if form_type.is_file else [],
        "file_size_max_mb": conf.FILE_SIZE_MAX_MB,
        "fill_seconds_min": conf.FILL_SECONDS_MIN if form_type.is_trap else 0,
        **issue_token(form_type),
    }


# --- Файлы ----------------------------------------------------------------------------------

async def upload_file(token: str, file_name: str, content: bytes) -> models_async.FormFile:
    """Файл к будущей заявке. Привязывается к ней при отправке, до этого — ничей."""
    payload = read_token(token)
    form_type = await _form_by_token(payload)
    if not form_type.is_file:
        raise HTTPException(406, "К этой форме нельзя прикладывать файлы")

    extension = upload.check_upload(file_name, content, conf.FILE_EXTENSION_LIST, conf.FILE_SIZE_MAX_MB)
    if await models_async.FormFile.filter(token_id=payload["id"]).count() >= form_type.file_count_max:
        raise HTTPException(406, f"Можно приложить не больше {form_type.file_count_max} файлов")
    name = await upload.save_upload(models.form_file_storage(), extension, content)
    return await models_async.FormFile.create(token_id=payload["id"], file=name, original_name=file_name[:255], size=len(content))


async def download_file(user: user_models_async.CustomUser, file_id: uuid.UUID):
    """Файл заявки — только её автору: заявку отправили вошедшим. Чужой, ещё не приложенный и несуществующий
    файл — одинаковый 404: по ответу не узнать, что файл есть."""
    form_file = await models_async.FormFile.get(id=file_id, form_request__user_id=user.id)
    return await upload.file_response(models.form_file_storage(), form_file.file, form_file.original_name)


async def _check_file_list(form_type: models_async.FormType, token_id: str, file_id_list: list[uuid.UUID]) -> list[uuid.UUID]:
    """Файлы загружены с этой же формой и ещё ни к чему не приложены."""
    file_id_list = list(set(file_id_list))
    if not file_id_list:
        return []
    if not form_type.is_file:
        raise HTTPException(406, "К этой форме нельзя прикладывать файлы")
    found = await models_async.FormFile.filter(id__in=file_id_list, token_id=token_id, form_request_id__isnull=True).count()
    if found != len(file_id_list):
        raise HTTPException(406, "Файл не найден — загрузите его заново")
    return file_id_list


# --- Заявка ----------------------------------------------------------------------------------

def _is_trapped(trap_value: str | None, issued_at: int) -> bool:
    """Скрытое поле заполнено или форму отправили быстрее, чем её можно заполнить."""
    return bool(trap_value) or timezone.now().timestamp() - issued_at < conf.FILL_SECONDS_MIN


async def _is_captcha_valid(form_type: models_async.FormType, payload: dict, answer: str | None, ip: str) -> bool:
    if not form_type.is_captcha:
        return True
    if conf.CAPTCHA_PROVIDER == "yandex":
        return await captcha.check_yandex(answer or "", ip)
    # Капчу включили, пока форма была открыта, — в токене нет ответа
    return "answer" in payload and captcha.check_numeric(payload["id"], payload["answer"], answer or "")


#: Общие поля заявки: какие из них обязательны, задаётся у формы в админке
FIELD_LABEL_MAP = {"name": "имя", "phone": "телефон", "email": "email", "message": "сообщение"}


def required_field_list(form_type) -> list[str]:
    """Общие поля, отмеченные у формы обязательными: is_name_required, is_phone_required и т. д."""
    return [field for field in FIELD_LABEL_MAP if getattr(form_type, f"is_{field}_required")]


def request_error_map(form_type, value_map: dict) -> dict[str, str]:
    """Что не так с полями заявки по настройкам формы: {поле: текст}, пусто — всё верно.
    Общее для сайта и админки: у обоих ошибка встаёт под своим полем.

    value_map — общие поля: name, phone, email, message.
    """
    error_map = {field: f"Укажите {FIELD_LABEL_MAP[field]}" for field in required_field_list(form_type) if not value_map.get(field)}
    # «Телефон или email» — только если ни одно из них не обязательно само: иначе подсветили бы
    # и email, хотя заполнить нужно именно телефон
    is_contact_missing = not (value_map.get("phone") or value_map.get("email"))
    if form_type.is_contact_required and is_contact_missing and not {"phone", "email"} & error_map.keys():
        error_map["phone"] = error_map["email"] = "Укажите телефон или email"
    if value_map.get("email"):
        try:
            validate_email(value_map["email"])
        except ValidationError:
            error_map["email"] = "Некорректный email"
    return error_map


async def create_request(data: FormRequestIn, user: user_models_async.CustomUser | None, ip: str, user_agent: str = "") -> None:
    """Заявка с сайта. Бот — сохраняется как спам без письма, отвечаем ему как человеку."""
    payload = read_token(data.token)
    form_type = await _form_by_token(payload)
    already_sent = HTTPException(406, "Заявка уже отправлена. Чтобы отправить ещё одну, обновите страницу")
    if await models_async.FormRequest.filter(token_id=payload["id"]).exists():
        raise already_sent

    is_spam = form_type.is_trap and _is_trapped(data.leave_empty, payload["time"])
    file_id_list = []
    if not is_spam:
        # Ошибки полей — 422 по полям, сайт подсветит их. Капча — после полей: токен SmartCaptcha
        # одноразовый, и заявка с пустыми полями не должна его тратить
        error_map = request_error_map(form_type, data.model_dump(include=set(FIELD_LABEL_MAP)))
        if not error_map and not await _is_captcha_valid(form_type, payload, data.captcha, ip):
            # Ошибка в поле captcha — сайт запросит форму заново: новый вопрос, новый токен виджета
            error_map["captcha"] = "Капча не пройдена, попробуйте ещё раз"
        if error_map:
            raise field_error(error_map)
        file_id_list = await _check_file_list(form_type, payload["id"], data.file_id_list)

    utm = parse_utm(data.visit.landing_page)
    try:
        async with in_transaction():
            form_request = await models_async.FormRequest.create(
                form_type=form_type, user=user, name=data.name, phone=data.phone, email=data.email,
                message=data.message, data=data.data, source=data.source, ip=ip, token_id=payload["id"],
                user_agent=user_agent[:500], **data.visit.model_dump(), utm=utm,
                channel=detect_channel(utm, data.visit.referrer).value,
                status=(Status.SPAM if is_spam else Status.NEW).value,
                email_status=(EmailStatus.NONE if is_spam else EmailStatus.WAIT).value,
            )
            if file_id_list:
                await models_async.FormFile.filter(id__in=file_id_list).update(form_request_id=form_request.id)
    except IntegrityError as exc:
        # Две отправки с одним токеном одновременно: проверку выше прошли обе, база пустит одну
        raise already_sent from exc

    if is_spam:
        logger.info(f"Заявка №{form_request.id} ({form_type.code}) похожа на бота — сохранена как спам")
        return
    logger.info(f"Заявка №{form_request.id} ({form_type.code}) с сайта")
    # Письмо некритично: заявка уже сохранена, посетитель получает обычный ответ
    await _queue_email(form_request.id)


async def _queue_email(form_request_id: int) -> bool:
    """Письмо о заявке — в очередь. Очередь недоступна — статус письма «Ошибка» с причиной,
    предупреждение в журнале и False."""
    try:
        await send_request_email.kiq(form_request_id)
    except Exception as exc:
        logger.warning(f"Заявка №{form_request_id}: письмо не поставлено в очередь", exc_info=True)
        await models_async.FormRequest.filter(id=form_request_id).update(
            email_status=EmailStatus.ERROR.value, email_error=f"Не удалось поставить письмо в очередь: {exc}"[:4000],
        )
        return False
    return True


@with_sync
async def resend_request_email(form_request_id: int) -> None:
    """Письмо о заявке ещё раз — из админки: не дошло, потерялось или заявку вернули из спама.
    Если прежнее письмо ещё стоит в очереди, оно может прийти дважды."""
    form_request = await models_async.FormRequest.get(id=form_request_id).select_related("form_type")
    if form_request.status == Status.SPAM:
        raise HTTPException(406, "Заявка в спаме: сначала смените статус")
    if not recipient_list(form_request.form_type):
        raise HTTPException(406, f"У формы «{form_request.form_type.name}» не указано, кому отправлять")
    await models_async.FormRequest.filter(id=form_request_id).update(
        email_status=EmailStatus.WAIT.value, email_error="", date_email_sent=None,
    )
    if not await _queue_email(form_request_id):
        raise HTTPException(406, "Очередь писем недоступна, причина — в заявке")


# --- Уборка (админка и команды) ---------------------------------------------------------------

#: Файлы с диска при удалении заявок в админке: Django удаляет записи, а файлы оставляет
delete_files = upload.delete_files


def clear_orphan_files(hours: int = conf.FILE_ORPHAN_HOURS) -> int:
    """Файлы, которые загрузили, но так и не приложили к заявке. Возвращает число удалённых."""
    return upload.clear_orphans(models.FormFile.objects.filter(form_request__isnull=True, date_add__lt=timezone.now() - timedelta(hours=hours)))
