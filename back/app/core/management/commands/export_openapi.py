"""manage.py export_openapi — схема API (openapi.json) из кода, в stdout.

Из неё фронт собирает типы: `npm run api:types` во front/. Схема — из этого же коммита,
а не с сервера, где может стоять другая версия: правка API и типы фронта — одним коммитом.
База не нужна.

Обычно руками не запускается: её вызывает `npm run api:types` (front/package.json).
Посмотреть схему проще в Swagger — /api/docs на runserver. Вручную, из back/app
(JSON одной строкой; не в папку проекта — файл попадёт в git):
    python manage.py export_openapi > /tmp/openapi.json
"""
import json

from django.core.management.base import BaseCommand

from project.api import create_app


class Command(BaseCommand):
    help = "Схема API (openapi.json) в stdout — из неё фронт собирает типы"

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(create_app().openapi(), ensure_ascii=False))
