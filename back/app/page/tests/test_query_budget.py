from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.utils import timezone
from tortoise.backends.asyncpg.client import AsyncpgDBClient

from core.tests.api import ApiTestCase
from page.tests.create import create_article, create_page_category, create_page_image


class PageQueryBudgetTest(ApiTestCase):
    def test_feed_query_budget(self):
        """Рубрики и обложки не добавляют SQL на каждую статью ленты."""
        article_list = []
        date_published = timezone.now() - timedelta(days=1)
        for number in range(20):
            category = create_page_category(f"Рубрика {number}")
            cover = create_page_image(file=f"page/budget-{number}.webp", alt=f"Обложка {number}")
            article_list.append(create_article(
                f"Статья {number}", category=category, cover=cover, date_published=date_published,
            ))
        article_list.reverse()  # при равной дате лента отдаёт новые id первыми

        # В Tortoise 1.1.9 оба метода asyncpg сами выполняют SQL, без делегирования друг другу.
        # Оборачиваем настоящие методы: база, результаты и исключения остаются настоящими.
        execute_query = AsyncpgDBClient.execute_query
        execute_query_dict = AsyncpgDBClient.execute_query_dict
        for row in (1, 20):
            with self.subTest(row=row):
                query_list = []

                async def counted_query(client, query, *args, **kwargs):
                    query_list.append(query)
                    return await execute_query(client, query, *args, **kwargs)

                async def counted_query_dict(client, query, *args, **kwargs):
                    query_list.append(query)
                    return await execute_query_dict(client, query, *args, **kwargs)

                # Запуск приложения и подготовка данных уже закончены; считаем только HTTP-запрос.
                with patch.object(AsyncpgDBClient, "execute_query", counted_query), \
                        patch.object(AsyncpgDBClient, "execute_query_dict", counted_query_dict):
                    response = self.api.get("/api/page/list", params={"row": row})

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["total"]["count"], 20)
                self.assertEqual(len(data["items"]), row)
                for item, article in zip(data["items"], article_list[:row], strict=True):
                    self.assertEqual(item["id"], article.id)
                    self.assertEqual(item["title"], article.title)
                    self.assertEqual(item["category"], {
                        "id": article.category.id, "name": article.category.name,
                        "slug": article.category.slug, "path": f"/{article.category.slug}",
                    })
                    self.assertEqual(item["cover"], {
                        "url": f"{settings.MEDIA_URL}{article.cover.file.name}", "alt": article.cover.alt,
                    })
                self.assertLessEqual(len(query_list), 2, f"Лента row={row}: выполнено {len(query_list)} SQL, бюджет — 2")
