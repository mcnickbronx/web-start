"""Настройки модуля «Пользователи» — из .env проекта с префиксом USER_, нет строки — значение отсюда
(как устроено — core/env.py). Ключ подписи токенов JWT_SECRET_KEY — тоже в .env, его читает settings.py
рядом с SECRET_KEY Django.

Читается при запуске Django (apps.py): неверное значение в .env остановит и manage.py, и выкладку
до миграций, а не только API.
"""
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

from core.env import env_int

#: Access живёт в памяти вкладки, refresh — в куке httpOnly и продлевается при каждом
#: обновлении access: кто заходит, не вылетит, пока не пропадёт дольше срока refresh
JWT_ACCESS_LIFETIME = timedelta(hours=env_int("USER_JWT_ACCESS_LIFETIME_HOURS", 24))
JWT_REFRESH_LIFETIME = timedelta(days=env_int("USER_JWT_REFRESH_LIFETIME_DAYS", 30))
# access длиннее refresh бессмысленен: сессию, которую не продлевали дольше срока refresh,
# уберёт следующий вход, и живой access перестанет работать
if JWT_ACCESS_LIFETIME > JWT_REFRESH_LIFETIME:
    raise ImproperlyConfigured("USER_JWT_ACCESS_LIFETIME_HOURS: access не длиннее refresh (USER_JWT_REFRESH_LIFETIME_DAYS)")

#: Код подтверждения живёт полчаса, новое письмо с кодом — не чаще раза в минуту
CONFIRMATION_CODE_LIFETIME = timedelta(minutes=env_int("USER_CONFIRMATION_CODE_LIFETIME_MINUTES", 30))
CONFIRMATION_CODE_RESEND_INTERVAL = timedelta(seconds=env_int("USER_CONFIRMATION_CODE_RESEND_SECONDS", 60))
#: После 5 неверных попыток код сгорает — иначе 6 цифр подбираются перебором. Больше 10 не дать:
#: опечатка вроде 500 молча сняла бы защиту
CONFIRMATION_CODE_ATTEMPTS = env_int("USER_CONFIRMATION_CODE_ATTEMPTS", 5, max_value=10)
