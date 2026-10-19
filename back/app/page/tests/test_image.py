"""Картинки из админки: загрузка из редактора и в «Картинках», ужатие в webp, файлы на диске."""
import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from page import conf
from page.models import PageImage
from page.services import optimize_image
from user.tests.create import create_user


def image_file(name="foto.png", size=(3000, 2000)) -> SimpleUploadedFile:
    """Картинка PNG как из формы загрузки."""
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


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


class ImageUploadTest(TestCase):
    """Две дороги картинки в админке: вставка в текст редактора (upload-image) и «Картинки → добавить»."""

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media)
        settings = override_settings(MEDIA_ROOT=media)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))

    def upload(self, file):
        return self.client.post(reverse("admin:page_page_upload_image"), {"image": file})

    def test_editor(self):
        """Из редактора: ужата до IMAGE_WIDTH_MAX, webp, исходное имя сохранено, файл на диске."""
        response = self.upload(image_file())
        self.assertEqual(response.status_code, 200)
        image = PageImage.objects.get(id=response.json()["id"])
        self.assertEqual((image.original_name, image.file.name[-5:], response.json()["url"]), ("foto.png", ".webp", image.file.url))
        self.assertEqual(Image.open(image.file.path).size, (conf.IMAGE_WIDTH_MAX, round(2000 * conf.IMAGE_WIDTH_MAX / 3000)))

    def test_editor_rejects(self):
        """Не картинка — ошибка с текстом для редактора, записи нет."""
        cases = [
            (SimpleUploadedFile("script.svg", b"<svg onload='alert(1)'/>"), "Допустимые форматы"),
            (SimpleUploadedFile("broken.png", b"not an image"), "Загрузите правильное изображение"),
        ]
        for file, message in cases:
            with self.subTest(file.name):
                response = self.upload(file)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.json()["message"])
        self.assertFalse(PageImage.objects.exists())

    def test_editor_without_rights(self):
        """Сотрудник, который страницы только смотрит, картинку в текст не загрузит."""
        viewer = create_user(email="viewer@example.com", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_page"))
        self.client.force_login(viewer)
        self.assertEqual(self.upload(image_file()).status_code, 403)

    def test_images_section(self):
        """«Картинки»: добавить — webp; заменить файл — старый уходит с диска; удалить запись — и файл."""
        self.client.post(reverse("admin:page_pageimage_add"), {"file": image_file(), "alt": "Фото"})
        image = PageImage.objects.get()
        first = Path(image.file.path)
        self.assertEqual((first.suffix, first.exists()), (".webp", True))
        self.client.post(reverse("admin:page_pageimage_change", args=[image.id]), {"file": image_file("new.jpg"), "alt": "Фото"})
        image.refresh_from_db()
        second = Path(image.file.path)
        self.assertEqual((image.original_name, first.exists(), second.exists()), ("new.jpg", False, True))
        self.client.post(reverse("admin:page_pageimage_delete", args=[image.id]), {"post": "yes"})
        self.assertFalse(second.exists())
