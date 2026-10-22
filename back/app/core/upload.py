"""Файл от посетителя: проверка, случайное имя на диске, уборка неприложенных, выдача из API.

    from core import upload

    content = await upload.read_upload(file, conf.FILE_SIZE_MAX_MB)                                    # эндпоинт
    extension = upload.check_upload(file_name, content, conf.FILE_EXTENSION_LIST, conf.FILE_SIZE_MAX_MB)  # сервис
    name = await upload.save_upload(models.file_storage(), extension, content)                          # сервис
    upload.clear_orphans(models.MyFile.objects.filter(record__isnull=True, date_add__lt=...))           # уборка
    return await upload.file_response(models.file_storage(), my_file.file, my_file.original_name)      # выдача

Модель файла, привязка к записи и право на скачивание — в модуле: у каждого свои.
"""
import asyncio
import mimetypes
import os
import stat
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils import timezone
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse


async def read_upload(file: UploadFile, size_max_mb: int) -> bytes:
    """Читает на байт больше предела: так check_upload узнаёт, что файл больше, не загружая его целиком."""
    return await file.read(size_max_mb * 1024 * 1024 + 1)


def check_upload(file_name: str, content: bytes, extension_list: list[str], size_max_mb: int) -> str:
    """Формат по расширению без учёта регистра, не пустой, не больше предела — иначе 406 с текстом
    для посетителя, в этом порядке. Возвращает расширение строчными, без точки."""
    extension = Path(file_name).suffix.lstrip(".").lower()
    if extension not in extension_list:
        raise HTTPException(406, f"Допустимые форматы: {', '.join(extension_list)}")
    if not content:
        raise HTTPException(406, "Файл пустой")
    if len(content) > size_max_mb * 1024 * 1024:
        raise HTTPException(406, f"Файл больше {size_max_mb} МБ")
    return extension


async def save_upload(storage: Storage, extension: str, content: bytes) -> str:
    """Сохраняет под случайным именем `ГГГГ/ММ/<uuid>.<расширение>`: имя посетителя в путь не попадает
    и чужой файл не затирает, исходное модуль хранит в записи сам. Возвращает имя для FileField."""
    name = f"{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{extension}"
    return await asyncio.to_thread(storage.save, name, ContentFile(content))


async def file_response(storage: Storage, name: str, filename: str = "") -> FileResponse:
    """Закрытый файл в ответ API — когда модуль уже проверил право. name — имя в хранилище из записи в базе,
    не из запроса: за папку хранилища storage.path не выпустит. Нет имени или файла на диске — 404, как у записи,
    которой нет. Файл скачивается, а не открывается в браузере, и не оседает в кэше прокси; filename — имя
    для посетителя, кириллица и кавычки уходят в Content-Disposition по RFC 5987."""
    path = storage.path(name) if name else ""
    try:
        stat_result = await asyncio.to_thread(os.stat, path)
    except (FileNotFoundError, NotADirectoryError):  # NotADirectoryError — в записи путь «через» файл: <файл>.pdf/x
        raise HTTPException(404) from None
    if not stat.S_ISREG(stat_result.st_mode):
        raise HTTPException(404)
    return FileResponse(
        path, filename=filename or Path(name).name, stat_result=stat_result,
        # Тип — по расширению на диске: его проверил check_upload, а имя посетителя — нет
        media_type=mimetypes.guess_type(path)[0] or "application/octet-stream",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


def delete_files(object_list, field: str = "file") -> None:
    """Удаляет файлы записей с диска — Django при удалении записей этого не делает. Нет файла — не ошибка."""
    for obj in object_list:
        getattr(obj, field).delete(save=False)


def clear_orphans(queryset, field: str = "file") -> int:
    """Удаляет записи под фильтром вместе с файлами на диске. Возвращает число удалённых."""
    object_list = list(queryset)
    delete_files(object_list, field)
    queryset.model._default_manager.filter(pk__in=[obj.pk for obj in object_list]).delete()
    return len(object_list)
