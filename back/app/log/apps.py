from django.apps import AppConfig


class LogConfig(AppConfig):
    name = "log"
    verbose_name = "Журнал"

    def ready(self):
        from log import conf  # noqa: F401 — настройки из .env проверяются при запуске, а не с первой уборкой
        # Слушатель очереди — один на процесс: API, админка, воркер, любая команда manage.py
        from log.handlers import start_listener

        start_listener()
