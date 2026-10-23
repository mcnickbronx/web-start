"""Картинка из админки → webp: ширина до предела модуля, поворот по EXIF.

    from core.image import to_webp

    content, extension = to_webp(upload.read(), extension, width_max=conf.IMAGE_WIDTH_MAX)  # сервис модуля

Формат и размер файла не проверяет — это правила модуля (`check_image` в `page/services.py`) или `core.upload`.
Не картинку не отвергает, а отдаёт как есть: что файл открывается как картинка, проверяет модуль до вызова.
"""
import io

from PIL import Image, ImageOps


def to_webp(content: bytes, extension: str, *, width_max: int) -> tuple[bytes, str]:
    """Ужимает до width_max и переводит в webp: фото с телефона на 8 МБ убьёт скорость страницы.

    gif не трогаем — может быть анимированным. Файл не читается — отдаём как есть:
    оптимизация некритичная и не должна мешать загрузке.
    """
    if extension == "gif":
        return content, extension
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
        # Телефон сохраняет снимок как есть, а поворот — тегом EXIF. В webp тег не переходит, и вертикальное
        # фото легло бы на бок, — поворачиваем сами
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
        if image.width > width_max:
            height = round(image.height * width_max / image.width)
            image = image.resize((width_max, height), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=82, method=4)
        return buffer.getvalue(), "webp"
    except Exception:
        return content, extension
