import logging

from django.utils import timezone

from core.broker import broker
from core.mailer import send_mail
from core.user_agent import describe_user_agent
from form import models, models_async

logger = logging.getLogger(__name__)

EmailStatus = models.FormRequest.EmailStatus


def format_value(value) -> str:
    """Значение дополнительного поля — для письма: список через запятую, да/нет словами."""
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, list):
        return ", ".join(format_value(item) for item in value)
    return "—" if value is None else str(value)


def tech_info_list(form_request) -> list[tuple[str, str]]:
    """Техническая информация для письма — у форм с галочкой «Техническая информация в письме».
    Время — до секунды, по Москве: так заявку легко сверить с Метрикой и журналом звонков."""
    row_list = [
        ("Время заявки", timezone.localtime(form_request.date_add).strftime("%d.%m.%Y %H:%M:%S")),
        ("Страница входа", form_request.landing_page),
        ("Пришёл с", form_request.referrer),
        ("Метки", ", ".join(f"{key}={value}" for key, value in form_request.utm.items())),
        ("ID в Яндекс Метрике", form_request.ym_client_id),
        ("IP", form_request.ip),
        ("Браузер", describe_user_agent(form_request.user_agent)),
    ]
    return [(label, value) for label, value in row_list if value]


def recipient_list(form_type) -> list[str]:
    """Кому отправлять письма о заявках формы. Пусто — заявки только в админке."""
    return [email.strip() for email in form_type.email_to.split(",") if email.strip()]


async def _set_email_status(form_request: models_async.FormRequest, status: str, error: str = "") -> None:
    form_request.email_status = status
    form_request.email_error = error
    form_request.date_email_sent = timezone.now() if status == EmailStatus.SENT else None
    await form_request.save(update_fields=["email_status", "email_error", "date_email_sent"])


@broker.task
async def send_request_email(form_request_id: int) -> None:
    """Письмо о новой заявке. Задача может выполниться повторно: уже отправленное не шлём.

    Письмо некритичное: заявка сохранена в любом случае, сбой почты виден в админке
    по статусу письма и в журнале.
    """
    form_request = await models_async.FormRequest.get_or_none(id=form_request_id).select_related("form_type")
    if form_request is None or form_request.email_status != EmailStatus.WAIT:
        return

    form_type = form_request.form_type
    to_list = recipient_list(form_type)
    if not to_list:
        await _set_email_status(form_request, EmailStatus.NONE)
        return

    file_list = await models_async.FormFile.filter(form_request_id=form_request.id)
    try:
        await send_mail(to_list, f"{form_type.email_subject or form_type.name} — заявка №{form_request.id}", "form_request", {
            "form_request": form_request,
            "form_type": form_type,
            "data_list": [(key, format_value(value)) for key, value in form_request.data.items()],
            "channel": models.FormRequest.Channel(form_request.channel).label if form_request.channel else "",
            "file_list": file_list,
            "tech_info_list": tech_info_list(form_request) if form_type.is_email_tech_info else [],
        })
    except Exception as exc:
        logger.warning(f"Письмо по заявке №{form_request.id} не отправлено", exc_info=True)
        await _set_email_status(form_request, EmailStatus.ERROR, str(exc)[:4000])
        return
    await _set_email_status(form_request, EmailStatus.SENT)
