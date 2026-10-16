"""Отправка писем — механизмом Django (backend и SMTP настраиваются в .env).

Вызывать только из задач `tasks.py`: отправка идёт по сети, в эндпоинте она задержит
ответ, а упавший SMTP уронит основное действие.
"""
import asyncio

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _send(to: list[str], subject: str, html: str) -> None:
    message = EmailMultiAlternatives(subject, strip_tags(html), settings.DEFAULT_FROM_EMAIL, to)
    message.attach_alternative(html, "text/html")
    message.send()


async def send_mail(to: str | list[str], subject: str, template: str, context: dict) -> None:
    """Письмо по шаблону email/<template>.html из templates/ любого модуля. Текстовая версия — из того же HTML.

    Несколько получателей — одно письмо всем сразу, адреса видны друг другу."""
    context = {"site_name": settings.SITE_NAME, "site_url": settings.SITE_URL, **context}
    html = render_to_string(f"email/{template}.html", context)
    # SMTP-клиент Django синхронный — в потоке, чтобы не блокировать воркер
    await asyncio.to_thread(_send, [to] if isinstance(to, str) else to, subject, html)
