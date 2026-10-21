import io
import tempfile
from pathlib import Path

from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from fastapi import HTTPException, UploadFile

from core.upload import check_upload, read_upload, save_upload

MB = 1024 * 1024


class UploadTest(SimpleTestCase):
    def test_check(self):
        """Формат — по последнему расширению без учёта регистра, потом пустой, потом размер: 406 с текстом
        для посетителя. Ровно предел — можно."""
        self.assertEqual(check_upload("Справка.PDF", b"x", ["pdf", "docx"], 1), "pdf")
        self.assertEqual(check_upload("ровно.pdf", b"x" * MB, ["pdf"], 1), "pdf")
        for name, content, message in [
            ("справка.pdf.exe", b"x", "Допустимые форматы: pdf, docx"),
            ("без-расширения", b"x", "Допустимые форматы: pdf, docx"),
            ("пустой.exe", b"", "Допустимые форматы: pdf, docx"),
            ("пустой.pdf", b"", "Файл пустой"),
            ("на-байт-больше.pdf", b"x" * (MB + 1), "Файл больше 1 МБ"),
        ]:
            with self.subTest(name), self.assertRaises(HTTPException) as error:
                check_upload(name, content, ["pdf", "docx"], 1)
            self.assertEqual((error.exception.status_code, error.exception.detail), (406, message))

    async def test_read(self):
        """Читается предел и ещё байт — не весь файл: по лишнему байту check_upload узнаёт, что файл больше."""
        content = await read_upload(UploadFile(io.BytesIO(b"x" * 3 * MB)), 1)
        self.assertEqual(len(content), MB + 1)

    async def test_save(self):
        """Имя на диске случайное, исходное в путь не попадает; два файла с одним расширением не затирают друг друга."""
        with tempfile.TemporaryDirectory() as root:
            storage = FileSystemStorage(location=root)
            name_list = [await save_upload(storage, "pdf", b"%PDF-1.4") for _ in range(2)]
            self.assertNotEqual(*name_list)
            for name in name_list:
                self.assertRegex(name, r"^\d{4}/\d{2}/[0-9a-f]{32}\.pdf$")
                self.assertEqual((Path(root) / name).read_bytes(), b"%PDF-1.4")
