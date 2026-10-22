from django.apps import AppConfig


class PageConfig(AppConfig):
    name = "page"
    verbose_name = "Страницы"

    def ready(self):
        from core import cache
        from page import conf  # noqa: F401 — настройки из .env проверяются при запуске, а не с первой загрузкой
        from page.models import PageCategory
        from page.services import CATEGORY_LIST_CACHE_KEY

        # Рубрику сохранили или удалили в админке — справочник на сайте сразу новый, а не через срок кэша
        cache.clear_on_change(PageCategory, CATEGORY_LIST_CACHE_KEY)
