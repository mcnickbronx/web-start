"""Мост: асинхронный сервис (Tortoise) из синхронного кода — админки и команд manage.py.

Сервис пишется один раз, асинхронным, и помечается декоратором:

    @with_sync
    async def resend_request_email(form_request_id: int) -> None: ...

    await resend_request_email(form_request.id)     # API и задачи — как обычно
    resend_request_email.sync(form_request.id)      # админка и команды — ждёт результата

Передавать id, а не объект Django. Транзакции с Django у вызова нет: Tortoise не видит
того, что админка сохранила, но ещё не закоммитила, поэтому рядом с сохранением через
Django — только из transaction.on_commit.
"""
import asyncio
from collections.abc import Awaitable, Callable
from functools import update_wrapper

from asgiref.sync import async_to_sync
from taskiq import InMemoryBroker
from tortoise.context import TortoiseContext

from core.broker import broker
from core.orm import tortoise_config

#: Цикл событий API в этом процессе — запоминает старт API (project/api.py). Только в нём
#: открыты соединения API: из любого другого цикла ими пользоваться нельзя
api_loop: asyncio.AbstractEventLoop | None = None


class with_sync[**P, R]:
    """Декоратор асинхронного сервиса: вызов как раньше и `.sync(...)` для синхронного кода."""

    def __init__(self, func: Callable[P, Awaitable[R]]) -> None:
        self.func = func
        update_wrapper(self, func)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        return self.func(*args, **kwargs)

    def sync(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return async_to_sync(_call)(self.func, *args, **kwargs)


async def _call[R](func: Callable[..., Awaitable[R]], *args, **kwargs) -> R:
    if asyncio.get_running_loop() is api_loop:
        # Админка в одном процессе с API — так она работает везде: asgiref выполняет вызов
        # в цикле событий API, где Tortoise и очередь задач уже подняты, — берём их
        return await func(*args, **kwargs)
    # Команды manage.py, обычный поток: у вызова свой цикл
    # событий — поднимаем Tortoise на один вызов. Соединения с базой и Redis привязаны
    # к циклу, в котором открыты: держать их между вызовами нельзя
    async with TortoiseContext() as context:
        await context.init(config=tortoise_config())
        try:
            return await func(*args, **kwargs)
        finally:
            await _release_broker()


async def _release_broker() -> None:
    """Цикл вызова сейчас закроется. Задачи без Redis выполняются в нём же — дождаться,
    иначе они оборвутся. Соединения с Redis — закрыть: следующий вызов придёт в другом цикле."""
    if isinstance(broker, InMemoryBroker):
        # Только задачи этого цикла: у API в том же процессе свои, и ждать их отсюда нельзя
        await asyncio.gather(*(asyncio.all_tasks() - {asyncio.current_task()}))
    else:
        await broker.connection_pool.disconnect()
