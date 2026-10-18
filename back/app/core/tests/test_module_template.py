import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class ModuleTemplateTest(SimpleTestCase):
    def test_startapp_from_template(self):
        """Заготовка модуля (back/readme.md, «Модуль»): все файлы на месте, tests/ — пакет, код без ошибок.
        Имя — такое, каким модуль не назовут: startapp не создаёт модуль с именем уже существующего."""
        with tempfile.TemporaryDirectory() as folder:
            call_command("startapp", "module_template_check", folder, template=str(settings.BASE_DIR / "core" / "module_template"), verbosity=0)
            file_set = {str(path.relative_to(folder)) for path in Path(folder).rglob("*") if path.is_file()}
            self.assertLessEqual({"__init__.py", "apps.py", "models.py", "admin.py", "schemas.py", "services.py", "rest.py",
                                  "readme.md", "migrations/__init__.py", "tests/__init__.py", "tests/create.py"}, file_set)
            for path in Path(folder).rglob("*.py"):
                compile(path.read_bytes(), str(path), "exec")
            self.assertIn('name = "module_template_check"', (Path(folder) / "apps.py").read_text(encoding="utf-8"))
