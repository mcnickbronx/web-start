from django.apps import AppConfig


class UserConfig(AppConfig):
    name = "user"
    verbose_name = "Пользователи"

    def ready(self):
        from user import conf  # noqa: F401 — сроки из .env проверяются при запуске, а не с первым запросом API
