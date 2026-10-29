"""Кэш справочников: значение из кэша одной строкой в сервисе API, сброс — когда запись сохранили в админке.

    # services.py модуля
    return await cache.get_or_set("page:category_list", lambda: models_async.PageCategory.filter(...).values(...), ttl=600)

    # apps.py модуля, в ready()
    cache.clear_on_change(PageCategory, "page:category_list")

Хранилище — кэш Django из settings.py: с `REDIS_URL` — Redis, без него кэша нет (`DummyCache`).
Кэш некритичный: Redis не ответил — значение из базы и предупреждение в журнал. Подробно — readme ядра, «Кэш».
"""
import asyncio
import functools
import logging
import math
import time
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Any

from django.core.cache import caches
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.redis import RedisCache
from django.core.signals import setting_changed
from django.db import transaction
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

_MISSING = object()
_hit_lock = Lock()
_hit_memory: dict[str, tuple[int, float]] = {}
# INCR Django делает EXISTS отдельно: ключ мог истечь перед INCR и создаться без срока.
# Один скрипт считает и задаёт срок атомарно; обычный запрос окно не продлевает.
_HIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 or redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


@functools.cache
def backend():
    """Один объект кэша на процесс. Не `django.core.cache.cache`: в API каждый запрос — своя задача asyncio,
    и Django заводил бы на каждый запрос новый объект, а с ним и новое соединение с Redis."""
    return caches.create_connection("default")


def reset_backend(setting: str, **kwargs) -> None:
    if setting == "CACHES":  # override_settings в тестах
        backend.cache_clear()


setting_changed.connect(reset_backend)


def _hit(key: str, limit: int, period: int) -> bool:
    try:
        store = backend()
        if not isinstance(store, DummyCache):
            if not isinstance(store, RedisCache):
                raise TypeError("Счётчик требует RedisCache")
            redis_key = store.make_and_validate_key(key)
            client = store._cache.get_client(redis_key, write=True)
            return client.eval(_HIT_SCRIPT, 1, redis_key, math.ceil(period)) <= limit
    except Exception:
        logger.warning("Счётчик Redis недоступен — лимит в памяти процесса")
    with _hit_lock:
        now = time.monotonic()
        for expired in [item for item, (_, end) in _hit_memory.items() if end <= now]:
            del _hit_memory[expired]
        count, end = _hit_memory.get(key, (0, now + period))
        _hit_memory[key] = (count + 1, end)
        return count < limit


async def hit(key: str, limit: int, period: int) -> bool:
    """Пропустить не больше limit вызовов за period секунд от первого; без Redis — память процесса."""
    if limit <= 0 or period <= 0:
        raise ValueError("Счётчик: limit и period должны быть больше нуля")
    return await asyncio.to_thread(_hit, key, limit, period)


async def get_or_set(key: str, fetch: Callable[[], Awaitable[Any]], ttl: int) -> Any:
    """Значение из кэша, а нет — `await fetch()`, в кэш на `ttl` секунд и вернуть.
    Хранить словари, списки, строки — не объекты ORM. Срок обязателен: Redis при нехватке памяти вытесняет
    только ключи со сроком (volatile-lru в compose.yml), ключ без срока остался бы навсегда."""
    if ttl is None or ttl <= 0:
        raise ValueError(f"Кэш {key}: нужен срок в секундах — ключ без срока Redis не вытеснит")
    # Обычные get/set в пуле потоков, а не aget/aset Django: те идут через один общий поток
    # (sync_to_async с thread_sensitive=True), и запросы API к кэшу вставали бы к нему в очередь
    try:
        value = await asyncio.to_thread(backend().get, key, _MISSING)
    except Exception as error:
        logger.warning("Кэш не прочитан, %s — из базы: %s", key, error)
        return await fetch()
    if value is not _MISSING:
        return value
    value = await fetch()
    try:
        await asyncio.to_thread(backend().set, key, value, ttl)
    except Exception as error:
        logger.warning("Кэш не записан, %s: %s", key, error)
    return value


def clear_on_change(model, *keys: str) -> None:
    """Сбрасывать ключи, когда запись модели сохранили или удалили через Django: админка, команды, `save()`.
    Запись из API через Tortoise и `QuerySet.update()` сигналов не шлют — тогда кэш доживёт до конца срока."""

    def clear(using: str, **kwargs) -> None:
        # После фиксации транзакции: иначе запрос API между сбросом и фиксацией положил бы в кэш старое
        transaction.on_commit(lambda: delete(keys), using=using)

    # weak=False: clear — локальная функция, по слабой ссылке сборщик убрал бы её сразу после выхода отсюда.
    # Тест этого не поймает: при DEBUG Django держит получателя в своём кэше и без нас
    uid = f"core.cache:{model._meta.label}:{','.join(keys)}"
    post_save.connect(clear, sender=model, weak=False, dispatch_uid=uid)
    post_delete.connect(clear, sender=model, weak=False, dispatch_uid=uid)


def delete(keys: tuple[str, ...]) -> None:
    try:
        backend().delete_many(keys)
    except Exception as error:
        # Сохранение в админке не падает из-за кэша: старое значение проживёт до конца срока
        logger.warning("Кэш не сброшен, %s: %s", ", ".join(keys), error)
