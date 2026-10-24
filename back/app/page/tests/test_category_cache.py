from django.test import override_settings
from django.urls import reverse

from core import cache
from core.tests.api import ApiTestCase
from page.models import PageCategory
from page.tests.create import create_page_category
from user.tests.create import create_user

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "page-category-cache"}}
# Порт 1 закрыт: соединение отклоняется сразу, как у остановленного Redis
REDIS_DOWN = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://127.0.0.1:1/0"}}


class CategoryListTest(ApiTestCase):
    def name_list(self) -> list[str]:
        response = self.api.get("/api/page/category/info")
        self.assertEqual(response.status_code, 200)
        return [item["name"] for item in response.json()]

    def test_order_from_admin(self):
        """Порядок — как в админке: по sort_order, а не по алфавиту."""
        create_page_category("Акции", sort_order=2)
        create_page_category("Новости", sort_order=1)
        create_page_category("Архив", is_active=False)
        self.assertEqual(self.name_list(), ["Новости", "Акции"])

    def test_no_cache_without_redis(self):
        """Без Redis (как в тестах) кэша нет: правка мимо save() видна сразу."""
        category = create_page_category("Новости")
        self.assertEqual(self.name_list(), ["Новости"])
        PageCategory.objects.filter(pk=category.pk).update(name="Статьи")
        self.assertEqual(self.name_list(), ["Статьи"])

    @override_settings(CACHES=REDIS_DOWN)
    def test_redis_down(self):
        """Redis не отвечает: справочник — из базы, сохранение рубрики не падает, в журнале предупреждения."""
        with self.assertLogs("core.cache", "WARNING") as logs:
            create_page_category("Новости")
            self.assertEqual(self.name_list(), ["Новости"])
        self.assertIn("Кэш не сброшен, page:category_list", logs.output[0])
        self.assertIn("Кэш не прочитан, page:category_list", logs.output[1])


@override_settings(CACHES=LOCMEM)
class CategoryListCacheTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        cache.backend().clear()

    def name_list(self) -> list[str]:
        return [item["name"] for item in self.api.get("/api/page/category/info").json()]

    def test_cached_until_saved(self):
        """Правка мимо save() (update) — справочник из кэша, прежний; сохранили, как админка, — сразу новый."""
        category = create_page_category("Новости")
        self.assertEqual(self.name_list(), ["Новости"])
        PageCategory.objects.filter(pk=category.pk).update(name="Статьи")
        self.assertEqual(self.name_list(), ["Новости"])
        category.name = "Блог"
        category.save()
        self.assertEqual(self.name_list(), ["Блог"])

    def test_cleared_on_add_hide_delete(self):
        """Новая, скрытая и удалённая в админке рубрика — справочник сразу новый."""
        news = create_page_category("Новости", sort_order=1)
        self.assertEqual(self.name_list(), ["Новости"])
        sale = create_page_category("Акции", sort_order=2)
        self.assertEqual(self.name_list(), ["Новости", "Акции"])
        sale.is_active = False
        sale.save()
        self.assertEqual(self.name_list(), ["Новости"])
        PageCategory.objects.filter(pk=news.pk).delete()  # «удалить выбранные» в админке
        self.assertEqual(self.name_list(), [])

    def test_cleared_on_move_in_admin(self):
        """Рубрику перенесли в другую в админке — справочник сразу новым деревом, а не через срок кэша."""
        news = create_page_category("Новости", sort_order=1)
        sale = create_page_category("Акции", sort_order=2)
        self.assertEqual(self.name_list(), ["Новости", "Акции"])
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        response = self.client.post(reverse("admin:page_pagecategory_change", args=[sale.pk]), {
            "name": sale.name, "parent": news.pk, "slug": sale.slug, "sort_order": sale.sort_order, "is_active": "on", "is_indexed": "on",
        })
        self.assertEqual(response.status_code, 302)
        tree = self.api.get("/api/page/category/info").json()
        self.assertEqual([(item["name"], [child["name"] for child in item["child_list"]]) for item in tree], [("Новости", ["Акции"])])
