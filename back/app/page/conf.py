"""Настройки модуля «Страницы» — из .env проекта с префиксом PAGE_, нет строки — значение отсюда
(как устроено — core/env.py).
"""
from core.env import env_int

#: Картинки шире ужимаются до этой ширины и переводятся в webp
IMAGE_WIDTH_MAX = env_int("PAGE_IMAGE_WIDTH_MAX", 1600)
#: Картинка читается в память целиком — поэтому не больше 100 МБ
IMAGE_SIZE_MAX_MB = env_int("PAGE_IMAGE_SIZE_MAX_MB", 15, max_value=100)
