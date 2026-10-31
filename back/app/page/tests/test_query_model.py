"""Лента page: рабочий пример фильтров и одновременные ошибки параметров."""
from datetime import UTC, datetime

from core.tests.api import ApiTestCase
from page.tests.create import create_article, create_page, create_page_category


class PageQueryModelTest(ApiTestCase):
    def test_typo_and_invalid_page_together(self):
        response = self.api.get("/api/page/list?serch=ремонт&page=abc")
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual({item["loc"]: item["type"] for item in body["full_error"]}, {"page": "int_parsing", "serch": "extra_forbidden"})
        self.assertEqual(body["message"], "; ".join(item["msg"] for item in body["full_error"]))

    def test_news_search_first_ten_published_articles(self):
        news = create_page_category("Новости", slug="news")
        other = create_page_category("Другое", slug="other")
        expected = []
        for number in range(12):
            article = create_article(
                "Ремонт" if number % 2 else "Советы", category=news,
                excerpt="Советы" if number % 2 else "Ремонт своими руками",
                date_published=datetime(2026, 1, number + 1, tzinfo=UTC),
            )
            expected.append(article.id)
        create_article("Ремонт", category=other)
        create_article("Ремонт", category=news, is_published=False)
        create_article("Ремонт", category=news, date_published=datetime(2099, 1, 1, tzinfo=UTC))
        create_article("Иная тема", category=news, excerpt="Иной анонс")
        create_page("Ремонт без рубрики")
        response = self.api.get("/api/page/list?category_slug=news&search=ремонт&page=1&row=10")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], {"count": 12})
        self.assertEqual([item["id"] for item in body["items"]], list(reversed(expected))[:10])
        self.assertEqual([item["row_number"] for item in body["items"]], list(range(1, 11)))
        self.assertTrue(all(item["category"]["slug"] == "news" for item in body["items"]))
