"""manage.py clear_form_files — убрать файлы, которые загрузили с сайта, но так и не приложили к заявке.

На сервере её запускают раз в сутки (см. app/form/readme.md).
"""
from django.core.management.base import BaseCommand

from form import conf
from form.services import clear_orphan_files


class Command(BaseCommand):
    help = "Удалить файлы, которые загрузили с сайта, но так и не приложили к заявке"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=conf.FILE_ORPHAN_HOURS, help="Старше скольких часов удалять")

    def handle(self, *args, **options):
        count = clear_orphan_files(options["hours"])
        self.stdout.write(f"Удалено файлов: {count}")
