from datetime import timedelta

from django.utils import timezone

from core.tests.api import ApiTestCase
from page.tests.create import create_article, create_page, create_page_category, create_page_image


class PageApiTest(ApiTestCase):
    def test_feed_shows_only_visible_articles(self):
        create_article("На сайте")
        create_article("Черновик", is_published=False)
        create_article("Завтра", date_published=timezone.now() + timedelta(days=1))
        create_article("В скрытой рубрике", category=create_page_category("Архив", is_active=False))
        create_page("Контакты")  # отдельная страница, не статья — в ленту не попадает
        item_list = self.api.get("/api/page/list").json()["items"]
        self.assertEqual([(item["title"], item["path"]) for item in item_list], [("На сайте", "/novosti/na-sayte")])

    def test_feed_filter(self):
        """Рубрика и поиск — по заголовку и анонсу, без учёта регистра."""
        create_article("Цены на ремонт", excerpt="Сколько стоит")
        create_article("Отзыв клиента", excerpt="Ремонт кухни за неделю")
        category = create_page_category("Компания")
        create_article("Новый офис", category=category)
        title_list = lambda **params: [item["title"] for item in self.api.get("/api/page/list", params=params).json()["items"]]  # noqa: E731
        self.assertEqual(title_list(search="ремонт"), ["Отзыв клиента", "Цены на ремонт"])
        self.assertEqual(title_list(category_slug=category.slug), ["Новый офис"])

    def test_feed_page_too_far(self):
        """Огромный номер страницы — 422, а не 500: смещение не влезло бы в bigint базы."""
        self.assertEqual(self.api.get("/api/page/list", params={"page": 10**20}).status_code, 422)

    def test_feed_row_number_runs_through_pages(self):
        create_article("Первая")
        create_article("Вторая")
        item_list = self.api.get("/api/page/list", params={"page": 2, "row": 1}).json()["items"]
        self.assertEqual([item["row_number"] for item in item_list], [2])  # на второй странице — не с единицы

    def test_feed_same_date_keeps_order(self):
        """Статьи с одной датой — по id, новые первыми: страницы ленты не повторяют и не теряют статей."""
        date = timezone.now() - timedelta(days=1)
        for title in ("Первая", "Вторая", "Третья"):
            create_article(title, date_published=date)
        title_list = [self.api.get("/api/page/list", params={"page": page, "row": 1}).json()["items"][0]["title"] for page in (1, 2, 3)]
        self.assertEqual(title_list, ["Третья", "Вторая", "Первая"])

    def test_feed_sort(self):
        """Сортировка — только по разрешённым полям, минус — один: «--title» — 406, а не ошибка базы."""
        self.assertEqual(self.api.get("/api/page/list", params={"sort": "-title"}).status_code, 200)
        self.assertEqual(self.api.get("/api/page/list", params={"sort": "--title"}).status_code, 406)

    def test_cover_url(self):
        """Обложка — адресом от корня сайта, одинаково в ленте и в статье."""
        article = create_article(cover=create_page_image())
        cover = {"url": "/media/page/2026/10/oblozhka.webp", "alt": "Обложка"}
        self.assertEqual(self.api.get("/api/page/list").json()["items"][0]["cover"], cover)
        self.assertEqual(self.api.get(f"/api/page/detail/{article.slug}").json()["cover"], cover)

    def test_detail(self):
        create_article("Черновик", is_published=False)
        page = create_page()
        response = self.api.get(f"/api/page/detail/{page.slug}")
        self.assertIn("<strong>", response.json()["content_html"])  # Markdown собран в HTML при сохранении
        self.assertEqual(self.api.get("/api/page/detail/chernovik").json(), {"message": "Не найдено"})

    def test_resolve(self):
        category = create_page_category()
        article = create_article()
        page = create_page()
        resolve = lambda slug: self.api.get(f"/api/page/resolve/{slug}").json()["type"]  # noqa: E731
        self.assertEqual(resolve(category.slug), "category")
        self.assertEqual(resolve(page.slug), "page")
        self.assertEqual(resolve(article.slug), "none")  # статья живёт по адресу /рубрика/статья
        self.assertEqual(resolve("net-takoy"), "none")

    def test_sitemap_skips_hidden_from_search(self):
        create_article("Для поиска")
        create_article("Не для поиска", is_indexed=False)
        loc_list = [item["loc"] for item in self.api.get("/api/page/sitemap").json()["items"]]
        self.assertEqual(loc_list, ["/novosti", "/novosti/dlya-poiska"])
