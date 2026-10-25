from django.core.exceptions import ValidationError
from django.test import TestCase

from page import services
from page.models import Page
from page.tests.create import create_page, create_page_category


class SlugTest(TestCase):
    def test_slug_unique_across_categories_and_pages(self):
        """Рубрики и страницы делят корень сайта: одинаковое название — следующий номер."""
        create_page_category("Новости")
        self.assertEqual(create_page("Новости").slug, "novosti-2")

    def test_reserved_slug(self):
        with self.assertRaisesMessage(ValidationError, "Адрес /admin занят самим сайтом"):
            services.clean_slug(Page, "admin", "", None)

    def test_long_title_twice(self):
        """Вторая страница с тем же длинным заголовком сохраняется: суффикс -2 входит в 200 знаков поля, а не дописывается сверх."""
        title = "Медосмотр " * 25
        self.assertEqual(len(create_page(title).slug), 199)
        slug = create_page(title).slug
        self.assertEqual(len(slug), 200)
        self.assertTrue(slug.endswith("medosmot-2"))

    def test_reserved_slug_from_title(self):
        """Заголовок «Admin» — адрес служебный, страница получает следующий номер."""
        self.assertEqual(create_page("Admin").slug, "admin-2")

    def test_title_without_letters(self):
        """Из заголовка без букв и цифр слага не выйдет — запасной «page», дальше по номерам."""
        self.assertEqual(create_page("!!!").slug, "page")
        self.assertEqual(create_page("???").slug, "page-2")
