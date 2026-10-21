"""История изменений записи: кто, когда и что поменял — было → стало.

Таблица истории своя у каждой модели, в её модуле, на основе HistoryModel:

    class FormRequestHistory(HistoryModel):
        record = models.ForeignKey(FormRequest, models.CASCADE, related_name="history")

Удалили запись в админке — история уходит с ней. Из API (Tortoise) запись с историей удаляется
после неё: `await FormRequestHistory.filter(record_id=...).delete()`.

Пишут в неё только две вещи из core:
- админка — HistoryAdmin (core/history_admin.py): поля в history_fields;
- сервис — декоратор @history ниже.
Сигналы не годятся: API пишет через Tortoise мимо сигналов Django, а filter().update() — мимо
сигналов обеих ORM. Декоратор сравнивает строку в базе до вызова и после — ему всё равно,
как сервис её поменял.
"""
import functools
import inspect
import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from tortoise.transactions import in_transaction


class HistoryModel(models.Model):
    """Основа таблицы истории: запись (поле record) модуль добавляет сам."""

    date = models.DateTimeField("Когда", auto_now_add=True)
    # Без ограничения в базе: пользователя можно удалить и из API — в истории останется его номер
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True, db_constraint=False, related_name="+", verbose_name="Кто")
    changes = models.JSONField("Что изменилось", default=dict, help_text="{поле: [было, стало]}; поле без значений — null")

    class Meta:
        abstract = True
        ordering = ["-id"]
        verbose_name = "Изменение"
        verbose_name_plural = "История"

    def __str__(self):
        return f"Изменение №{self.pk}"


def diff(before: dict, after: dict, hidden=()) -> dict:
    """{поле: [было, стало]} по изменившимся полям; скрытые — только факт: {поле: None}."""
    # Даты, деньги, UUID — строкой, как их сохранит JSON
    before, after = (json.loads(json.dumps(values, cls=DjangoJSONEncoder)) for values in (before, after))
    return {name: None if name in hidden else [before[name], after[name]] for name in after if before[name] != after[name]}


def history(model, fields: list[str], hidden: list[str] = ()):
    """Сервис, который меняет запись, — с историей: что он поменял, ляжет в таблицу model.

        @history(models_async.FormRequestHistory, ["status"])
        async def set_status(form_request_id: int, status: str, user=None): ...

    Запись — первый аргумент сервиса (её id), кто — аргумент user сервиса: пользователь или его id,
    None — система. Строку до вызова читает с блокировкой, после — снова и пишет разницу в той же
    транзакции. Ничего не поменялось — строки нет. hidden — поля, у которых пишется только факт
    изменения, без значений (телефон, email).
    """
    def decorator(func):
        signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            arguments = signature.bind(*args, **kwargs).arguments
            record_id, user = next(iter(arguments.values())), arguments.get("user")
            user_id = getattr(user, "pk", user)  # пользователь Django или Tortoise — его id
            if user_id is not None and (not isinstance(user_id, int) or isinstance(user_id, bool)):
                raise TypeError(f"@history: user — пользователь, его id или None, а не {user!r}")
            record_model = model._meta.fields_map["record"].related_model
            async with in_transaction():
                # Блокировка — отдельным запросом: с .values() Tortoise молча теряет FOR UPDATE
                await record_model.filter(id=record_id).select_for_update().only("id").first()
                before = await record_model.filter(id=record_id).values(*fields)
                result = await func(*args, **kwargs)
                after = await record_model.filter(id=record_id).values(*fields)
                if before and after and (changes := diff(before[0], after[0], hidden)):
                    await model.create(record_id=record_id, user_id=user_id, changes=changes)
            return result
        return wrapper
    return decorator
