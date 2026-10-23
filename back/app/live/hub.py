"""Живые события: открытые соединения браузеров в этом процессе и рассылка пользователю.

    from live import hub

    await hub.send(user.id, {"type": "order_paid", "order_id": order.id})   # сервис API, фоновая задача
    hub.send.sync(user_id, {"type": "order_paid", "order_id": order_id})    # админка, команда manage.py

Без `REDIS_URL` событие уходит прямо в соединения этого процесса (профиль light, один процесс API).
С `REDIS_URL` — в канал Redis, а в соединения его отдают слушатели процессов API: так событие из админки,
воркера или соседнего процесса доходит до вкладки, к какому бы процессу она ни подключилась.
Событие не хранится: открытой вкладки нет — оно пропало. Подробно — readme модуля.
"""
import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from typing import Any

from django.conf import settings
from redis.asyncio import Redis
from starlette.websockets import WebSocket

from core.bridge import with_sync
from core.broker import broker

logger = logging.getLogger(__name__)

#: Канал Redis — один на все события: каждый процесс API отдаёт своим соединениям, остальное пропускает
CHANNEL = "live"
#: Пауза перед новой попыткой слушателя, секунды: разброс — процессы не стучатся в Redis разом
RETRY_SECONDS = (1, 5)

#: Открытые соединения этого процесса: пользователь → его вкладки
_connection_set_by_user_id: dict[int, set[WebSocket]] = {}
#: Слушатель канала Redis — один на процесс, стартует с первым соединением
_listener: asyncio.Task | None = None


def connect(user_id: int, websocket: WebSocket) -> None:
    """Учесть соединение вошедшего пользователя. С Redis — запустить слушателя канала, если он ещё не слушает."""
    _connection_set_by_user_id.setdefault(user_id, set()).add(websocket)
    if settings.REDIS_URL:
        _start_listener()


def disconnect(user_id: int, websocket: WebSocket) -> None:
    """Снять соединение с учёта; соединений у пользователя не осталось — убрать и его."""
    connection_set = _connection_set_by_user_id.get(user_id, set())
    connection_set.discard(websocket)
    if not connection_set:
        _connection_set_by_user_id.pop(user_id, None)


async def deliver(user_id: int, event: Any) -> int:
    """Событие — во все соединения пользователя в этом процессе; вернуть, сколько отправлено.
    Не отправилось (вкладку закрыли) — соединение снимается с учёта молча."""
    text = json.dumps(event, ensure_ascii=False)
    count = 0
    for websocket in list(_connection_set_by_user_id.get(user_id, ())):
        try:
            await websocket.send_text(text)
            count += 1
        except Exception:
            disconnect(user_id, websocket)
    return count


@with_sync
async def send(user_id: int, event: dict) -> None:
    """Событие пользователю во все его открытые вкладки; event — словарь для JSON с ключом `type`.
    О доставке не сообщает и не падает, если Redis недоступен: событие — уведомление, а не данные."""
    if not settings.REDIS_URL:
        await deliver(user_id, event)
        return
    text = json.dumps({"user_id": user_id, "event": event}, ensure_ascii=False)
    try:
        await _publish(text)
    except Exception as error:
        logger.warning("Живые события: Redis не принял событие пользователю %s — %s: %s", user_id, type(error).__name__, error)


def _start_listener() -> None:
    global _listener
    loop = asyncio.get_running_loop()
    # Цикл событий свой у каждого запуска API (и у каждого теста): слушатель прежнего цикла остановлен с ним
    if _listener is None or _listener.done() or _listener.get_loop() is not loop:
        _listener = loop.create_task(_listen_forever())


async def _listen_forever() -> None:
    """Каждое сообщение канала — соединениям этого процесса. Связь с Redis пропала — предупреждение в журнал
    и новая попытка; соединения браузеров остаются открытыми."""
    while True:
        try:
            async for text in _listen():
                await _deliver_message(text)
        except Exception as error:
            logger.warning("Живые события: нет связи с Redis, новая попытка через несколько секунд — %s: %s",
                           type(error).__name__, error)
        await asyncio.sleep(random.uniform(*RETRY_SECONDS))


async def _deliver_message(text: str | bytes) -> None:
    try:
        message = json.loads(text)
        user_id, event = message["user_id"], message["event"]
        if type(user_id) is not int:
            raise TypeError(f"user_id — {type(user_id).__name__}, а не число")
    except (ValueError, RecursionError, TypeError, KeyError) as error:
        logger.warning("Живые события: непонятное сообщение в канале Redis пропущено — %s: %s", type(error).__name__, error)
        return
    await deliver(user_id, event)


# Транспорт Redis — две маленькие функции: тесты подменяют их каналом в памяти.
# Соединения — из пула брокера задач (тот же Redis): мост сам закрывает их после .sync() из команды manage.py,
# у вызова там свой цикл событий, а соединение Redis живёт только в цикле, где открыто


async def _publish(text: str) -> None:
    async with Redis(connection_pool=broker.connection_pool) as redis:
        await redis.publish(CHANNEL, text)


async def _listen() -> AsyncIterator[bytes]:
    async with Redis(connection_pool=broker.connection_pool) as redis, redis.pubsub() as pubsub:
        await pubsub.subscribe(CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]
