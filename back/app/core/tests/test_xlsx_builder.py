"""Готовый xlsx из строк: безопасный текст, типы, выдача ASGI и настоящий потребитель."""
import asyncio
import datetime
import io
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from tempfile import gettempdir
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from core.xlsx import build_xlsx


class XlsxBuilderTest(SimpleTestCase):
    def read(self, headers, rows):
        with build_xlsx(headers, rows) as buffer:
            self.assertEqual(buffer.tell(), 0)
            return load_workbook(buffer).active

    def test_text_is_text_in_saved_file(self):
        texts = ['=HYPERLINK("https://example.com","Открыть")', '#N/A', '+79990000000',
                 '@имя', '-строка', '+строка', '\tстрока', 'Анна <b>& текст</b>', '']
        sheet = self.read(['=Заголовок\x00\x0b\ufffe\uffff'], ((text,) for text in texts))
        self.assertEqual((sheet['A1'].value, sheet['A1'].data_type), ('=Заголовок', 's'))
        for row, text in enumerate(texts[:-1], 2):
            with self.subTest(text=text):
                self.assertEqual((sheet.cell(row, 1).value, sheet.cell(row, 1).data_type), (text, 's'))
        self.assertIsNone(sheet.cell(len(texts) + 1, 1).value)  # пустой текст — пустая ячейка
        self.assertEqual(self.read(['Имя'], [['Ан\x00\x0b\ufffe\uffffна']])['A2'].value, 'Анна')

    def test_types_and_local_datetime(self):
        date = datetime.date(2026, 11, 3)
        naive = datetime.datetime(2026, 11, 3, 8, 30)
        aware = datetime.datetime(2026, 11, 3, 5, 30, tzinfo=datetime.UTC)
        time = datetime.time(12, 34, 56)
        with timezone.override('Europe/Moscow'):
            cells = list(self.read(range(9), [[7, 1.25, Decimal('12.50'), True, None, date, naive, aware, time]])[2])
        self.assertEqual([c.value for c in cells], [7, 1.25, 12.5, True, None,
                                                 datetime.datetime(2026, 11, 3), naive, naive, time])
        self.assertEqual([c.data_type for c in cells], ['n', 'n', 'n', 'b', 'n', 'd', 'd', 'd', 'd'])

    def test_empty_and_single_pass_order(self):
        self.assertEqual(list(self.read(['Имя', 'Сумма'], iter(())).values), [('Имя', 'Сумма')])

        class Once:
            def __iter__(self):
                if hasattr(self, 'used'):
                    raise AssertionError('Второй проход')
                self.used = True
                yield iter(['Борис', 2])
                yield iter(['Анна', 1])

        self.assertEqual(list(self.read(iter(['Имя', 'Сумма']), Once()).values),
                         [('Имя', 'Сумма'), ('Борис', 2), ('Анна', 1)])

    def test_source_or_type_error_closes_buffer_and_temporary_xml(self):
        def broken_rows():
            yield ['Успело записаться']
            raise RuntimeError('Источник недоступен')

        cases = [(broken_rows(), RuntimeError), ([['Первая'], [object()]], ValueError),
                 ([[datetime.time(12, tzinfo=datetime.UTC)]], ValueError),
                 ([[float('nan')]], ValueError), ([[Decimal('Infinity')]], ValueError),
                 ([['я' * 32768]], ValueError)]
        for rows, error in cases:
            with self.subTest(error=error, rows=type(rows)):
                before = set(Path(gettempdir()).glob('openpyxl.*'))
                buffer = io.BytesIO()
                with patch('core.xlsx.io.BytesIO', return_value=buffer):
                    with self.assertRaises(error):
                        build_xlsx(['Имя'], rows)
                self.assertTrue(buffer.closed)
                self.assertEqual(set(Path(gettempdir()).glob('openpyxl.*')) - before, set())

    def test_save_error_closes_buffer_and_temporary_xml(self):
        # Два реальных участка сохранения: до закрытия листа и при переносе XML в ZIP.
        for method in ['writestr', 'write']:
            with self.subTest(method=method):
                before = set(Path(gettempdir()).glob('openpyxl.*'))
                buffer = io.BytesIO()
                with patch('core.xlsx.io.BytesIO', return_value=buffer), \
                        patch('core.xlsx.ZipFile.' + method, side_effect=OSError('Диск недоступен')):
                    with self.assertRaisesRegex(OSError, 'Диск недоступен'):
                        build_xlsx(['Имя'], [['Анна']])
                self.assertTrue(buffer.closed)
                self.assertEqual(set(Path(gettempdir()).glob('openpyxl.*')) - before, set())

    def test_xml_and_text_length_boundary(self):
        self.assertEqual(self.read(['Имя'], [['Ан\ud800\udfffна']])['A2'].value, 'Анна')
        self.assertEqual(self.read(['Имя'], [['я' * 32767]])['A2'].value, 'я' * 32767)

    def test_concurrent_builds_are_independent(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            files = list(pool.map(lambda name: build_xlsx(['Имя'], [[name]]), ['Анна', 'Борис']))
        for buffer, name in zip(files, ['Анна', 'Борис']):
            with buffer:
                self.assertEqual(load_workbook(buffer).active['A2'].value, name)

    def test_synthetic_fastapi_download(self):
        app = FastAPI()  # только в тесте, проектные роутеры не меняются

        @app.get('/example-report')
        async def report():
            headers = ['Имя', 'Сумма', 'Дата']
            rows = (row for row in [
                ['=HYPERLINK("https://example.com","Открыть")', Decimal('12.30'),
                 datetime.datetime(2026, 11, 3, 5, 30, tzinfo=datetime.UTC)],
                ['Анна', None, None],
            ])
            buffer = await asyncio.to_thread(build_xlsx, headers, rows)
            with buffer:
                return Response(buffer.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                headers={'Content-Disposition': 'attachment; filename="example-report.xlsx"'})

        with timezone.override('Europe/Moscow'), TestClient(app) as client:
            response = client.get('/example-report')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(response.headers['content-disposition'], 'attachment; filename="example-report.xlsx"')
        sheet = load_workbook(io.BytesIO(response.content)).active
        self.assertEqual(list(sheet.values), [('Имя', 'Сумма', 'Дата'),
                                             ('=HYPERLINK("https://example.com","Открыть")', 12.3, datetime.datetime(2026, 11, 3, 8, 30)),
                                             ('Анна', None, None)])
        self.assertEqual((sheet['A2'].data_type, sheet['B2'].data_type, sheet['C2'].data_type), ('s', 'n', 'd'))

    def test_synthetic_fastapi_source_error_is_not_partial_download(self):
        app = FastAPI()

        def rows():
            yield ['Успело записаться']
            raise RuntimeError('Источник недоступен')

        @app.get('/example-report')
        async def report():
            buffer = await asyncio.to_thread(build_xlsx, ['Имя'], rows())
            with buffer:
                return Response(buffer.getvalue())

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get('/example-report')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('content-disposition', response.headers)
