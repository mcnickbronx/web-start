from django.test import SimpleTestCase

from core.slug import slugify_text


class SlugifyTextTest(SimpleTestCase):
    def test_cyrillic(self):
        """Кириллица — своим транслитом (ё → e, щ → sch), знаки и пробелы — один дефис."""
        self.assertEqual(slugify_text("Ёлка и щука — 2026!"), "elka-i-schuka-2026")
        self.assertEqual(slugify_text("Йод"), "yod")

    def test_alphabet(self):
        """Весь алфавит — каждая буква своим транслитом: правка словаря меняет адреса."""
        self.assertEqual(
            slugify_text("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
            "abvgdeezhziyklmnoprstufhcchshschyeyuya",
        )

    def test_empty(self):
        """Пустая строка и None — пустой слаг: модуль подставит свой запасной."""
        self.assertEqual(slugify_text(""), "")
        self.assertEqual(slugify_text(None), "")

    def test_length_max(self):
        """Обрезка по длине не оставляет дефиса на конце."""
        self.assertEqual(slugify_text("а" * 10 + " б", length_max=11), "a" * 10)
