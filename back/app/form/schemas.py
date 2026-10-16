from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

# Значение дополнительного поля: строка, число, да/нет, пусто или список — например, отмеченные галочки
DataItem = Annotated[str, StringConstraints(max_length=500)] | int | float
DataValue = Annotated[str, StringConstraints(max_length=2000)] | int | float | bool | None | Annotated[list[DataItem], Field(max_length=50)]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]


def clipped(length: int):
    """Строка, обрезанная до length. Для данных визита: из-за длинного адреса заявка не должна пропасть."""
    return Annotated[str, AfterValidator(lambda value: value.strip()[:length])]


class FormDetailOut(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "code": "callback", "name": "Заказать звонок", "is_contact_required": True,
        "required_field_list": ["name", "phone"], "is_captcha": True, "captcha_provider": "numeric",
        "captcha_question": "23 + 7", "captcha_client_key": None, "is_file": True, "file_count_max": 5,
        "file_extension_list": ["jpg", "pdf", "docx"], "file_size_max_mb": 10, "fill_seconds_min": 3,
        "token": "eyJpZCI6Ij...",
    }})

    code: str = Field(..., description="Код формы")
    name: str = Field(..., description="Название")
    is_contact_required: bool = Field(..., description="Нужен телефон или email — хотя бы одно из двух")
    required_field_list: list[Literal["name", "phone", "email", "message"]] = Field(..., description="Обязательные общие поля")
    is_captcha: bool = Field(..., description="Нужна капча")
    captcha_provider: Literal["numeric", "yandex"] | None = Field(None, description="numeric — показать captcha_question и поле ответа; yandex — виджет SmartCaptcha")
    captcha_question: str | None = Field(None, description="Пример для капчи numeric")
    captcha_client_key: str | None = Field(None, description="Ключ виджета для капчи yandex")
    is_file: bool = Field(..., description="Можно прикладывать файлы")
    file_count_max: int = Field(..., description="Сколько файлов можно приложить")
    file_extension_list: list[str] = Field(..., description="Допустимые расширения")
    file_size_max_mb: int = Field(..., description="Предел размера файла, МБ")
    fill_seconds_min: int = Field(..., description="Не отправлять раньше, чем через столько секунд после получения формы: "
                                                   "быстрее — ловушка для ботов, заявка уйдёт в спам. 0 — ловушка выключена")
    token: str = Field(..., description="Токен формы: для загрузки файлов и отправки. Одноразовый, живёт 2 часа")


class FormFileOut(BaseModel):
    file_id: UUID = Field(..., description="ID файла — в file_id_list при отправке заявки")


class VisitIn(BaseModel):
    """Откуда человек пришёл на сайт. Сайт запоминает это при первом заходе (например, в localStorage)
    и присылает с каждой заявкой. Все поля необязательные: чего нет — не передавать."""

    referrer: clipped(1000) = Field("", description="document.referrer при первом заходе, если это чужой сайт: поисковик, реклама, соцсеть")
    landing_page: clipped(1000) = Field("", description="Первая страница визита целиком, с параметрами: location.pathname + location.search. "
                                                         "UTM-метки и клики рекламы (yclid, gclid) бэкенд разберёт из неё сам")
    ym_client_id: clipped(50) = Field("", description="ClientID Яндекс Метрики: кука _ym_uid или ym(<счётчик>, 'getClientID')")


class FormRequestIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "token": "eyJpZCI6Ij...", "name": "Иван", "phone": "+79990000000", "email": "ivan@example.com",
        "message": "Перезвоните после обеда", "data": {"Удобное время": "после 14:00", "Услуги": ["медосмотр", "выезд"]},
        "source": "/kontakty", "file_id_list": [], "captcha": "30", "leave_empty": "",
        "visit": {"referrer": "https://yandex.ru/",
                  "landing_page": "/uslugi?utm_source=yandex&utm_medium=cpc&utm_campaign=medosmotr-moskva&yclid=123",
                  "ym_client_id": "1727000000123456789"},
    }})

    token: str = Field(..., max_length=1000, description="Токен из /detail/{code}")
    name: Text = Field("", max_length=200, description="Имя")
    phone: Text = Field("", max_length=40, description="Телефон")
    email: Text = Field("", max_length=254, description="Email")
    message: Text = Field("", max_length=5000, description="Сообщение")
    data: dict[str, DataValue] = Field(default_factory=dict, max_length=50, description="Дополнительные поля формы: подпись → значение (строка, число, да/нет, список)")
    source: Text = Field("", max_length=500, description="Адрес страницы, с которой отправлена заявка")
    visit: VisitIn = Field(default_factory=VisitIn, description="Откуда человек пришёл на сайт: сайт-источник, страница входа с метками, Метрика")
    file_id_list: list[UUID] = Field(default_factory=list, max_length=20, description="Файлы из /upload-file")
    captcha: str | None = Field(None, max_length=5000, description="Ответ на пример (numeric) или токен виджета (yandex)")
    leave_empty: str | None = Field(None, max_length=500, description="Ловушка для ботов: скрытое поле, всегда пустое")
