import ast
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class CoreIndependenceTest(SimpleTestCase):
    def test_core_imports_no_module(self):
        """core — основа модулей: импорт модуля отсюда связал бы core с ним, и модуль нельзя было бы убрать."""
        core = Path(apps.get_app_config("core").path).resolve()
        base = Path(settings.BASE_DIR).resolve()
        modules = {config.name for config in apps.get_app_configs() if Path(config.path).resolve().parent == base and config.name != "core"}
        found = []
        for path in core.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                # import_module("…") по строке не ловим
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                found += [f"{path.relative_to(core)}:{node.lineno}: {name}" for name in names if name.split(".")[0] in modules]
        self.assertEqual(found, [])
