from datetime import timedelta

from django.utils import timezone

from log.models import StatusLog


def clear_log(days: int) -> int:
    """Удаляет записи журнала старше `days` дней. Возвращает число удалённых."""
    border = timezone.now() - timedelta(days=days)
    deleted, _ = StatusLog.objects.filter(date_add__lt=border).delete()
    return deleted
