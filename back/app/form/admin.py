import json

from admin_filter_kit.filters import AutocompleteFilter
from django import forms
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html
from fastapi import HTTPException

from core.history_admin import HistoryAdmin
from core.user_agent import describe_user_agent
from core.xlsx import export_xlsx
from form import services
from form.models import FormFile, FormRequest, FormType


class FormRequestForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        # Заявку из админки проверяем так же, как с сайта. У существующей меняется только статус
        form_type = cleaned_data.get("form_type")
        if self.instance.pk is None and form_type:
            for field, message in services.request_error_map(form_type, cleaned_data).items():
                self.add_error(field, message)
        return cleaned_data


def utm_filter(key: str) -> type[admin.SimpleListFilter]:
    """Фильтр списка заявок по одной метке из JSON «Метки»: значения — те, что встречались."""

    class UtmFilter(admin.SimpleListFilter):
        title = key
        parameter_name = key

        def lookups(self, request, model_admin):
            value_list = (
                FormRequest.objects.filter(utm__has_key=key)
                .values_list(f"utm__{key}", flat=True).distinct().order_by(f"utm__{key}")[:100]
            )
            return [(value, value) for value in value_list if value]

        def queryset(self, request, queryset):
            return queryset.filter(**{f"utm__{key}": self.value()}) if self.value() else queryset

    return UtmFilter


@admin.register(FormType)
class FormTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "email_to", "is_captcha", "is_trap", "is_file", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "email_to"]
    prepopulated_fields = {"code": ["name"]}
    readonly_fields = ["date_add", "date_modified"]
    fieldsets = [
        (None, {"fields": ["name", "code", "is_active"]}),
        ("Письмо", {"fields": ["email_to", "email_subject", "is_email_tech_info"]}),
        ("Обязательные поля", {"fields": ["is_contact_required", "is_name_required", "is_phone_required", "is_email_required", "is_message_required"]}),
        ("Защита и файлы", {"fields": ["is_captcha", "is_trap", "is_file", "file_count_max"]}),
        ("Даты", {"fields": ["date_add", "date_modified"]}),
    ]


class FormFileInline(admin.TabularInline):
    model = FormFile
    fields = ["download", "size", "date_add"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False  # файлы приходят только с сайта

    @admin.display(description="Файл")
    def download(self, obj: FormFile) -> str:
        return format_html('<a href="{}">{}</a>', reverse("admin:form_formrequest_file", args=[obj.id]), obj.original_name)


@admin.register(FormRequest)
class FormRequestAdmin(HistoryAdmin):
    form = FormRequestForm
    history_fields = ["status"]
    list_display = ["__str__", "date_add", "form_type", "name", "phone", "email", "channel", "status", "email_status"]
    list_editable = ["status"]
    # «Форма» — с подсказками по названию и коду: форм бывают сотни, списком в панели не помещаются
    list_filter = ["status", "channel", ("form_type", AutocompleteFilter), utm_filter("utm_source"), utm_filter("utm_campaign"), "email_status"]
    list_select_related = ["form_type"]
    search_fields = ["name", "phone", "email", "message"]
    date_hierarchy = "date_add"
    inlines = [FormFileInline]
    actions = ["resend_email", export_xlsx]
    readonly_fields = [
        "form_type", "user", "name", "phone", "email", "message", "data_display", "source", "ip",
        "channel", "landing_page", "referrer", "utm_display", "ym_client_id", "browser", "user_agent",
        "email_status", "email_error", "date_email_sent", "date_add", "date_modified",
    ]
    fieldsets = [
        (None, {"fields": ["form_type", "status", "date_add"]}),
        ("Заявка", {"fields": ["name", "phone", "email", "message", "data_display", "user"]}),
        ("Откуда", {"fields": ["source", "channel", "landing_page", "referrer", "utm_display", "ym_client_id", "ip", "browser", "user_agent"]}),
        ("Письмо", {"fields": ["email_status", "email_error", "date_email_sent"]}),
        ("Даты", {"fields": ["date_modified"]}),
    ]

    # Заявку можно завести вручную — например, после звонка. У неё только общие поля,
    # источник «админка», и письмо по ней не уходит: менеджер о ней и так знает
    add_fieldsets = [(None, {"fields": ["form_type", "status", "name", "phone", "email", "message"]})]

    def get_fieldsets(self, request, obj=None):
        return self.add_fieldsets if obj is None else self.fieldsets

    def get_inlines(self, request, obj=None):
        return [] if obj is None else self.inlines  # файлы приходят только с сайта

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.source = "админка"
            obj.email_status = FormRequest.EmailStatus.NONE
            obj.channel = FormRequest.Channel.MANUAL
        super().save_model(request, obj, form, change)

    @admin.action(description="Отправить письмо ещё раз")
    def resend_email(self, request, queryset):
        # Сервис асинхронный, общий с API — через мост, см. core/bridge.py
        count = 0
        for form_request_id in queryset.values_list("id", flat=True):
            try:
                services.resend_request_email.sync(form_request_id)
                count += 1
            except HTTPException as exc:
                self.message_user(request, f"Заявка №{form_request_id}: письмо не отправлено. {exc.detail}", messages.ERROR)
        if count:
            self.message_user(request, f"Письма поставлены в очередь: {count}. Статус — в колонке «Письмо»")

    @admin.display(description="Метки")
    def utm_display(self, obj: FormRequest) -> str:
        return ", ".join(f"{key}: {value}" for key, value in obj.utm.items()) or "—"

    @admin.display(description="Браузер и устройство")
    def browser(self, obj: FormRequest) -> str:
        return describe_user_agent(obj.user_agent) or "—"

    @admin.display(description="Дополнительные поля")
    def data_display(self, obj: FormRequest) -> str:
        if not obj.data:
            return "—"
        return format_html("<pre>{}</pre>", json.dumps(obj.data, ensure_ascii=False, indent=2))

    def get_urls(self):
        # Раньше стандартных: иначе адрес примет за id заявки
        download = path("file/<uuid:file_id>/", self.admin_site.admin_view(self.download_file), name="form_formrequest_file")
        return [download, *super().get_urls()]

    def download_file(self, request, file_id):
        """Файл заявки — только тем, кто может смотреть заявки: файлы лежат вне media/ и наружу не отдаются."""
        if not self.has_view_permission(request):
            raise Http404
        form_file = FormFile.objects.filter(id=file_id).first()
        if form_file is None or not form_file.file:
            raise Http404
        return FileResponse(form_file.file.open("rb"), as_attachment=True, filename=form_file.original_name or None)

    # Django удаляет записи файлов, но не сами файлы — убираем и их
    def delete_model(self, request, obj):
        file_list = list(obj.formfile_set.all())
        super().delete_model(request, obj)
        services.delete_files(file_list)

    def delete_queryset(self, request, queryset):
        file_list = list(FormFile.objects.filter(form_request__in=queryset))
        super().delete_queryset(request, queryset)
        services.delete_files(file_list)
