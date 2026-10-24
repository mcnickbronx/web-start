from django.test import TestCase
from django.urls import reverse

from core.tests.api import ApiTestCase
from page.models import PageCategory
from page.tests.create import create_article, create_page_category
from user.tests.create import create_user


class CategoryTreeApiTest(ApiTestCase):
    def category_info(self) -> list[dict]:
        response = self.api.get("/api/page/category/info")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_tree(self):
        """Подрубрики — в child_list родителя, на каждом уровне по sort_order; в ответе только поля схемы,
        без parent_id и sort_order; у рубрики без подрубрик — пустой child_list."""
        news = create_page_category("Новости", sort_order=1)
        city = create_page_category("Город", parent=news, sort_order=2)
        sale = create_page_category("Акции", parent=news, sort_order=1)
        article = create_page_category("Статьи", sort_order=2)
        node = lambda category, child_list: {  # noqa: E731
            "id": category.id, "name": category.name, "slug": category.slug, "path": f"/{category.slug}", "child_list": child_list,
        }
        self.assertEqual(self.category_info(), [
            node(news, [node(sale, []), node(city, [])]),
            node(article, []),
        ])

    def test_equal_sort_order_by_name(self):
        """Порядок у равных sort_order — по названию, как в списке админки, а не по времени создания."""
        create_page_category("Новости")
        create_page_category("Акции")
        self.assertEqual([item["name"] for item in self.category_info()], ["Акции", "Новости"])

    def test_child_of_hidden_in_root(self):
        """Подрубрика скрытой рубрики остаётся на сайте — в корне, а скрытой нет нигде."""
        archive = create_page_category("Архив", is_active=False)
        create_page_category("2019", parent=archive)
        self.assertEqual([(item["name"], item["child_list"]) for item in self.category_info()], [("2019", [])])

    def test_feed_of_parent_without_children(self):
        """Лента рубрики — только её статьи: статьи подрубрик в неё не попадают."""
        news = create_page_category("Новости")
        create_article("Открыли офис", category=news)
        create_article("Скидки в октябре", category=create_page_category("Акции", parent=news))
        item_list = self.api.get("/api/page/list", params={"category_slug": news.slug}).json()["items"]
        self.assertEqual([item["title"] for item in item_list], ["Открыли офис"])


class CategoryParentAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))

    def save_category(self, category: PageCategory, parent: PageCategory):
        """Сохранить рубрику в админке с новым родителем. Id в запросе — строкой, как из настоящей формы."""
        return self.client.post(reverse("admin:page_pagecategory_change", args=[category.pk]), {
            "name": category.name, "parent": str(parent.pk), "slug": category.slug, "sort_order": category.sort_order,
            "is_active": "on", "is_indexed": "on",
        })

    def assert_cycle_refused(self, category: PageCategory, parent: PageCategory):
        response = self.save_category(category, parent)
        self.assertEqual(response.status_code, 200)  # вернулась форма с ошибкой, а не сохранилось
        self.assertEqual(response.context["adminform"].form.errors["parent"], ["Нельзя вложить рубрику в саму себя или в её подрубрику"])
        category.refresh_from_db()
        self.assertNotEqual(category.parent_id, parent.pk)

    def test_into_itself(self):
        news = create_page_category("Новости")
        self.assert_cycle_refused(news, news)

    def test_into_own_descendant(self):
        """В подрубрику своей подрубрики — тоже нельзя: ветка замкнулась бы в цикл и пропала с сайта."""
        news = create_page_category("Новости")
        city = create_page_category("Город", parent=news)
        district = create_page_category("Район", parent=city)
        self.assert_cycle_refused(news, city)
        self.assert_cycle_refused(news, district)

    def test_into_other_branch(self):
        """В соседнюю ветку — можно: в цикл это не замыкает."""
        news = create_page_category("Новости")
        city = create_page_category("Город", parent=news)
        article = create_page_category("Статьи")
        self.assertEqual(self.save_category(city, article).status_code, 302)
        city.refresh_from_db()
        self.assertEqual(city.parent_id, article.pk)
