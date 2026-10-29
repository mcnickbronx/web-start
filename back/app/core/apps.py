from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Ядро"

    def ready(self):
        from core import ai  # настройки проверяются при запуске, видны в env_settings
