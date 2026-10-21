"""manage.py runserver — админка Django и API на одном порту (через project/asgi.py).

Подменяет стандартный runserver Django: имя то же, поведение другое. Стандартный поднял бы
только админку — про FastAPI он не знает. Из его флагов здесь есть только адрес:порт и --noreload.
Подмена держится на порядке INSTALLED_APPS: Django берёт команду из первого приложения, где она есть,
поэтому core стоит первым. Опустите core ниже django.contrib.staticfiles — молча вернётся стандартный.

Только для локальной разработки.

Запуск из back/app:
    python manage.py runserver                       # 127.0.0.1:8000
    python manage.py runserver 8001                  # другой порт
    python manage.py runserver 0.0.0.0:8000 --noreload
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
