from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class ModulesTest(SimpleTestCase):
    def test_local_apps_have_test_package(self):
        """Подключённые локальные модули не теряют tests из общего прогона; содержимое тестов не проверяем."""
        base = Path(settings.BASE_DIR).resolve()
        for config in apps.get_app_configs():
            path = Path(config.path).resolve()
            if not path.is_relative_to(base):
                continue
            with self.subTest(module=config.name):
                package = path / "tests" / "__init__.py"
                self.assertTrue(package.is_file(), f"Модуль {config.name}: нет пакета тестов {package}")
