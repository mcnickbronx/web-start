"""Настройки модулей из .env: значение по умолчанию — в conf.py модуля, своё — строкой в .env проекта.

Сайты работают на общем образе бэкенда и код поменять не могут — своё значение им задать
можно только через .env. Поэтому каждая настройка модуля читается так, по строке на настройку:

    IMAGE_WIDTH_MAX = env_int("PAGE_IMAGE_WIDTH_MAX", 1600)

Имя — с префиксом модуля. Неверное значение (не число, вне границ, не из списка, пустой список)
останавливает запуск с понятной ошибкой: лучше не подняться, чем молча работать не так.
Прочитанное запоминается в SETTING_LIST: что действует — `manage.py env_settings`, а тест следит,
что каждая настройка есть в шаблоне .env.txt.
"""
import os
from typing import NamedTuple

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()


class Setting(NamedTuple):
    name: str
    value: object
    default: object
    is_set: bool       # строка есть в .env
    is_secret: bool    # ключ: команда env_settings значение не показывает


#: Каждая настройка, прочитанная через env_int / env_list / env_str
SETTING_LIST: list[Setting] = []


def _remember(name: str, value, default, is_secret: bool = False):
    SETTING_LIST.append(Setting(name, value, default, name in os.environ, is_secret))
    return value


def env_int(name: str, default: int, min_value: int = 1, max_value: int | None = None) -> int:
    """Целое из .env; нет строки — default."""
    raw = env.str(name, default=str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"{name}={raw}: нужно целое число") from None
    if value < min_value or (max_value is not None and value > max_value):
        limit = f"от {min_value} до {max_value}" if max_value is not None else f"не меньше {min_value}"
        raise ImproperlyConfigured(f"{name}={value}: допустимо {limit}")
    return _remember(name, value, default)


def env_list(name: str, default: list[str]) -> list[str]:
    """Список через запятую из .env, строчными, без точки в начале (форматы пишут и как «.pdf»); нет строки — default."""
    value = [item.strip().lower().lstrip(".") for item in env.list(name, default=default) if item.strip(" .")]
    if not value:
        raise ImproperlyConfigured(f"{name}: пустой список")
    return _remember(name, value, default)


def env_str(name: str, default: str, choice_list: list[str] | None = None, is_secret: bool = False) -> str:
    """Строка из .env; нет строки — default. choice_list — допустимые значения, is_secret — ключ."""
    value = env.str(name, default=default).strip()
    if choice_list and value not in choice_list:
        raise ImproperlyConfigured(f"{name}={value}: допустимо {', '.join(choice_list)}")
    return _remember(name, value, default, is_secret)
