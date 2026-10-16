"""Файл сгенерирован автоматически командой manage.py sync_async_models.

Не редактировать: источник схемы — models.py этого же модуля, правки затрёт
следующая генерация. После изменения моделей: makemigrations → sync_async_models.
Когда файл менялся и почему — в истории git.
"""
from tortoise import fields
from tortoise.models import Model


class StatusLog(Model):
    """Запись журнала. Создаётся только хендлером logging, руками не пишется."""

    id = fields.BigIntField(primary_key=True)
    logger_name = fields.CharField(max_length=100, db_index=True, default="")
    level = fields.SmallIntField(db_index=True, default=40)
    msg = fields.TextField(default="")
    trace = fields.TextField(null=True)
    date_add = fields.DatetimeField(auto_now_add=True, db_index=True)

    class Meta:
        table = "log_statuslog"
        ordering = ['-date_add']

    def __str__(self):
        return f"StatusLog {self.pk}"
