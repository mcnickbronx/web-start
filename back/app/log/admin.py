from django.contrib import admin

from log.models import StatusLog


@admin.register(StatusLog)
class StatusLogAdmin(admin.ModelAdmin):
    list_display = ["date_add", "level", "logger_name", "message_short"]
    list_filter = ["level", "logger_name"]
    search_fields = ["msg", "trace"]
    readonly_fields = ["date_add", "level", "logger_name", "msg", "trace"]
    date_hierarchy = "date_add"

    @admin.display(description="Сообщение")
    def message_short(self, obj: StatusLog) -> str:
        return obj.msg[:120]

    def has_add_permission(self, request) -> bool:
        return False   # записи создаёт только хендлер logging

    def has_change_permission(self, request, obj=None) -> bool:
        return False   # журнал, который можно править, журналом не является
