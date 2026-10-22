"""Единый формат ошибок API.

- HTTPException → {"message": "..."} (или dict из detail как есть)
- 422 валидации → {"message": "...", "full_error": [{"type", "loc", "msg"}]} на русском;
  ошибки полей из сервисов — тем же форматом через field_error()
- DoesNotExist из Tortoise → 404 {"message": "Не найдено"}
- ExternalServiceError из core.http → 502 {"message": "Сервис «…» недоступен…"}, в журнал — предупреждение
- любое другое исключение → 500 {"message": "Внутренняя ошибка сервера"}
"""
import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from tortoise.exceptions import DoesNotExist

from core.http import ExternalServiceError
from core.translations import HTTP_MESSAGES, VALIDATION_MESSAGES

logger = logging.getLogger(__name__)


def _validation_message(error: dict) -> str:
    template = VALIDATION_MESSAGES.get(error.get("type", ""))
    if template is None:
        # ValueError из своих валидаторов приходит как "Value error, <текст>" — отдаём сам текст
        return error.get("msg", "").removeprefix("Value error, ")
    try:
        return template.format(**(error.get("ctx") or {}))
    except (KeyError, IndexError):
        return template


def field_error(error_map: dict[str, str]) -> HTTPException:
    """Ошибки полей, найденные сервисом, — 422 в том же формате, что ошибки схемы: сайт покажет
    их под полями. error_map — {поле: текст}; одинаковые тексты в message не повторяются.

        raise field_error({"phone": "Укажите телефон или email", "email": "Укажите телефон или email"})
    """
    return HTTPException(422, {
        "message": "; ".join(dict.fromkeys(error_map.values())),
        "full_error": [{"type": "value_error", "loc": field, "msg": message} for field, message in error_map.items()],
    })


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        content = exc.detail
    elif exc.detail == HTTPStatus(exc.status_code).phrase:
        # detail не задан — Starlette подставил английскую фразу статуса
        content = {"message": HTTP_MESSAGES.get(exc.status_code, exc.detail)}
    else:
        content = {"message": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail_list = []
    for error in exc.errors():
        # loc вида ("body", "items", 0) — берём имя поля, а не индекс элемента
        field_list = [str(part) for part in error.get("loc", []) if not isinstance(part, int)]
        detail_list.append({
            "type": error.get("type", ""),
            "loc": field_list[-1] if field_list else "",
            "msg": _validation_message(error),
        })
    return JSONResponse(
        status_code=422,
        content={"message": "; ".join(detail["msg"] for detail in detail_list), "full_error": detail_list},
    )


async def does_not_exist_handler(request: Request, exc: DoesNotExist) -> JSONResponse:
    """Model.get() без записи → 404, текст исключения (с именем модели) наружу не отдаём."""
    return JSONResponse(status_code=404, content={"message": HTTP_MESSAGES[404]})


async def external_service_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
    """Внешний сервис не ответил или ответил ошибкой → 502. Наш код в порядке — в журнал предупреждение
    одной строкой (что ответил сервис), а не ошибка с трейсом; посетителю — понятный текст."""
    logger.warning(f"{request.method} {request.url.path} — {exc}")
    return JSONResponse(status_code=502, content={"message": f"Сервис «{exc.service}» недоступен. Попробуйте позже"})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Необработанная ошибка → 500 в нашем формате. В stdout трейсбек пишет uvicorn:
    Starlette после ответа пробрасывает исключение дальше. Свой вызов нужен для журнала
    в БД — логи uvicorn туда не попадают, только логи модулей проекта."""
    logger.exception(f"{request.method} {request.url.path} — необработанная ошибка", exc_info=exc)
    return JSONResponse(status_code=500, content={"message": HTTP_MESSAGES[500]})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(DoesNotExist, does_not_exist_handler)
    app.add_exception_handler(ExternalServiceError, external_service_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
