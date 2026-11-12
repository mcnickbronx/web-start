import tempfile
from pathlib import Path

from django.core.files.storage import FileSystemStorage
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from core.upload import delete_files


class DeleteFilesTest(SimpleTestCase):
    @isolate_apps()
    def test_missing_file_does_not_interrupt_deletion(self):
        """Отсутствующий файл посередине не мешает удалить следующий; посторонний файл остаётся."""
        with tempfile.TemporaryDirectory() as root:
            storage = FileSystemStorage(location=root)

            class UploadedFile(models.Model):
                file = models.FileField(storage=storage)

                class Meta:
                    app_label = "core"

            name_list = ["first.pdf", "missing.pdf", "last.pdf"]
            first, missing, last = [Path(root) / name for name in name_list]
            keep = Path(root) / "keep.pdf"
            first.write_bytes(b"first")
            last.write_bytes(b"last")
            keep.write_bytes(b"keep")
            object_list = [UploadedFile(file=name) for name in name_list]

            self.assertEqual(first.read_bytes(), b"first")
            self.assertFalse(missing.exists())
            self.assertEqual(last.read_bytes(), b"last")
            self.assertEqual(keep.read_bytes(), b"keep")

            delete_files(object_list)

            for path in (first, missing, last):
                self.assertFalse(path.exists())
            self.assertEqual(keep.read_bytes(), b"keep")

            # Новые объекты сохраняют прежние имена уже удалённых файлов.
            delete_files([UploadedFile(file=name) for name in name_list])

            for path in (first, missing, last):
                self.assertFalse(path.exists())
            self.assertEqual(keep.read_bytes(), b"keep")
