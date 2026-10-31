"""Настоящий multipart: отсутствие поля и пустое имя — разные случаи договора API."""
from unittest.mock import patch

from starlette.datastructures import UploadFile

from core.tests.api import ApiTestCase
from form import conf
from form.models import FormFile
from form.tests.create import create_form_type


class MultipartContractTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        create_form_type(is_file=True)
        self.files_before = {path for path in conf.FILE_ROOT.rglob("*") if path.is_file()}
        self.token = self.api.get("/api/form/detail/callback").json()["token"]

    def send(self, filename=None, content=b"", token=None):
        parts = []
        if token is not None:
            parts.append(("token", token.encode(), None))
        if filename is not None:
            parts.append(("file", content, filename))
        return self.send_parts(parts)

    def send_parts(self, parts):
        # Ручной multipart сохраняет filename="": клиентская библиотека может
        # превратить такой files-параметр в текстовое поле ещё до запроса.
        body = []
        for name, content, filename in parts:
            disposition = f'Content-Disposition: form-data; name="{name}"'
            if filename is not None:
                disposition += f'; filename="{filename}"'
            body.append(f"--boundary\r\n{disposition}\r\n\r\n".encode() + content + b"\r\n")
        return self.api.post("/api/form/upload-file", content=b"".join(body) + b"--boundary--\r\n",
                             headers={"Content-Type": "multipart/form-data; boundary=boundary"})

    def assertBusinessError(self, response, message):
        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.json(), {"message": message})
        self.assertNoFiles()

    def assertNoFiles(self):
        self.assertFalse(FormFile.objects.exists())
        self.assertEqual({path for path in conf.FILE_ROOT.rglob("*") if path.is_file()}, self.files_before)

    def assertMissing(self, response, *fields):
        self.assertEqual(response.status_code, 422)
        self.assertNoFiles()
        self.assertEqual(response.json(), {
            "message": "; ".join(["Поле обязательно для заполнения"] * len(fields)),
            "full_error": [{"type": "missing", "loc": field, "msg": "Поле обязательно для заполнения"} for field in fields],
        })

    def test_named_zero_byte_is_business_error(self):
        self.assertBusinessError(self.send("пустой.pdf", token=self.token), "Файл пустой")

    def test_absent_file_is_missing(self):
        self.assertMissing(self.send(token=self.token), "file")

    def test_empty_filename_is_format_error(self):
        for content in [b"", b"x"]:
            with self.subTest(content=content):
                self.assertBusinessError(self.send("", content, self.token),
                                         "Допустимые форматы: " + ", ".join(conf.FILE_EXTENSION_LIST))

    def test_empty_filename_keeps_other_validation_errors(self):
        self.assertMissing(self.send(""), "token")
        self.assertMissing(self.send("", token=""), "token")
        self.assertMissing(self.send(), "token", "file")
        response = self.send_parts([("token", b"not-a-string", "token.txt"), ("file", b"", "")])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {
            "message": "Значение должно быть строкой",
            "full_error": [{"type": "string_type", "loc": "token", "msg": "Значение должно быть строкой"}],
        })
        self.assertNoFiles()

    def test_empty_filename_keeps_business_check_order(self):
        self.assertBusinessError(self.send("", token="invalid"), "Форма повреждена, обновите страницу")
        create_form_type(code="without-files", is_file=False)
        token = self.api.get("/api/form/detail/without-files").json()["token"]
        self.assertBusinessError(self.send("", token=token), "К этой форме нельзя прикладывать файлы")

    def test_repeated_parts_keep_last_value(self):
        valid = ("token", self.token.encode(), None)
        invalid = ("token", b"invalid", None)
        empty = ("file", b"", "")
        named = ("file", b"", "named.pdf")
        for parts, message in [
            ([invalid, valid, empty], "Допустимые форматы: " + ", ".join(conf.FILE_EXTENSION_LIST)),
            ([valid, invalid, empty], "Форма повреждена, обновите страницу"),
            ([valid, empty, named], "Файл пустой"),
            ([valid, named, empty], "Допустимые форматы: " + ", ".join(conf.FILE_EXTENSION_LIST)),
        ]:
            with self.subTest(parts=parts):
                self.assertBusinessError(self.send_parts(parts), message)
        self.assertMissing(self.send_parts([valid, ("token", b"", None), empty]), "token")

    def test_rejected_file_is_closed(self):
        closed = []
        original_close = UploadFile.close

        async def close(file):
            self.assertFalse(file.file.closed)
            await original_close(file)
            closed.append(file)

        with patch.object(UploadFile, "close", close):
            for filename in ["", "named.pdf"]:
                self.assertEqual(self.send(filename, token=self.token).status_code, 406)
        self.assertEqual(len(closed), 2)
        self.assertTrue(all(file.file.closed for file in closed))
        self.assertNoFiles()
