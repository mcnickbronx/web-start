"""Telegram Bot API: простой текст, необязательные уведомления, безопасные ошибки."""
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from core import http
from core.env import env_str

TOKEN = env_str("TELEGRAM_TOKEN", "", is_secret=True)
PROXY = env_str("TELEGRAM_PROXY", "", is_secret=True)


def _check_proxy() -> None:
    if not PROXY:
        return
    try:
        parsed = urlsplit(PROXY)
        if parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port != 0 and not any(char.isspace() for char in PROXY):
            return
    except ValueError:
        pass
    raise ImproperlyConfigured("TELEGRAM_PROXY: нужен HTTP/HTTPS-прокси с адресом и допустимым портом") from None


_check_proxy()


async def send_message(chat_id: str | int, text: str) -> None:
    """Отправить простой текст. Нет токена — ничего; сбой — без URL, тела ответа и цепочки ошибок."""
    if not TOKEN:
        return
    if len(text) > 4096:
        text = text[:4095] + "…"
    try:
        result = await http.request_json(
            "POST", f"https://api.telegram.org/bot{TOKEN}/sendMessage", service="Telegram",
            json={"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}},
            proxy=PROXY or None,
        )
        if isinstance(result, dict) and result.get("ok") is True:
            return
    except Exception:
        # HTTP-клиент может включить token в URL и в текст ошибки. Не переносим ни то, ни другое.
        pass
    # Вне except: у безопасной ошибки нет даже скрытой цепочки с секретом.
    raise http.ExternalServiceError("Telegram", "не удалось отправить сообщение")
