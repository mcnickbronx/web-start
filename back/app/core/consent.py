"""Проверка явно переданного согласия; хранение остаётся у вызывающего модуля."""
from datetime import datetime
from ipaddress import ip_address

from django.utils import timezone

from core.errors import field_error


def consent_stamp(consent: bool, required: bool, ip: str | None) -> tuple[datetime | None, str | None]:
    """Только настоящий True означает факт; отсутствие IP не отменяет согласие."""
    if consent is not True:
        if required:
            raise field_error({"consent": "Подтвердите согласие"})
        return None, None
    try:
        client_ip = str(ip_address(ip)) if ip else None
    except ValueError:
        client_ip = None
    return timezone.now(), client_ip
