"""Выгрузка списка админки в Excel: действие «Выгрузить в Excel», колонки — как в списке.

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

from django.contrib import admin
from django.contrib.admin.utils import label_for_field, lookup_field
from django.http import FileResponse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import SafeData
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell

# Символы, которых нет в XML 1.0: управляющие и U+FFFE, U+FFFF. openpyxl отказывает только на управляющих,
# а U+FFFF пишет как есть — лист в файле не откроется
ILLEGAL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


@admin.action(description="Выгрузить в Excel", permissions=["view"])
def export_xlsx(modeladmin, request, queryset):
    name_list = modeladmin.get_list_display(request)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet()
    sheet.append([str(label_for_field(name, queryset.model, modeladmin)) for name in name_list])
    for obj in queryset.iterator(chunk_size=2000):
        sheet.append([cell(sheet, value(obj, name, modeladmin)) for name in name_list])
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"{queryset.model._meta.verbose_name_plural} {timezone.localdate():%Y-%m-%d}.xlsx"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def value(obj, name, modeladmin):
    """Значение колонки — как в списке: подпись выбора, строка связи, дата без часового пояса."""
    field, _, result = lookup_field(name, obj, modeladmin)
    if field is not None and field.choices:
        result = dict(field.flatchoices).get(result, result)
    if isinstance(result, datetime.datetime) and timezone.is_aware(result):
        return timezone.localtime(result).replace(tzinfo=None)  # Excel не знает часовых поясов
    if result is None or isinstance(result, (bool, int, float, Decimal, datetime.date, datetime.time)):
        return result
    if isinstance(result, SafeData):
        result = html.unescape(strip_tags(result))  # колонка-метод админки с разметкой
    # Недопустимое в xlsx из текста посетителя — убрать, а не уронить всю выгрузку
    return ILLEGAL_CHARACTERS.sub("", str(result))


def cell(sheet, result):
    """Строка — всегда текст. openpyxl пишет «=…» формулой, а «#N/A» — ошибкой: имя «=HYPERLINK(…)»
    из формы сайта стало бы ссылкой в таблице менеджера."""
    xlsx_cell = WriteOnlyCell(sheet, result)
    if isinstance(result, str):
        xlsx_cell.data_type = "s"
    return xlsx_cell
