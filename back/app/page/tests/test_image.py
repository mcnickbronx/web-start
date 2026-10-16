"""Картинки из админки ужимаются и переводятся в webp при загрузке."""
import io

from django.test import SimpleTestCase
from PIL import Image

from page.services import optimize_image


class OptimizeImageTest(SimpleTestCase):
    def test_phone_photo_stays_upright(self):
        """Телефон сохраняет снимок как есть, а поворот — тегом EXIF: вертикальное фото 20×40 лежит в файле 40×20."""
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: при показе повернуть на 90°
        buffer = io.BytesIO()
        Image.new("RGB", (40, 20)).save(buffer, format="JPEG", exif=exif)
        content, extension = optimize_image(buffer.getvalue(), "jpg")
        self.assertEqual(extension, "webp")
        self.assertEqual(Image.open(io.BytesIO(content)).size, (20, 40))
