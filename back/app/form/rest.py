from uuid import UUID

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from starlette.datastructures import UploadFile as StarletteUploadFile

from core import upload
from core.schemas import MessageOut
from form import conf, services
from form.schemas import FormDetailOut, FormFileOut, FormRequestIn
from user.auth import CurrentUser, OptionalUser


class UploadFileRoute(APIRoute):
    """Сохраняет прежние ошибки пустого имени, которое FastAPI теперь считает отсутствующим файлом."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                data = await request.form()
                file = data.get("file")
                if not isinstance(file, StarletteUploadFile) or file.filename != "" or file.size != 0:
                    raise
                errors = error.errors()
                remaining = [item for item in errors if not (
                    item["type"] == "missing" and item["loc"] == ("body", "file")
                )]
                if len(remaining) == len(errors):
                    raise
                if remaining:
                    raise RequestValidationError(remaining, body=error.body) from None
                # FastAPI 0.150+ считает этот файл отсутствующим. Прежний API проверяет
                # токен и разрешение формы, затем отказывает пустому имени/файлу с 406.
                await services.upload_file(data["token"], "", b"")
                raise

        return handle


router = APIRouter()
upload_router = APIRouter(route_class=UploadFileRoute)

BUSINESS = {406: {"model": MessageOut, "description": "Сообщение пользователю"}}


@router.get("/detail/{code}", response_model=FormDetailOut, summary="Описание формы и токен",
            responses={404: {"model": MessageOut, "description": "Нет такой формы или она выключена"}},
            description="Без авторизации. Запрашивается при открытии формы на сайте: что показывать "
                        "(капча, файлы) и одноразовый токен. Токен нужен для загрузки файлов и отправки. "
                        "Новый токен — новый запрос, в том числе после отправки заявки.")
async def form_detail(code: str):
    return await services.get_form_detail(code)


@upload_router.post("/upload-file", response_model=FormFileOut, summary="Загрузить файл к заявке", responses=BUSINESS,
             description="Без авторизации, multipart: `token` из `/detail/{code}` и `file`. Возвращает `file_id` — "
                         "его передают в `file_id_list` при отправке. Файлы, так и не приложенные к заявке, "
                         "удаляет команда уборки. 406 — форма не принимает файлы, неверный формат, "
                         "размер или количество.")
async def upload_file(token: str = Form(..., description="Токен формы"), file: UploadFile = File(..., description="Файл")):
    content = await upload.read_upload(file, conf.FILE_SIZE_MAX_MB)
    form_file = await services.upload_file(token, file.filename or "", content)
    return {"file_id": form_file.id}


router.include_router(upload_router)


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


@router.get("/file/{file_id}", response_class=FileResponse, summary="Скачать свой файл заявки",
            responses={200: {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
                             "description": "Файл; имя — в Content-Disposition"},
                       401: {"model": MessageOut, "description": "Нет токена или он недействителен"},
                       404: {"model": MessageOut, "description": "Нет такого файла, он не ваш или ещё не приложен к заявке"}},
            description="Файл заявки — только её автору: тому, кто отправил заявку вошедшим. Чужой, ещё не приложенный "
                        "и несуществующий файл — одинаково 404, по ответу не узнать, есть ли такой файл. "
                        "Менеджеры скачивают файлы в админке, в заявке.")
async def download_file(file_id: UUID, user: CurrentUser):
    return await services.download_file(user, file_id)
