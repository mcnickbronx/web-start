"""Прозрачность PNG сохраняется при переводе в webp."""
import io

from django.test import SimpleTestCase
from PIL import Image

from core.image import to_webp


class ToWebpTransparencyTest(SimpleTestCase):
    def test_png_transparency_is_preserved_in_webp(self):
        """RGBA, LA и палитра: прозрачные, полупрозрачные и непрозрачный пиксели остаются."""
        alpha = [0, 64, 128, 255]
        for mode in ("RGBA", "LA", "P"):
            with self.subTest(mode=mode):
                with Image.new(mode, (4, 1)) as image, io.BytesIO() as buffer:
                    if mode == "P":
                        image.putpalette([32, 128, 192] * 4)
                        image.info["transparency"] = bytes(alpha)
                    for x, value in enumerate(alpha):
                        pixel = (32, 128, 192, value) if mode == "RGBA" else (128, value)
                        image.putpixel((x, 0), x if mode == "P" else pixel)
                    image.save(buffer, format="PNG")
                    png_content = buffer.getvalue()

                # Проверяем именно закодированный вход: палитра должна сохранить свою alpha.
                with io.BytesIO(png_content) as buffer, Image.open(buffer) as source:
                    self.assertEqual(source.mode, mode)
                    with source.convert("RGBA") as rgba:
                        self.assertEqual([rgba.getpixel((x, 0))[3] for x in range(4)], alpha)

                content, extension = to_webp(png_content, "png", width_max=600)
                self.assertEqual(extension, "webp")
                with io.BytesIO(content) as buffer, Image.open(buffer) as result:
                    self.assertEqual(result.format, "WEBP")
                    self.assertEqual(result.size, (4, 1))
                    with result.convert("RGBA") as rgba:
                        self.assertEqual([rgba.getpixel((x, 0))[3] for x in range(4)], alpha)
