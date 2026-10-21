"""Настройки модуля «Пользователи».

Из .env проекта — сроки входа: кабинету клиента, CRM сотрудников и приложению подходят разные.
Без них — сутки и 30 дней. Остальное — константы, одинаково у всех сайтов. Ключ подписи токенов
JWT_SECRET_KEY — тоже в .env, его читает settings.py рядом с SECRET_KEY Django.

Сроки кодов названы словами и в описаниях для Swagger (rest.py, schemas.py), и в readme
модуля и слоя user фронта: поменял здесь — найди поиском и поправь там.
"""
from datetime import timedelta

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

#: Access живёт в памяти вкладки, refresh — в куке httpOnly и продлевается при каждом
#: обновлении access: кто заходит, не вылетит, пока не пропадёт дольше срока refresh
JWT_ACCESS_LIFETIME_HOURS = env.int("USER_JWT_ACCESS_LIFETIME_HOURS", default=24)
JWT_REFRESH_LIFETIME_DAYS = env.int("USER_JWT_REFRESH_LIFETIME_DAYS", default=30)
if JWT_ACCESS_LIFETIME_HOURS < 1 or JWT_REFRESH_LIFETIME_DAYS < 1:
    raise ImproperlyConfigured("USER_JWT_ACCESS_LIFETIME_HOURS и USER_JWT_REFRESH_LIFETIME_DAYS — не меньше 1")
JWT_ACCESS_LIFETIME = timedelta(hours=JWT_ACCESS_LIFETIME_HOURS)
JWT_REFRESH_LIFETIME = timedelta(days=JWT_REFRESH_LIFETIME_DAYS)

#: Коды подтверждения живут полчаса, новое письмо с кодом — не чаще раза в минуту.
#: После 5 неверных попыток код сгорает — иначе 6 цифр подбираются перебором
CONFIRMATION_CODE_LIFETIME = timedelta(minutes=30)
CONFIRMATION_CODE_RESEND_INTERVAL = timedelta(minutes=1)
CONFIRMATION_CODE_ATTEMPTS = 5
