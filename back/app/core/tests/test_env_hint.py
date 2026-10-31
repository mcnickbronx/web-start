"""Подсказка без .env копирует публичный шаблон независимо от рабочего каталога."""
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import SimpleTestCase


class EnvHintTest(SimpleTestCase):
    def test_copy_command_uses_template_directory_and_quotes_paths(self):
        for name in ("project", "Проект с пробелом ' $(touch injected) `touch injected_backtick`; конец"):
            with self.subTest(name=name), TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                back = root / name / "back"
                project = back / "app" / "project"
                project.mkdir(parents=True)
                settings_file = project / "settings.py"
                shutil.copyfile(settings.BASE_DIR / "project" / "settings.py", settings_file)
                template = back / ".env.txt"
                shutil.copyfile(settings.BASE_DIR.parent / ".env.txt", template)
                elsewhere = root / "elsewhere"
                elsewhere.mkdir()
                environment = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8"}
                for cwd in (back / "app", elsewhere):
                    with self.subTest(cwd=cwd.name):
                        result = subprocess.run(
                            [sys.executable, "-c", "import runpy, sys; runpy.run_path(sys.argv[1])", str(settings_file)],
                            cwd=cwd, env=environment, capture_output=True, text=True, timeout=15,
                        )
                        self.assertNotEqual(result.returncode, 0)
                        prefix = "Нет .env — скопируйте шаблон: "
                        self.assertIn(prefix, result.stderr)
                        command = result.stderr.rsplit(prefix, 1)[1].strip()
                        target = back / ".env"
                        self.assertFalse(target.exists())
                        self.assertEqual(shlex.split(command), ["cp", str(template), str(target)])
                        copied = subprocess.run(
                            ["/bin/sh", "-c", command], cwd=cwd, env=environment,
                            capture_output=True, text=True, timeout=15,
                        )
                        self.assertEqual(copied.returncode, 0, copied.stderr)
                        self.assertEqual(target.read_bytes(), template.read_bytes())
                        self.assertEqual(list(root.rglob(".env")), [target])
                        self.assertFalse(list(root.rglob("injected*")))
                        target.unlink()
