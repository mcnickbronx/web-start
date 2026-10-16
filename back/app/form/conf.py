"""Настройки модуля «Заявки».

Из .env проекта — только капча: у сайтов разные ключи Яндекса. Остальное — константы:
одинаково у всех сайтов, а настройка в .env — это часть договора с сайтом, которую пришлось бы
поддерживать. Понадобится сайту своё значение — тогда и вынести в .env.
"""
from datetime import timedelta

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

#: Капча: numeric — пример с числами, работает без ключей; yandex — Яндекс SmartCaptcha
CAPTCHA_PROVIDER = env("FORM_CAPTCHA_PROVIDER", default="numeric")
SMARTCAPTCHA_SERVER_KEY = env("FORM_SMARTCAPTCHA_SERVER_KEY", default="")
#: Ключ для виджета на сайте — отдаётся фронту в описании формы
SMARTCAPTCHA_CLIENT_KEY = env("FORM_SMARTCAPTCHA_CLIENT_KEY", default="")

if CAPTCHA_PROVIDER not in ("numeric", "yandex"):
    raise ImproperlyConfigured(f"FORM_CAPTCHA_PROVIDER={CAPTCHA_PROVIDER}: допустимо numeric или yandex")
if CAPTCHA_PROVIDER == "yandex" and not (SMARTCAPTCHA_SERVER_KEY and SMARTCAPTCHA_CLIENT_KEY):
    raise ImproperlyConfigured("FORM_CAPTCHA_PROVIDER=yandex: нужны FORM_SMARTCAPTCHA_SERVER_KEY и FORM_SMARTCAPTCHA_CLIENT_KEY")

#: Сколько живёт открытая форма: токен из описания формы
TOKEN_LIFETIME = timedelta(minutes=120)
#: Форма отправлена быстрее — это бот (ловушка по времени). Сайт ждёт столько же сам: число
#: уходит ему в описании формы, чтобы человек, вставивший телефон из буфера, не попал в спам
FILL_SECONDS_MIN = 3

#: Файлы заявок — в закрытой папке, вне media/: media/ открыта всем по прямой ссылке
FILE_ROOT = settings.BASE_DIR.parent / "private" / "form"
FILE_EXTENSION_LIST = ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "xls", "xlsx"]
FILE_SIZE_MAX_MB = 10
#: Файлы, так и не приложенные к заявке, старше этого удаляет команда clear_form_files
FILE_ORPHAN_HOURS = 24
