"""Общие схемы ответов API."""
from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    message: str = Field(..., description="Сообщение")


class ValidationErrorDetail(BaseModel):
    type: str = Field(..., description="Тип ошибки")
    loc: str = Field(..., description="Поле с ошибкой")
    msg: str = Field(..., description="Сообщение об ошибке")


class ValidationErrorOut(BaseModel):
    message: str = Field(..., description="Все ошибки одной строкой")
    full_error: list[ValidationErrorDetail] = Field(..., description="Ошибки по полям")
