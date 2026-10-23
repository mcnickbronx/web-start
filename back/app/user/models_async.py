"""Файл сгенерирован автоматически командой manage.py sync_async_models.

Не редактировать: источник схемы — models.py этого же модуля, правки затрёт
следующая генерация. После изменения моделей: makemigrations → sync_async_models.
Когда файл менялся и почему — в истории git.
"""
from uuid import uuid4

from django.utils.timezone import now

from tortoise import fields
from tortoise.models import Model


class CustomUser(Model):
    """Пользователь с логином по email."""

    id = fields.BigIntField(primary_key=True)
    password = fields.CharField(max_length=128, default="")
    last_login = fields.DatetimeField(null=True)
    is_superuser = fields.BooleanField(default=False)
    first_name = fields.CharField(max_length=150, default="")
    last_name = fields.CharField(max_length=150, default="")
    is_staff = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    date_joined = fields.DatetimeField(default=now)
    email = fields.CharField(max_length=254, unique=True)
    confirmation_code = fields.CharField(max_length=6, null=True)
    confirmation_code_created_at = fields.DatetimeField(null=True)
    confirmation_code_attempts = fields.SmallIntField(default=0)
    password_changed_at = fields.DatetimeField(null=True)
    is_confirmed = fields.BooleanField(default=True)
    # groups: связь на auth.Group (вне проекта) не генерируется
    # user_permissions: связь на auth.Permission (вне проекта) не генерируется

    class Meta:
        table = "user_customuser"

    def __str__(self):
        return f"CustomUser {self.pk}"


class UserSession(Model):
    """Вход с одного устройства: удалили сессию — токены этого устройства сразу недействительны."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    user = fields.ForeignKeyField("models.CustomUser", related_name="usersession_set", on_delete=fields.CASCADE)
    user_agent = fields.CharField(max_length=500, default="")
    ip = fields.CharField(max_length=45, default="")
    date_add = fields.DatetimeField(auto_now_add=True)
    date_used = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_usersession"
        ordering = ['-date_used']

    def __str__(self):
        return f"UserSession {self.pk}"
