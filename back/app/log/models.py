import logging

from django.db import models

# Уровни logging как choices: в базе лежит число (record.levelno), в админке — название
LOG_LEVELS = (
    (logging.DEBUG, "Debug"),
    (logging.INFO, "Info"),
    (logging.WARNING, "Warning"),
    (logging.ERROR, "Error"),
    (logging.CRITICAL, "Fatal"),
)


class StatusLog(models.Model):
    """Запись журнала. Создаётся только хендлером logging, руками не пишется."""

    logger_name = models.CharField("Модуль", max_length=100, db_index=True)
    level = models.PositiveSmallIntegerField("Уровень", choices=LOG_LEVELS, default=logging.ERROR, db_index=True)
    msg = models.TextField("Сообщение")
    trace = models.TextField("Трейсбек", null=True, blank=True)
    date_add = models.DateTimeField("Записано", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал"
        ordering = ["-date_add"]

    def __str__(self):
        return self.msg[:100]
