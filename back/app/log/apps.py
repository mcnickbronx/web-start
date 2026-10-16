from django.apps import AppConfig


class LogConfig(AppConfig):
    name = "log"
    verbose_name = "Журнал"

    def ready(self):
        # Слушатель очереди — один на процесс: API, админка, воркер, любая команда manage.py
        from log.handlers import start_listener

        start_listener()
