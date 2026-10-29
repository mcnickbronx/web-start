"""Прямые внешние импорты требуют своих строк в requirements.txt."""
import ast
from importlib.metadata import packages_distributions
from pathlib import Path
import re
import sys

from django.conf import settings
from django.test import SimpleTestCase


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


class RequirementsTest(SimpleTestCase):
    def test_external_imports_are_declared(self):
        base = Path(settings.BASE_DIR)
        local = {path.name for path in base.iterdir() if path.is_dir()}
        local.update(path.stem for path in base.glob("*.py"))
        declared = set()
        for line in (base.parent / "requirements.txt").read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==", line.strip())
            if match:
                declared.add(normalize(match[1]))

        imports = {}
        for path in sorted(base.rglob("*.py")):
            # Шаблоны *.py-tpl не являются Python-файлами приложения.
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    package = name.split(".")[0]
                    if package not in sys.stdlib_module_names and package not in local:
                        imports.setdefault(package, set()).add(f"{path.relative_to(base)}:{node.lineno}")

        distributions = packages_distributions()
        missing = []
        for package, locations in sorted(imports.items()):
            names = distributions.get(package, [])
            if not names:
                reason = "дистрибутив не найден в установленном окружении"
            elif not declared.intersection(normalize(name) for name in names):
                reason = "нет строки requirements.txt: " + ", ".join(names)
            else:
                continue
            missing.append(f"{package}: {reason} ({', '.join(sorted(locations))})")
        self.assertEqual(missing, [], "\n" + "\n".join(missing))
