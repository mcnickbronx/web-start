"""Настройки модулей из .env: значение по умолчанию — в conf.py модуля, своё — строкой в .env проекта.

Сайты работают на общем образе бэкенда и код поменять не могут — своё значение им задать
можно только через .env. Поэтому каждая настройка модуля читается так, по строке на настройку:

    IMAGE_WIDTH_MAX = env_int("PAGE_IMAGE_WIDTH_MAX", 1600)

Имя — с префиксом модуля. Неверное значение (не число, вне границ, пустой список) останавливает
запуск с понятной ошибкой: лучше не подняться, чем молча работать не так.
"""
import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()


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
    return value


def env_list(name: str, default: list[str]) -> list[str]:
    """Список через запятую из .env, строчными; нет строки — default."""
    value = [item.strip().lower() for item in env.list(name, default=default) if item.strip()]
    if not value:
        raise ImproperlyConfigured(f"{name}: пустой список")
    return value
