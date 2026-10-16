"""Капча формы. Способ — настройка FORM_CAPTCHA_PROVIDER.

numeric — пример на сложение. Работает без ключей и внешних сервисов, но защищает только
от ботов, которые не разбирают форму: вопрос приходит текстом. Ответ в токене формы
не лежит — только его хеш с ключом проекта, иначе бот прочитал бы ответ из токена.

yandex — Яндекс SmartCaptcha: виджет на сайте выдаёт токен, бэкенд проверяет его
у Яндекса. Если Яндекс недоступен, заявка проходит: так советует Яндекс.
"""
import logging
import secrets

import aiohttp
from django.utils.crypto import constant_time_compare, salted_hmac

from form import conf

logger = logging.getLogger(__name__)

SMARTCAPTCHA_URL = "https://smartcaptcha.cloud.yandex.ru/validate"


def answer_hash(token_id: str, answer: str) -> str:
    """Хеш ответа, привязанный к токену: один и тот же ответ в разных формах даёт разный хеш."""
    return salted_hmac("form.captcha", f"{token_id}:{answer.strip()}").hexdigest()


def create_question(token_id: str) -> tuple[str, str]:
    """(вопрос для человека, хеш ответа для токена)."""
    left, right = secrets.randbelow(40) + 10, secrets.randbelow(9) + 1
    return f"{left} + {right}", answer_hash(token_id, str(left + right))


def check_numeric(token_id: str, expected_hash: str, answer: str) -> bool:
    return constant_time_compare(answer_hash(token_id, answer or ""), expected_hash)


async def check_yandex(captcha_token: str, ip: str) -> bool:
    """Токен виджета SmartCaptcha — у Яндекса.

    Нет связи или ответ не 200 — заявка проходит: так советует Яндекс, чтобы сбой капчи
    не стоил заявки. 403 — неверный ключ сервера: капча фактически не работает, поэтому
    в журнал — ошибка с ответом Яндекса, а не «не ответила».
    """
    if not captcha_token:
        return False
    data = {"secret": conf.SMARTCAPTCHA_SERVER_KEY, "token": captcha_token, "ip": ip}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(SMARTCAPTCHA_URL, data=data) as response:
                if response.status == 200:
                    return (await response.json(content_type=None)).get("status") == "ok"
                status, text = response.status, (await response.text())[:500]
    except Exception:
        logger.warning("SmartCaptcha не ответила, заявка пропущена", exc_info=True)
        return True
    log = logger.error if status == 403 else logger.warning
    log(f"SmartCaptcha ответила {status}: {text} — заявка пропущена")
    return True
