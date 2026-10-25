"""Слаг из текста — одинаковые адреса во всех модулях."""
import re
from collections.abc import Callable

# Транслит для слагов. Свой словарь: предсказуемый адрес и никаких сюрпризов при обновлении библиотеки
TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify_text(value: str, length_max: int = 200) -> str:
    """Строка → слаг: транслит кириллицы, латиница, цифры и дефис."""
    value = "".join(TRANSLIT_MAP.get(char, char) for char in (value or "").strip().lower())
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:length_max].strip("-")


def unique_slug(source: str, is_taken: Callable[[str], bool], fallback: str = "item", length_max: int = 200) -> str:
    """Свободный слаг из текста: занят — с суффиксом -2, -3…; вместе с суффиксом не длиннее `length_max`
    (предел поля слага), иначе второй записи с длинным названием база не даст сохраниться.

    `is_taken(slug)` — занят ли адрес; решает модуль: своя таблица, соседние, зарезервированные адреса.
    Текст без букв и цифр — `fallback`. Функция обычная, не `async`: её зовут админка и Django ORM.
    """
    base = slugify_text(source, length_max) or fallback
    candidate, counter = base, 1
    while is_taken(candidate):
        counter += 1
        suffix = f"-{counter}"
        candidate = base[:length_max - len(suffix)].rstrip("-") + suffix
    return candidate
