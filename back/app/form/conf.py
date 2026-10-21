"""Настройки модуля «Заявки» — из .env проекта с префиксом FORM_, нет строки — значение отсюда
(как устроено — core/env.py). В коде только папка файлов: она связана с томом ./private в compose.yml,
другой путь из .env увёл бы файлы мимо тома, и они пропали бы при пересоздании контейнера.
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.env import env_int, env_list, env_str

#: Капча: numeric — пример с числами, работает без ключей; yandex — Яндекс SmartCaptcha
CAPTCHA_PROVIDER = env_str("FORM_CAPTCHA_PROVIDER", "numeric", choice_list=["numeric", "yandex"])
SMARTCAPTCHA_SERVER_KEY = env_str("FORM_SMARTCAPTCHA_SERVER_KEY", "", is_secret=True)
#: Ключ для виджета на сайте — отдаётся фронту в описании формы
SMARTCAPTCHA_CLIENT_KEY = env_str("FORM_SMARTCAPTCHA_CLIENT_KEY", "", is_secret=True)

if CAPTCHA_PROVIDER == "yandex" and not (SMARTCAPTCHA_SERVER_KEY and SMARTCAPTCHA_CLIENT_KEY):
    raise ImproperlyConfigured("FORM_CAPTCHA_PROVIDER=yandex: нужны FORM_SMARTCAPTCHA_SERVER_KEY и FORM_SMARTCAPTCHA_CLIENT_KEY")

#: Сколько живёт открытая форма: токен из описания формы
TOKEN_LIFETIME = timedelta(minutes=env_int("FORM_TOKEN_LIFETIME_MINUTES", 120))
#: Форма отправлена быстрее — это бот (ловушка по времени), 0 — ловушки нет. Сайт ждёт столько же сам:
#: число уходит ему в описании формы, чтобы человек, вставивший телефон из буфера, не попал в спам.
#: Не больше минуты: 3000 «в миллисекундах» заставило бы сайт ждать, пока форма устареет
FILL_SECONDS_MIN = env_int("FORM_FILL_SECONDS_MIN", 3, min_value=0, max_value=60)

#: Файлы заявок — в закрытой папке, вне media/: media/ открыта всем по прямой ссылке
FILE_ROOT = settings.BASE_DIR.parent / "private" / "form"
#: Форматы и размер проверяет бэкенд, ошибка называет их посетителю
FILE_EXTENSION_LIST = env_list("FORM_FILE_EXTENSION_LIST", ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "xls", "xlsx"])
#: Файл читается в память целиком, а у контейнера лимит памяти (compose.yml) — поэтому не больше 50 МБ
FILE_SIZE_MAX_MB = env_int("FORM_FILE_SIZE_MAX_MB", 10, max_value=50)
#: Файлы, так и не приложенные к заявке, старше этого удаляет команда clear_form_files
FILE_ORPHAN_HOURS = env_int("FORM_FILE_ORPHAN_HOURS", 24)
# Уборка раньше конца жизни формы удалила бы файлы, которые посетитель ещё приложит
if timedelta(hours=FILE_ORPHAN_HOURS) < TOKEN_LIFETIME:
    raise ImproperlyConfigured(
        f"FORM_FILE_ORPHAN_HOURS={FILE_ORPHAN_HOURS}: не меньше срока формы FORM_TOKEN_LIFETIME_MINUTES={TOKEN_LIFETIME.total_seconds() // 60:.0f}"
    )
# Ждать дольше, чем живёт форма, — заявка не уйдёт никогда
if timedelta(seconds=FILL_SECONDS_MIN) >= TOKEN_LIFETIME:
    raise ImproperlyConfigured("FORM_FILL_SECONDS_MIN: меньше срока формы FORM_TOKEN_LIFETIME_MINUTES")
