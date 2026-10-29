"""Короткий вызов ИИ через core.http; схема и общий лимит пользователя — здесь, данные — у модуля."""
import asyncio
import json
import logging
from urllib.parse import urlsplit

import aiohttp
from django.core.exceptions import ImproperlyConfigured
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from core import cache, http
from core.env import env_int, env_str

logger = logging.getLogger(__name__)


def _url(name: str, default: str) -> str:
    value = env_str(name, default, is_secret=True)
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.query and not parsed.fragment
        parsed.port  # неверный порт — тоже ошибка настройки, без адреса в исключении
    except ValueError:
        valid = False
    if (value and not valid) or (not value and name == "AI_BASE_URL"):
        raise ImproperlyConfigured(f"{name}: нужен адрес http:// или https:// без query и fragment") from None
    return value.rstrip("/")


def _number(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        return env_int(name, default, min_value=minimum, max_value=maximum)
    except ImproperlyConfigured:
        bounds = f"от {minimum} до {maximum}" if maximum is not None else f"не меньше {minimum}"
        raise ImproperlyConfigured(f"{name}: нужно целое число, {bounds}") from None


BASE_URL = _url("AI_BASE_URL", "https://api.openai.com/v1")
API_KEY = env_str("AI_API_KEY", "", is_secret=True)
MODEL = env_str("AI_MODEL", "gpt-5.6-terra")
PROXY = _url("AI_PROXY", "")
TIMEOUT = _number("AI_TIMEOUT", 60, 1, 600)
USER_LIMIT = _number("AI_USER_LIMIT", 100, 0)


def _error(service: str, status: int | None = None, detail: str = "не удалось получить ответ ИИ"):
    hint = {401: "проверьте AI_API_KEY", 403: "проверьте доступ к сервису", 404: "проверьте AI_BASE_URL и AI_MODEL"}
    if status is not None:
        detail = f"ответил {status}; {hint.get(status, 'попробуйте позже')}"
    return http.ExternalServiceError(service, detail, status)


async def chat(messages: list[dict], *, service: str, user_id: int | None,
               schema: type[BaseModel] | None = None, model: str | None = None) -> BaseModel | str:
    """Один слот на вызов; максимум один повтор схемы и два HTTP-повтора на весь вызов.
    user_id=None — явное снятие пользовательского лимита для команды/фоновой задачи."""
    if not API_KEY:
        raise _error(service, detail="ИИ выключен: задайте AI_API_KEY")
    if USER_LIMIT and user_id is not None and not await cache.hit(f"ai:user:{user_id}", USER_LIMIT, 3600):
        raise HTTPException(429, f"Лимит запросов к ИИ — {USER_LIMIT} в час. Попробуйте позже")
    payload = {"model": model or MODEL, "messages": list(messages)}
    if schema is not None:
        payload["response_format"] = {"type": "json_object"}
        payload["messages"] = [{"role": "system", "content": "Верни JSON по схеме: " + json.dumps(schema.model_json_schema(), ensure_ascii=False)}, *messages]
    http_retries, schema_retries = 0, 0
    while True:
        try:
            data = await http.request_json(
                "POST", BASE_URL + "/chat/completions", service=service, json=payload,
                headers={"Authorization": f"Bearer {API_KEY}"}, proxy=PROXY or None,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            )
        except http.ExternalServiceError as error:
            if error.status in {429, 500, 502, 503} and http_retries < 2:
                http_retries += 1
                await asyncio.sleep(http_retries)
                continue
            raise _error(service, error.status) from None
        try:
            message = data["choices"][0]["message"]
            content = message["content"]
            valid = not message.get("refusal") and isinstance(content, str) and bool(content.strip())
        except (KeyError, IndexError, TypeError):
            valid = False
        if not valid:
            raise _error(service, detail="ИИ вернул пустой ответ, отказ или неверное тело") from None
        if schema is not None:
            try:
                result = schema.model_validate_json(content)
            except ValidationError as error:
                # msg/input/ctx и динамические ключи loc могут содержать секреты. Только известные поля.
                fields = sorted({str(item["loc"][0]) for item in error.errors(include_url=False, include_context=False, include_input=False)
                                 if item["loc"] and item["loc"][0] in schema.model_fields})
                if schema_retries:
                    raise _error(service, detail="ответ ИИ не соответствует JSON-схеме") from None
                schema_retries += 1
                payload["messages"] += [{"role": "assistant", "content": content},
                                        {"role": "user", "content": "Исправь JSON по схеме. Ошибочные поля: " + (", ".join(fields) or "корень JSON")}]
                continue
        else:
            result = content
        # usage приходит от внешнего сервиса: в журнал разрешены только числовые счётчики.
        usage = data.get("usage")
        usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                 if isinstance(usage, dict) and type(usage.get(key)) is int}
        logger.info("ИИ service=%s model=%s user_id=%s usage=%s", service, payload["model"], user_id, usage)
        return result
