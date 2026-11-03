"""Сбой настоящей записи XML не оставляет файл и не мешает соседнему экспорту."""
import builtins
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import gettempdir
from threading import Event
from unittest.mock import patch

from django.test import SimpleTestCase
from openpyxl import load_workbook

from core.xlsx import build_xlsx


class XlsxXmlWriteTest(SimpleTestCase):
    def test_disk_write_error_preserves_cause_and_cleans_only_own_file(self):
        started, resume = Event(), Event()

        def healthy_rows():
            yield ['Соседний экспорт']
            started.set()
            if not resume.wait(10):
                raise RuntimeError('Соседний экспорт не продолжен')

        real_open = builtins.open
        with ThreadPoolExecutor(max_workers=1) as pool:
            healthy = pool.submit(build_xlsx, ['Имя'], healthy_rows())
            try:
                self.assertTrue(started.wait(10))
                before = set(Path(gettempdir()).glob('openpyxl.*'))
                self.assertTrue(before)
                for limit in (1, 15, 50):
                    with self.subTest(fail_write_at=limit):
                        files = []
                        buffer = io.BytesIO()
                        error = OSError('Сбой настоящей записи XML')

                        class BrokenDiskFile:
                            def __init__(self, file):
                                self.file, self.count = file, 0
                                files.append(file)

                            def write(self, text):
                                self.count += 1
                                if self.count >= limit:
                                    raise error
                                return self.file.write(text)

                            def __enter__(self):
                                return self

                            def __exit__(self, *args):
                                return self.file.__exit__(*args)

                        def disk_open(file, *args, **kwargs):
                            opened = real_open(file, *args, **kwargs)
                            if 'openpyxl.' in str(file) and args and args[0] == 'w':
                                return BrokenDiskFile(opened)
                            return opened

                        with patch.object(builtins, 'open', side_effect=disk_open), \
                                patch('core.xlsx.io.BytesIO', return_value=buffer):
                            with self.assertRaises(OSError) as caught:
                                build_xlsx(['Имя'], [['Анна'], ['Борис']])
                        self.assertIs(caught.exception, error)
                        self.assertTrue(buffer.closed)
                        self.assertTrue(files)
                        self.assertTrue(all(file.closed for file in files))
                        self.assertEqual(set(Path(gettempdir()).glob('openpyxl.*')), before)
            finally:
                resume.set()
            with healthy.result(timeout=10) as buffer:
                self.assertEqual(load_workbook(buffer).active['A2'].value, 'Соседний экспорт')
