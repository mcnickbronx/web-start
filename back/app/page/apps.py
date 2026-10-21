from django.apps import AppConfig


class PageConfig(AppConfig):
    name = "page"
    verbose_name = "Страницы"

    def ready(self):
        from page import conf  # noqa: F401 — настройки из .env проверяются при запуске, а не с первой загрузкой
