from django.apps import AppConfig


class FormConfig(AppConfig):
    name = "form"
    verbose_name = "Заявки"

    def ready(self):
        from core import telegram  # noqa: F401 — настройки проверяются при запуске
