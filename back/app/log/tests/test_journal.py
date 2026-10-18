"""Журнал в базе: строка от хендлера, путь через очередь и поток слушателя, фильтр модулей, уборка clear_log."""
import logging
import queue
import sys
from datetime import timedelta
from io import StringIO
from logging.handlers import QueueListener

from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone

from log.handlers import DatabaseLogHandler, ProjectOnlyFilter, RecordQueueHandler
from log.models import StatusLog


def make_record(name="form.services", level=logging.WARNING, exc_info=None):
    return logging.LogRecord(name, level, __file__, 1, "Письмо по заявке %s не ушло", (7,), exc_info)


def error_info():
    try:
        raise ValueError("мусор от сервиса")
    except ValueError:
        return sys.exc_info()


class ThreadDatabaseLogHandler(DatabaseLogHandler):
    def emit(self, record):
        super().emit(record)
        connection.close()   # поток слушателя кончается, а его соединение остаётся открытым — psycopg выдаёт ResourceWarning


class ProjectOnlyFilterTest(SimpleTestCase):
    def test_only_project_modules(self):
        """В журнал — модули проекта; django и uvicorn — только в stdout."""
        log_filter = ProjectOnlyFilter()
        self.assertTrue(log_filter.filter(make_record(name="form.services")))
        self.assertTrue(log_filter.filter(make_record(name="core.errors")))
        self.assertFalse(log_filter.filter(make_record(name="django.request")))
        self.assertFalse(log_filter.filter(make_record(name="uvicorn.error")))


class DatabaseLogTest(TransactionTestCase):
    # Не TestCase: emit() зовёт close_old_connections(), а она закрывает соединение, если автокоммит
    # не как в настройках, — в TestCase это соединение теста с открытой транзакцией

    def test_emit_writes_row(self):
        """Хендлер пишет одну строку: модуль, уровень, сообщение с подставленными аргументами, без трейсбека."""
        DatabaseLogHandler().emit(make_record())
        row = StatusLog.objects.get()
        self.assertEqual((row.logger_name, row.level, row.msg, row.trace), ("form.services", logging.WARNING, "Письмо по заявке 7 не ушло", None))

    def test_queue_to_database(self):
        """Как на сервере: запись в очередь, в базу её пишет поток слушателя — с трейсбеком, без чужого шума."""
        # Очередь и слушателя собираем сами, как в LOGGING: при TESTING хендлера db нет, слушатель не запущен
        handler = RecordQueueHandler(queue.Queue())
        handler.addFilter(ProjectOnlyFilter())
        with QueueListener(handler.queue, ThreadDatabaseLogHandler()):   # на выходе stop() дожидается, пока очередь допишется
            handler.handle(make_record(level=logging.ERROR, exc_info=error_info()))
            handler.handle(make_record(name="django.request"))
        row = StatusLog.objects.get()
        self.assertEqual((row.logger_name, row.level), ("form.services", logging.ERROR))
        self.assertIn("ValueError: мусор от сервиса", row.trace)


class ClearLogTest(TestCase):
    def test_clear_log_command(self):
        """Уборка из crontab: старше --days удаляется, свежее остаётся."""
        old = StatusLog.objects.create(logger_name="form", msg="старое")
        StatusLog.objects.create(logger_name="form", msg="новое")
        StatusLog.objects.filter(pk=old.pk).update(date_add=timezone.now() - timedelta(days=91))   # auto_now_add
        out = StringIO()
        call_command("clear_log", days=90, stdout=out)
        self.assertEqual(list(StatusLog.objects.values_list("msg", flat=True)), ["новое"])
        self.assertIn("Удалено записей: 1", out.getvalue())
