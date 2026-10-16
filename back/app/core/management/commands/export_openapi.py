"""manage.py export_openapi — схема API (openapi.json) из кода, в stdout.

Из неё фронт собирает типы: `npm run api:types` во front/. Схема — из этого же коммита,
а не с сервера, где может стоять другая версия: правка API и типы фронта — одним коммитом.
База не нужна.
"""
import json

from django.core.management.base import BaseCommand

from project.api import create_app


class Command(BaseCommand):
    help = "Схема API (openapi.json) в stdout — из неё фронт собирает типы"

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(create_app().openapi(), ensure_ascii=False))
