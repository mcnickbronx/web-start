"""Брокер фоновых задач (taskiq).

Есть `REDIS_URL` — задачи уходят в Redis, их разбирает отдельный процесс-воркер
(`taskiq worker project.worker:broker`, см. project/worker.py). Нет — задачи выполняются сразу
в текущем процессе: локально можно работать без Redis и без воркера.

Задача объявляется в `<module>/tasks.py`:

    @broker.task
    async def send_something(user_id: int) -> None: ...

и вызывается из сервиса или эндпоинта: `await send_something.kiq(user.id)`.
Вызов не ждёт выполнения — если задача упадёт, основное действие уже завершено.

Задача может выполниться дважды: воркер упал посреди неё — через 10 минут её заберёт
другой. Поэтому задача должна спокойно переживать повтор.
"""
from django.conf import settings
from taskiq import AsyncBroker, InMemoryBroker
from taskiq_redis import RedisStreamBroker


def create_broker() -> AsyncBroker:
    if settings.REDIS_URL:
        # Поток Redis с подтверждением: задача уходит из очереди, только когда выполнена.
        # consumer_id="0" — задачи, поставленные до первого запуска воркера, не теряются.
        # maxlen — хвост выполненных задач не растёт без предела. Имя очереди новое:
        # под ключом "taskiq" прежний брокер хранил список, и поток там не создать
        return RedisStreamBroker(settings.REDIS_URL, queue_name="tasks", consumer_id="0", maxlen=10_000)
    return InMemoryBroker()


broker = create_broker()
