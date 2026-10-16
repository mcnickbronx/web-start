"""manage.py runserver — админка Django и API на одном порту (через project/asgi.py).

Перекрывает стандартный runserver: у него нет FastAPI. Только для локальной разработки.
"""
import uvicorn
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Локальный сервер: /admin — Django, /api — FastAPI (Swagger: /api/docs)"

    def add_arguments(self, parser):
        parser.add_argument("addrport", nargs="?", default="127.0.0.1:8000", help="Порт или адрес:порт")
        parser.add_argument("--noreload", action="store_true", help="Без автоперезагрузки при изменении кода")

    def handle(self, *args, **options):
        host, _, port = options["addrport"].rpartition(":")
        uvicorn.run(
            "project.asgi:application",
            host=host or "127.0.0.1",
            port=int(port),
            app_dir=str(settings.BASE_DIR),
            reload=not options["noreload"],
            reload_dirs=[str(settings.BASE_DIR)],
            reload_includes=["*.py", "*.html"],
        )
