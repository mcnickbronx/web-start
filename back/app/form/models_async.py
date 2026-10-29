"""Файл сгенерирован автоматически командой manage.py sync_async_models.

Не редактировать: источник схемы — models.py этого же модуля, правки затрёт
следующая генерация. После изменения моделей: makemigrations → sync_async_models.
Когда файл менялся и почему — в истории git.
"""
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model


class FormType(Model):
    """Форма на сайте: заявка на звонок, обратная связь, отклик на вакансию."""

    id = fields.BigIntField(primary_key=True)
    name = fields.CharField(max_length=200, default="")
    code = fields.CharField(max_length=100, unique=True)
    email_to = fields.CharField(max_length=500, default="")
    telegram_chat = fields.CharField(max_length=500, default="")
    is_telegram_contacts = fields.BooleanField(default=False)
    email_subject = fields.CharField(max_length=250, default="")
    is_email_tech_info = fields.BooleanField(default=False)
    is_contact_required = fields.BooleanField(default=True)
    is_name_required = fields.BooleanField(default=False)
    is_phone_required = fields.BooleanField(default=False)
    is_email_required = fields.BooleanField(default=False)
    is_message_required = fields.BooleanField(default=False)
    is_captcha = fields.BooleanField(default=False)
    is_trap = fields.BooleanField(default=True)
    is_file = fields.BooleanField(default=False)
    file_count_max = fields.SmallIntField(default=5)
    is_active = fields.BooleanField(default=True)
    date_add = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "form_formtype"
        ordering = ['name']

    def __str__(self):
        return f"FormType {self.pk}"


class FormRequest(Model):
    """Заявка с формы на сайте."""

    id = fields.BigIntField(primary_key=True)
    form_type = fields.ForeignKeyField("models.FormType", related_name="formrequest_set", on_delete=fields.NO_ACTION)
    user = fields.ForeignKeyField("models.CustomUser", related_name="formrequest_set", on_delete=fields.NO_ACTION, null=True)
    name = fields.CharField(max_length=200, default="")
    phone = fields.CharField(max_length=40, default="")
    email = fields.CharField(max_length=254, default="")
    message = fields.TextField(default="")
    data = fields.JSONField(default=dict)
    source = fields.CharField(max_length=500, default="")
    ip = fields.CharField(max_length=45, default="")
    user_agent = fields.CharField(max_length=500, default="")
    channel = fields.CharField(max_length=10, db_index=True, default="")
    referrer = fields.CharField(max_length=1000, default="")
    landing_page = fields.CharField(max_length=1000, default="")
    utm = fields.JSONField(default=dict)
    ym_client_id = fields.CharField(max_length=50, default="")
    token_id = fields.UUIDField(unique=True, default=uuid4)
    status = fields.CharField(max_length=10, db_index=True, default='new')
    email_status = fields.CharField(max_length=10, default='wait')
    email_error = fields.TextField(default="")
    date_email_sent = fields.DatetimeField(null=True)
    date_add = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "form_formrequest"
        ordering = ['-id']

    def __str__(self):
        return f"FormRequest {self.pk}"


class FormRequestHistory(Model):
    id = fields.BigIntField(primary_key=True)
    date = fields.DatetimeField(auto_now_add=True)
    user = fields.ForeignKeyField("models.CustomUser", related_name=False, on_delete=fields.NO_ACTION, null=True, db_constraint=False)
    changes = fields.JSONField(default=dict)
    record = fields.ForeignKeyField("models.FormRequest", related_name="history", on_delete=fields.NO_ACTION)

    class Meta:
        table = "form_formrequesthistory"
        ordering = ['-id']

    def __str__(self):
        return f"FormRequestHistory {self.pk}"


class FormFile(Model):
    """Файл к заявке. Загружается до отправки заявки и привязывается к ней при отправке."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    form_request = fields.ForeignKeyField("models.FormRequest", related_name="formfile_set", on_delete=fields.NO_ACTION, null=True)
    token_id = fields.UUIDField(db_index=True)
    file = fields.CharField(max_length=300, default="")
    original_name = fields.CharField(max_length=255, default="")
    size = fields.IntField(default=0)
    date_add = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "form_formfile"

    def __str__(self):
        return f"FormFile {self.pk}"
