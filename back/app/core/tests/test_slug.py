from django.test import SimpleTestCase

from core.slug import slugify_text, unique_slug


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


class UniqueSlugTest(SimpleTestCase):
    def test_suffix_fits_length(self):
        """База во весь предел занята — суффикс входит в предел, а не дописывается сверх: ровно 200 знаков."""
        taken = {"a" * 200}
        self.assertEqual(unique_slug("a" * 250, taken.__contains__), "a" * 198 + "-2")
        taken |= {"a" * 198 + f"-{counter}" for counter in range(2, 10)}
        self.assertEqual(unique_slug("a" * 250, taken.__contains__), "a" * 197 + "-10")

    def test_fallback_and_counter(self):
        """Текст без букв и цифр — запасной слаг; занят — следующий свободный номер."""
        self.assertEqual(unique_slug("", lambda slug: False), "item")
        self.assertEqual(unique_slug("!!!", lambda slug: False, fallback="product"), "product")
        taken = {"item", "item-2"}
        self.assertEqual(unique_slug("!!!", taken.__contains__), "item-3")

    def test_no_double_hyphen(self):
        """На месте среза под суффикс — дефис: он не удваивается."""
        taken = {"aaaaaaa-bb"}
        self.assertEqual(unique_slug("aaaaaaa bb", taken.__contains__, length_max=10), "aaaaaaa-2")
