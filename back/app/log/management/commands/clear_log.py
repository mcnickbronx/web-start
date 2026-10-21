"""manage.py clear_log [--days N] — убрать старые записи журнала, по умолчанию старше LOG_KEEP_DAYS.

Журнал растёт без ограничения, уборку ставят в cron на сервере (см. app/log/readme.md).
"""
from django.core.management.base import BaseCommand

from log import conf
from log.services import clear_log


class Command(BaseCommand):
    help = "Удалить записи журнала старше указанного числа дней"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=conf.KEEP_DAYS, help="Сколько дней хранить (по умолчанию LOG_KEEP_DAYS из .env, без него 90)")

    def handle(self, *args, **options):
        deleted = clear_log(options["days"])
        self.stdout.write(f"Удалено записей: {deleted}")
