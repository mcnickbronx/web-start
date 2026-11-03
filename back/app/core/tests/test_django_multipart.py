"""Регресс CVE-2026-108147: base64 не обходит ранний отказ upload handler."""
import base64
from io import BytesIO

from django.core.files.uploadhandler import FileUploadHandler, MemoryFileUploadHandler, StopUpload
from django.http.multipartparser import MultiPartParser
from django.test import SimpleTestCase, override_settings


def multipart(encoded):
    return (
        b'--bounded\r\n'
        b'Content-Disposition: form-data; name="file"; filename="example.txt"\r\n'
        b'Content-Type: text/plain\r\n'
        b'Content-Transfer-Encoding: base64\r\n\r\n'
        + encoded + b'\r\n--bounded--\r\n'
    )


def parse(body, stream, handlers):
    return MultiPartParser(
        {"CONTENT_TYPE": "multipart/form-data; boundary=bounded", "CONTENT_LENGTH": str(len(body))},
        stream, handlers,
    ).parse()


class RejectUpload(FileUploadHandler):
    chunk_size = 1024

    def __init__(self, stream):
        super().__init__()
        self.stream = stream
        self.first_chunk = None
        self.bytes_read = None

    def receive_data_chunk(self, raw_data, start):
        self.first_chunk = raw_data
        self.bytes_read = self.stream.tell()
        # Ранний отказ должен оставить непрочитанный хвост запроса.
        raise StopUpload(connection_reset=True)

    def file_complete(self, file_size):
        return None


class DjangoMultipartTest(SimpleTestCase):
    @override_settings(FILE_UPLOAD_MAX_MEMORY_SIZE=1024)
    def test_base64_reaches_handler_before_reading_whole_file(self):
        content = b"bounded upload\n" * 8192
        body = multipart(base64.b64encode(content))
        with BytesIO(body) as stream:
            handler = RejectUpload(stream)
            post, files = parse(body, stream, [handler])
            self.assertIsNotNone(handler.first_chunk)
            self.assertTrue(content.startswith(handler.first_chunk))
            self.assertGreater(len(handler.first_chunk), 0)
            # Запас на заголовки и поиск границы; предел не растёт с файлом.
            self.assertLessEqual(handler.bytes_read, 4 * handler.chunk_size)
            self.assertEqual(stream.tell(), handler.bytes_read)
        self.assertFalse(post)
        self.assertFalse(files)

    def test_valid_base64_file_preserves_content(self):
        content = "Учебный файл\n".encode() * 257
        encoded = base64.b64encode(content)
        # Пробелы смещают выравнивание base64 на границах входных блоков.
        encoded = b" \r\n".join(encoded[i:i + 77] for i in range(0, len(encoded), 77))
        body = multipart(encoded)
        handler = MemoryFileUploadHandler()
        handler.chunk_size = 1024
        with BytesIO(body) as stream:
            post, files = parse(body, stream, [handler])
        self.assertFalse(post)
        with files["file"] as uploaded:
            self.assertEqual(uploaded.name, "example.txt")
            self.assertEqual(uploaded.read(), content)
