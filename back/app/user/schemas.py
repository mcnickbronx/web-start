from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Email целиком в нижнем регистре: User@Mail.ru и user@mail.ru — один аккаунт
Email = Annotated[str, AfterValidator(lambda value: value.strip().lower())]


def same_password_as(field: str):
    """Пароль «ещё раз»: совпадает с field. Ошибка — у этого поля, сайт покажет её под ним.
    Не прошло проверку само field — молчим: ошибка уже у него."""
    def check(value: str, info: ValidationInfo) -> str:
        if field in info.data and value != info.data[field]:
            raise ValueError("Пароли не совпадают")
        return value
    return Annotated[str, AfterValidator(check)]


class TokenPairIn(BaseModel):
    email: Email = Field(..., max_length=254, description="Email")
    password: str = Field(..., max_length=128, description="Пароль")

    model_config = ConfigDict(json_schema_extra={"example": {"email": "user@example.com", "password": "0Q9w8E7r"}})


class TokenOut(BaseModel):
    access: str = Field(..., description="Access-токен (1 день) — в заголовок Authorization: Bearer. "
                                         "Refresh (30 дней) бэкенд кладёт в куку httpOnly, для /refresh")


class UserMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID")
    email: str = Field(..., description="Email")
    first_name: str = Field(..., description="Имя")
    last_name: str = Field(..., description="Фамилия")
    is_staff: bool = Field(..., description="Доступ в админку")
    is_superuser: bool = Field(..., description="Суперпользователь")
    last_login: datetime | None = Field(None, description="Последний вход")
    date_joined: datetime = Field(..., description="Дата регистрации")


class UserUpdateIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"first_name": "Иван", "last_name": "Иванов"}},
    )

    first_name: str = Field(None, max_length=150, description="Имя")
    last_name: str = Field(None, max_length=150, description="Фамилия")


class RegisterIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "email": "user@example.com", "password": "0987Asdf", "password_confirm": "0987Asdf",
        "first_name": "Иван", "last_name": "Иванов",
    }})

    email: Email = Field(..., max_length=254, description="Email")
    password: str = Field(..., min_length=8, max_length=128, description="Пароль")
    password_confirm: same_password_as("password") = Field(..., max_length=128, description="Пароль ещё раз")
    first_name: str = Field("", max_length=150, description="Имя")
    last_name: str = Field("", max_length=150, description="Фамилия")


class EmailIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "user@example.com"}})

    email: Email = Field(..., max_length=254, description="Email")


class CodeIn(EmailIn):
    model_config = ConfigDict(json_schema_extra={"example": {"email": "user@example.com", "code": "123456"}})

    # [0-9], а не \d: \d пропускает цифры других алфавитов («１２３»), а сравнение кода на них падает
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^[0-9]+$", description="Код из письма — шесть цифр")


class PasswordResetConfirmIn(CodeIn):
    model_config = ConfigDict(json_schema_extra={"example": {
        "email": "user@example.com", "code": "123456",
        "password_new": "NewPass456", "password_new_confirm": "NewPass456",
    }})

    password_new: str = Field(..., min_length=8, max_length=128, description="Новый пароль")
    password_new_confirm: same_password_as("password_new") = Field(..., max_length=128, description="Новый пароль ещё раз")


class PasswordChangeIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "password_current": "0987Asdf", "password_new": "NewPass456", "password_new_confirm": "NewPass456",
    }})

    password_current: str = Field(..., max_length=128, description="Текущий пароль")
    password_new: str = Field(..., min_length=8, max_length=128, description="Новый пароль")
    password_new_confirm: same_password_as("password_new") = Field(..., max_length=128, description="Новый пароль ещё раз")

    @field_validator("password_new")
    @classmethod
    def differs_from_current(cls, value: str, info: ValidationInfo) -> str:
        if value == info.data.get("password_current"):
            raise ValueError("Новый пароль должен отличаться от текущего")
        return value


class SessionOut(BaseModel):
    """Вход с одного устройства."""

    id: UUID = Field(..., description="ID сессии — для выхода на этом устройстве")
    device: str = Field(..., description="Браузер и устройство: «Chrome, Android, телефон»; не узнали — пусто")
    ip: str = Field(..., description="IP при входе")
    date_add: datetime = Field(..., description="Когда вошли")
    date_used: datetime = Field(..., description="Последняя активность — когда устройство продлевало вход")
    is_current: bool = Field(..., description="Это устройство")
