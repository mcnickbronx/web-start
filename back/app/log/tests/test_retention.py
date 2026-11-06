"""Граница удаления журнала: точное время, включая микросекунды."""
from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from log.models import StatusLog


class LogRetentionTest(TestCase):
    def test_command_keeps_exact_cutoff_and_newer_rows(self):
        now = datetime(2026, 11, 7, 1, 0, tzinfo=UTC)  # 04:00 в Europe/Moscow.
        cutoff = now - timedelta(days=90)
        for name, delta in [("before", -1), ("at", 0), ("after", 1)]:
            row = StatusLog.objects.create(logger_name="form", msg=name)
            StatusLog.objects.filter(pk=row.pk).update(date_add=cutoff + timedelta(microseconds=delta))
        out = StringIO()
        with patch("log.services.timezone.now", return_value=now):
            call_command("clear_log", days=90, stdout=out)
        self.assertEqual(set(StatusLog.objects.values_list("msg", flat=True)), {"at", "after"})
        self.assertIn("Удалено записей: 1", out.getvalue())
