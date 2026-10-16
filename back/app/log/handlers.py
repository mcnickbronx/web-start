"""Запись логов в БД: журнал виден в админке и переживает перезапуск контейнеров.

Зачем очередь. API асинхронный, а Django ORM из async-контекста бросает
SynchronousOnlyOperation — писать в базу прямо в хендлере нельзя. Поэтому
`logger.info(...)` только кладёт запись в очередь в памяти (не блокирует и не требует
await), а в базу её пишет поток слушателя: там контекст синхронный и ORM работает.
Вызов из-за этого одинаков везде — в эндпоинте, сервисе, задаче, админке и команде.

Очередь и слушателя создаёт сам dictConfig по настройкам LOGGING (см. settings.py),
здесь только то, что он создать не может: фильтр, сохранение трейсбека и запись в базу.

Цена решения: запись «выстрелил и забыл». Если процесс убили жёстко или база
недоступна, запись потеряется, а основное действие не пострадает. Поэтому в журнал
идёт только некритичное: то, что терять нельзя, — обычная модель и обычная запись.
"""
import atexit
import logging
from functools import cache
from logging.handlers import QueueHandler

from django.core.exceptions import AppRegistryNotReady

_listener_started = False


@cache
def project_app_labels() -> frozenset[str]:
    from core.generator import project_app_configs

    return frozenset(app_config.label for app_config in project_app_configs())


class ProjectOnlyFilter(logging.Filter):
    """В базу — только логи модулей проекта: django, uvicorn и tortoise шумят и без нас."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            return record.name.split(".")[0] in project_app_labels()
        except AppRegistryNotReady:
            # Логи на старте, до загрузки приложений: писать некуда, таблицы ещё нет
            return False


class RecordQueueHandler(QueueHandler):
    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """Запись идёт между потоками одного процесса, сериализовать нечего.
        Стандартный prepare() форматирует сообщение и обнуляет exc_info — трейсбек
        был бы потерян, а колонка trace всегда оставалась пустой."""
        return record


class DatabaseLogHandler(logging.Handler):
    """Пишет запись в StatusLog. Работает только в потоке слушателя — там можно синхронный ORM."""

    def emit(self, record: logging.LogRecord) -> None:
        from django.db import close_old_connections

        from log.models import StatusLog

        try:
            # Поток живёт всё время работы процесса, соединение могло закрыться со стороны сервера
            close_old_connections()
            StatusLog.objects.create(
                logger_name=record.name,
                level=record.levelno,
                msg=record.getMessage(),
                trace=self.format_trace(record),
            )
        except Exception:
            # Логирование не должно ронять ничего, даже себя. handleError печатает в stderr,
            # его подхватит docker. Своим logger.error здесь пользоваться нельзя — рекурсия
            self.handleError(record)

    @staticmethod
    def format_trace(record: logging.LogRecord) -> str | None:
        if not record.exc_info:
            return None
        return logging.Formatter().formatException(record.exc_info)


def start_listener() -> None:
    """Запускает поток, который пишет очередь в базу. Вызывается из LogConfig.ready()."""
    global _listener_started
    if _listener_started:
        return

    handler = logging.getHandlerByName("db")
    listener = getattr(handler, "listener", None)
    if listener is None:
        return   # хендлера нет в LOGGING — журнал отключён, это допустимо

    listener.start()
    _listener_started = True
    # Дренаж очереди при остановке процесса, иначе последние записи не доедут
    atexit.register(listener.stop)
