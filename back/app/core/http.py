"""Клиент внешних API: одна сессия aiohttp на процесс, таймаут по умолчанию, сбой сервиса — 502.

    data = await http.request_json("GET", url, service="Поиск запчастей", params={"q": number})

Нет связи, таймаут или ответ 400 и выше — ExternalServiceError: API ответит 502 «Сервис «…» недоступен»
(обработчик — core/errors.py). Свой разбор ответа (статусы, текст) — `http.session()` напрямую, как капча формы.
"""
import asyncio
from typing import Any

import aiohttp

TIMEOUT = 60

_loop: asyncio.AbstractEventLoop | None = None
_session: aiohttp.ClientSession | None = None


class ExternalServiceError(Exception):
    """Внешний сервис не ответил или ответил ошибкой. status — код ответа, None — ответа не было."""

    def __init__(self, service: str, detail: str, status: int | None = None) -> None:
        super().__init__(f"Сервис «{service}»: {detail}")
        self.service, self.status = service, status


def session() -> aiohttp.ClientSession:
    """Общая сессия: соединения переиспользуются, таймаут 60 с (свой — `timeout=aiohttp.ClientTimeout(total=10)`
    в запросе). Сессия привязана к циклу событий: в другом цикле (команда manage.py) — новая."""
    global _loop, _session
    loop = asyncio.get_running_loop()
    if _session is None or _session.closed or _loop is not loop:
        if _session is not None and _loop.is_closed():
            # Цикл закрыли, не закрыв сессию (asyncio.run в тесте): ждать закрытия уже не в чем — без шума в журнале
            _session.detach()
        _loop, _session = loop, aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT))
    return _session


async def close() -> None:
    """Закрыть сессию этого цикла: при остановке API и воркера, в конце вызова моста из команды manage.py."""
    global _session
    if _session is not None and _loop is asyncio.get_running_loop():
        await _session.close()
        _session = None


async def request_json(method: str, url: str, *, service: str, **kwargs) -> Any:
    """JSON ответа сервиса. kwargs — как у aiohttp: params, json, data, headers, timeout.
    service — название для человека: его увидит посетитель в ошибке 502 и разработчик в журнале."""
    try:
        async with session().request(method, url, **kwargs) as response:
            if response.status >= 400:
                text = (await response.text())[:500]
                raise ExternalServiceError(service, f"ответил {response.status}: {text}", response.status)
            return await response.json(content_type=None)
    except TimeoutError as error:
        raise ExternalServiceError(service, "нет ответа, таймаут") from error
    except (aiohttp.ClientError, ValueError) as error:  # ValueError — ответ не JSON
        raise ExternalServiceError(service, f"{type(error).__name__}: {error}") from error
