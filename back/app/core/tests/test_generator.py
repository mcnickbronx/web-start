import io

from django.core.management import call_command
from django.test import SimpleTestCase


class GeneratedModelsTest(SimpleTestCase):
    def test_models_async_up_to_date(self):
        """models_async.py совпадают с моделями: иначе API работает против старой схемы."""
        call_command("sync_async_models", "--check", stdout=io.StringIO())
