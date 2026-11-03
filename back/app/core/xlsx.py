"""XLSX из готовых строк и действие админки «Выгрузить в Excel».

    from core.xlsx import export_xlsx

    class FormRequestAdmin(admin.ModelAdmin):
        actions = [export_xlsx]

Выгружает тот, кто видит список: отмеченные записи или все под фильтром («Выбрать все»), в порядке списка.
"""
import datetime
import html
import io
import re
from decimal import Decimal
from math import isfinite
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import admin
from django.contrib.admin.utils import label_for_field, lookup_field
from django.http import FileResponse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import SafeData
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.writer.excel import ExcelWriter

# Символы, которых нет в XML 1.0: управляющие и U+FFFE, U+FFFF. openpyxl отказывает только на управляющих,
# а U+FFFF пишет как есть — лист в файле не откроется
ILLEGAL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def build_xlsx(headers, rows) -> io.BytesIO:
    """Заголовки и конечный одноразовый источник строк → xlsx в начале открытого BytesIO.

    Ячейки: str, bool, int/float/Decimal, date/datetime, time без tzinfo, None.
    Порядок сохраняется; пустой источник даёт только заголовок. Буфер закрывает вызывающий.
    Неподдерживаемые типы, aware time, NaN/Infinity, текст >32767 символов — ValueError.
    Вызывающий ограничивает строки/колонки и объём; файл целиком в памяти.
    """
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet()
    buffer = io.BytesIO()
    try:
        sheet.append([cell(sheet, str(header)) for header in headers])
        for row in rows:
            sheet.append([cell(sheet, result) for result in row])
        # Workbook.save() не закрывает ZIP при ошибке записи.
        with ZipFile(buffer, "w", ZIP_DEFLATED, allowZip64=True) as archive:
            ExcelWriter(workbook, archive).save()
        buffer.seek(0)
        return buffer
    except BaseException:
        buffer.close()
        # Workbook.close() не убирает XML write_only при ошибке до/во время save.
        # Закрываем поток листа и удаляем его собственный временный файл.
        try:
            if not sheet.closed:
                sheet.close()
        finally:
            if sheet._writer is not None:
                sheet._writer.close()
                if Path(sheet._writer.out).exists():
                    sheet._writer.cleanup()
        raise
    finally:
        workbook.close()


@admin.action(description="Выгрузить в Excel", permissions=["view"])
def export_xlsx(modeladmin, request, queryset):
    name_list = modeladmin.get_list_display(request)
    headers = [str(label_for_field(name, queryset.model, modeladmin)) for name in name_list]
    rows = ([value(obj, name, modeladmin) for name in name_list] for obj in queryset.iterator(chunk_size=2000))
    buffer = build_xlsx(headers, rows)
    filename = f"{queryset.model._meta.verbose_name_plural} {timezone.localdate():%Y-%m-%d}.xlsx"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def value(obj, name, modeladmin):
    """Значение колонки — как в списке: подпись выбора, строка связи, HTML без разметки."""
    field, _, result = lookup_field(name, obj, modeladmin)
    if field is not None and field.choices:
        result = dict(field.flatchoices).get(result, result)
    if result is None or isinstance(result, (bool, int, float, Decimal, datetime.date, datetime.time)):
        return result
    if isinstance(result, SafeData):
        result = html.unescape(strip_tags(result))  # колонка-метод админки с разметкой
    return str(result)


def cell(sheet, result):
    """Строка — всегда текст. openpyxl пишет «=…» формулой, а «#N/A» — ошибкой: имя «=HYPERLINK(…)»
    из формы сайта стало бы ссылкой в таблице менеджера."""
    if result is not None and not isinstance(result, (str, bool, int, float, Decimal, datetime.date, datetime.time)):
        raise ValueError("Неподдерживаемый тип ячейки XLSX")
    if isinstance(result, datetime.time) and result.tzinfo is not None:
        raise ValueError("Время XLSX должно быть без часового пояса")
    if isinstance(result, (float, Decimal)) and not isfinite(result):
        raise ValueError("Число XLSX должно быть конечным")
    if isinstance(result, datetime.datetime) and timezone.is_aware(result):
        result = timezone.localtime(result).replace(tzinfo=None)  # Excel не знает часовых поясов
    if isinstance(result, str):
        result = ILLEGAL_CHARACTERS.sub("", result)
        if len(result) > 32767:
            raise ValueError("Текст XLSX длиннее 32767 символов")
    xlsx_cell = WriteOnlyCell(sheet, result)
    if isinstance(result, str):
        xlsx_cell.data_type = "s"
    return xlsx_cell
