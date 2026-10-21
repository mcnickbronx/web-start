from fastapi import APIRouter, File, Form, Request, UploadFile

from core import upload
from core.schemas import MessageOut
from form import conf, services
from form.schemas import FormDetailOut, FormFileOut, FormRequestIn
from user.auth import OptionalUser

router = APIRouter()

BUSINESS = {406: {"model": MessageOut, "description": "Сообщение пользователю"}}


@router.get("/detail/{code}", response_model=FormDetailOut, summary="Описание формы и токен",
            responses={404: {"model": MessageOut, "description": "Нет такой формы или она выключена"}},
            description="Без авторизации. Запрашивается при открытии формы на сайте: что показывать "
                        "(капча, файлы) и одноразовый токен. Токен нужен для загрузки файлов и отправки. "
                        "Новый токен — новый запрос, в том числе после отправки заявки.")
async def form_detail(code: str):
    return await services.get_form_detail(code)


@router.post("/upload-file", response_model=FormFileOut, summary="Загрузить файл к заявке", responses=BUSINESS,
             description="Без авторизации, multipart: `token` из `/detail/{code}` и `file`. Возвращает `file_id` — "
                         "его передают в `file_id_list` при отправке. Файлы, так и не приложенные к заявке, "
                         "удаляет команда уборки. 406 — форма не принимает файлы, неверный формат, "
                         "размер или количество.")
async def upload_file(token: str = Form(..., description="Токен формы"), file: UploadFile = File(..., description="Файл")):
    content = await upload.read_upload(file, conf.FILE_SIZE_MAX_MB)
    form_file = await services.upload_file(token, file.filename or "", content)
    return {"file_id": form_file.id}


@router.post("/create", response_model=MessageOut, summary="Отправить заявку", responses=BUSINESS,
             description="Без авторизации; с токеном пользователя заявка привяжется к нему. Какие поля "
                         "обязательны — в `/detail/{code}`: `required_field_list` и `is_contact_required`. "
                         "Поле `leave_empty` на сайте скрыто и всегда пустое — это ловушка для ботов.\n\n"
                         "422 — ошибки полей в `full_error`, `loc` — имя поля: не заполнено обязательное "
                         "(`name`, `phone`, `email`, `message`), нет ни телефона, ни email (на обоих), "
                         "неверный email, не пройдена капча (`captcha`). 406 — токен устарел или уже "
                         "использован (заявка отправлена), форма выключена, файл не найден.\n\n"
                         "После 406 и после ошибки в поле `captcha` — запросить форму заново: по коду ответа, "
                         "а не по тексту, тексты могут меняться.")
async def create_request(data: FormRequestIn, request: Request, user: OptionalUser):
    ip = request.client.host if request.client else ""
    await services.create_request(data, user, ip, request.headers.get("user-agent", ""))
    return {"message": "Заявка отправлена"}
