from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.tests.api import ApiTestCase
from page import services
from page.models import PageRedirect
from page.tests.create import create_article, create_page_category
from user.tests.create import create_user


def redirect_map() -> dict[str, str]:
    return dict(PageRedirect.objects.values_list("path_from", "path_to"))


class RedirectTest(TestCase):
    def test_clean_path(self):
        """Адрес из админки и адрес от сайта — к одному виду: путь без домена, параметров, «/» в конце и процентов."""
        self.assertEqual(services.clean_path(" https://old.example.ru/news/2019/item.html?id=5 "), "/news/2019/item.html")
        self.assertEqual(services.clean_path("news/item/"), "/news/item")
        self.assertEqual(services.clean_path("/%D0%BD%D0%BE%D0%B2%D0%BE%D1%81%D1%82%D0%B8/"), "/новости")
        self.assertEqual(services.clean_path("/"), "/")

    def test_no_chains_and_loops(self):
        """Адрес менялся дважды — оба старых ведут сразу на последний; вернули прежний — по кругу не водит."""
        services.save_redirect("/a", "/b")
        services.save_redirect("/b", "/c")
        self.assertEqual(redirect_map(), {"/a": "/c", "/b": "/c"})
        services.save_redirect("/c", "/a")
        self.assertEqual(redirect_map(), {"/b": "/a", "/c": "/a"})

    def test_manual_redirect_to_redirected_path(self):
        services.save_redirect("/a", "/b")
        with self.assertRaisesMessage(ValidationError, "С адреса /a уже есть редирект на /b"):
            services.check_redirect("/c", "/a", None)


class RedirectAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))

    def save_page(self, page, slug: str):
        data = {
            "title": page.title, "slug": slug, "category": page.category_id or "", "excerpt": page.excerpt,
            "content_md": page.content_md, "is_indexed": "on", **({"is_published": "on"} if page.is_published else {}),
        }
        response = self.client.post(reverse("admin:page_page_change", args=[page.pk]), data)
        self.assertEqual(response.status_code, 302)  # сохранилось, а не вернулось с ошибками формы

    def test_slug_change_keeps_old_path(self):
        """Сменили слаг опубликованной статьи — старый адрес ведёт на новый. Черновик ещё нигде не стоит — его нет."""
        self.save_page(create_article("Цены"), "ceny-2026")
        self.save_page(create_article("Черновик", is_published=False), "chernovik-2")
        self.assertEqual(redirect_map(), {"/novosti/ceny": "/novosti/ceny-2026"})

    def test_category_slug_change_keeps_old_path(self):
        category = create_page_category("Новости")
        response = self.client.post(reverse("admin:page_pagecategory_change", args=[category.pk]), {
            "name": category.name, "slug": "news", "sort_order": 100, "is_active": "on", "is_indexed": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(redirect_map(), {"/novosti": "/news"})

    def test_manual_redirect_saves_paths(self):
        """Ссылку со старого сайта можно вставить целиком — сохранится путь."""
        response = self.client.post(reverse("admin:page_pageredirect_add"), {
            "path_from": "https://old.example.ru/news/1.html?id=1", "path_to": "/novosti/",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(redirect_map(), {"/news/1.html": "/novosti"})


class RedirectApiTest(ApiTestCase):
    def test_redirect(self):
        """Сайт передаёт адрес как пришёл: с «/» в конце, кириллица процентами."""
        PageRedirect.objects.create(path_from="/новости/старая", path_to="/novosti/novaya")
        path = "/%D0%BD%D0%BE%D0%B2%D0%BE%D1%81%D1%82%D0%B8/%D1%81%D1%82%D0%B0%D1%80%D0%B0%D1%8F/"
        self.assertEqual(self.api.get("/api/page/redirect", params={"path": path}).json(), {"path_to": "/novosti/novaya"})
        self.assertEqual(self.api.get("/api/page/redirect", params={"path": "/net-takogo"}).status_code, 404)
