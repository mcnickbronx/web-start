"""manage.py clear_log --days 90 — убрать старые записи журнала.

Журнал растёт без ограничения, уборку ставят в cron на сервере (см. app/log/readme.md).
"""
from django.core.management.base import BaseCommand

from log.services import clear_log


class Command(BaseCommand):
    help = "Удалить записи журнала старше указанного числа дней"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="Сколько дней хранить (по умолчанию 90)")

    def handle(self, *args, **options):
        deleted = clear_log(options["days"])
        self.stdout.write(f"Удалено записей: {deleted}")
