"""Картинка → webp: ширина до предела, поворот по EXIF, gif и не картинка — как есть."""
import io

from django.test import SimpleTestCase
from PIL import Image

from core.image import to_webp


def image_bytes(size: tuple[int, int], image_format: str, **kwargs) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, format=image_format, **kwargs)
    return buffer.getvalue()


class ToWebpTest(SimpleTestCase):
    def test_wide_shrinks_to_width_max(self):
        """Шире предела — ужата до width_max с той же пропорцией; уже предела — размер прежний."""
        content, extension = to_webp(image_bytes((3000, 2000), "JPEG"), "jpg", width_max=600)
        self.assertEqual((extension, Image.open(io.BytesIO(content)).size), ("webp", (600, 400)))
        content, extension = to_webp(image_bytes((300, 200), "JPEG"), "jpg", width_max=600)
        self.assertEqual((extension, Image.open(io.BytesIO(content)).size), ("webp", (300, 200)))

    def test_phone_photo_stays_upright(self):
        """Вертикальное фото 20×40 телефон кладёт в файл 40×20 с тегом поворота — в webp оно стоит."""
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: при показе повернуть на 90°
        content, extension = to_webp(image_bytes((40, 20), "JPEG", exif=exif), "jpg", width_max=600)
        self.assertEqual((extension, Image.open(io.BytesIO(content)).size), ("webp", (20, 40)))

    def test_gif_as_is(self):
        """gif может быть анимированным — те же байты."""
        content = image_bytes((3000, 2000), "GIF")
        self.assertEqual(to_webp(content, "gif", width_max=600), (content, "gif"))

    def test_not_image_as_is(self):
        """Не открывается как картинка — те же байты и расширение: загрузку оптимизация не ломает."""
        self.assertEqual(to_webp(b"not an image", "png", width_max=600), (b"not an image", "png"))
