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
