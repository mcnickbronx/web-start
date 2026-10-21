"""Админка с историей: правки в карточке и прямо в списке — в таблицу истории модели (core/history.py).

    class FormRequestAdmin(HistoryAdmin):
        history_fields = ["status"]

На странице записи появляется блок «История» — только чтение, новые сверху.
"""
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from core.history import diff


class HistoryInline(admin.TabularInline):
    fields = readonly_fields = ["date", "user", "changes_display"]
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True  # блок есть только на странице записи — его видит тот, кто видит запись

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")  # иначе на каждую строку — свой запрос за «кто»

    @admin.display(description="Что изменилось")
    def changes_display(self, obj):
        def label(field, value):
            return dict(field.flatchoices).get(value, value) if field and field.choices else value

        rows = []
        for name, values in obj.changes.items():
            try:
                field = self.parent_model._meta.get_field(name)
            except FieldDoesNotExist:
                field = None  # поле удалили или переименовали — старые строки под прежним именем, значения как есть
            title = field.verbose_name if field else name
            rows.append((title, "изменено" if values is None else f"{label(field, values[0])} → {label(field, values[1])}"))
        return format_html_join(mark_safe("<br>"), "{}: {}", rows)  # разделитель — разметка, имена и значения экранируются


class HistoryAdmin(admin.ModelAdmin):
    #: Поля, правки которых пишутся в историю
    history_fields: list[str] = []
    #: Из них — только факт изменения, без значений (телефон, email)
    history_hidden: list[str] = []

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        changed = [name for name in self.history_fields if name in form.changed_data]
        if change and changed:
            before = {name: form.initial.get(name) for name in changed}
            after = {name: obj._meta.get_field(name).value_from_object(obj) for name in changed}
            obj.history.create(user=request.user, changes=diff(before, after, self.history_hidden))

    def get_inline_instances(self, request, obj=None):
        instances = super().get_inline_instances(request, obj)
        if obj is not None:
            inline = type("HistoryInline", (HistoryInline,), {"model": self.model.history.rel.related_model})
            instances.append(inline(self.model, self.admin_site))
        return instances
