"""Настройки модуля «Пользователи» — константы: одинаково у всех сайтов. Ключ подписи токенов
JWT_SECRET_KEY — в .env, его читает settings.py рядом с SECRET_KEY Django.

Сроки и число попыток названы словами и в описаниях для Swagger (rest.py, schemas.py), и в readme
модуля и слоя user фронта: поменял здесь — найди поиском и поправь там.
"""
from datetime import timedelta

#: Access живёт в памяти вкладки, refresh — в куке httpOnly и продлевается при каждом
#: обновлении access: кто заходит, не вылетит через месяц
JWT_ACCESS_LIFETIME = timedelta(days=1)
JWT_REFRESH_LIFETIME = timedelta(days=30)

#: Коды подтверждения живут полчаса, новое письмо с кодом — не чаще раза в минуту.
#: После 5 неверных попыток код сгорает — иначе 6 цифр подбираются перебором
CONFIRMATION_CODE_LIFETIME = timedelta(minutes=30)
CONFIRMATION_CODE_RESEND_INTERVAL = timedelta(minutes=1)
CONFIRMATION_CODE_ATTEMPTS = 5
