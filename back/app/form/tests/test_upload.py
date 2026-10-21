from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.utils import timezone

from core.tests.api import ApiTestCase
from form import conf, services
from form.models import FormFile
from form.tests.create import create_form_type

FORMAT_ERROR = "Допустимые форматы: " + ", ".join(conf.FILE_EXTENSION_LIST)


class UploadFileTest(ApiTestCase):
    """Границы загрузки файла к заявке: что примут, что отклонят и с каким текстом — его сайт показывает посетителю."""

    def setUp(self):
        super().setUp()
        # Файлы с диска — до очистки таблиц: уборки теста выполняются раньше неё
        self.addCleanup(lambda: services.delete_files(list(FormFile.objects.all())))

    def open_form(self, code="callback") -> dict:
        return self.api.get(f"/api/form/detail/{code}").json()

    def upload(self, form: dict, name="справка.pdf", content=b"%PDF-1.4"):
        return self.api.post("/api/form/upload-file", data={"token": form["token"]}, files={"file": (name, content, "application/octet-stream")})

    def assertRejected(self, response, message):
        self.assertEqual((response.status_code, response.json()["message"]), (406, message))

    def test_format(self):
        """Формат — по последнему расширению, без учёта регистра. «справка.pdf.exe» — не pdf, у «.pdf» (скрытый файл)
        расширения нет: иначе под видом документа пришла бы программа."""
        create_form_type(is_file=True)
        form = self.open_form()
        self.assertEqual(self.upload(form, "Справка.PDF").status_code, 200)
        for name in ["справка.pdf.exe", "script.php", "без-расширения", ".pdf"]:
            with self.subTest(name):
                self.assertRejected(self.upload(form, name), FORMAT_ERROR)

    def test_empty(self):
        """Пустой файл — 406: в заявке он ничего не сообщит, а посетитель, скорее всего, выбрал не тот."""
        create_form_type(is_file=True)
        self.assertRejected(self.upload(self.open_form(), "пустой.pdf", b""), "Файл пустой")

    @patch.object(conf, "FILE_SIZE_MAX_MB", 1)
    def test_size(self):
        """Ровно предел — можно, на байт больше — 406: граница не съезжает ни в одну сторону, и файл больше
        предела не принимается, даже если читается не целиком."""
        create_form_type(is_file=True)
        form = self.open_form()
        self.assertEqual(self.upload(form, "ровно.pdf", b"x" * 1024 * 1024).status_code, 200)
        for name, size in [("на-байт-больше.pdf", 1024 * 1024 + 1), ("два-мегабайта.pdf", 2 * 1024 * 1024)]:
            with self.subTest(name):
                self.assertRejected(self.upload(form, name, b"x" * size), "Файл больше 1 МБ")

    @patch.object(conf, "FILE_SIZE_MAX_MB", 1)
    def test_check_order(self):
        """Порядок проверок — договор с сайтом: какой текст увидит посетитель, когда не так сразу несколько.
        Сначала — принимает ли форма файлы, потом формат, потом пустой и размер."""
        create_form_type(is_file=True)
        form = self.open_form()
        self.assertRejected(self.upload(form, "пустой.exe", b""), FORMAT_ERROR)
        self.assertRejected(self.upload(form, "большой.exe", b"x" * 2 * 1024 * 1024), FORMAT_ERROR)

        create_form_type(name="Отзыв", code="review", is_file=False)
        form = self.open_form("review")
        for name, content in [("справка.pdf", b"%PDF-1.4"), ("пустой.exe", b"")]:
            with self.subTest(name):
                self.assertRejected(self.upload(form, name, content), "К этой форме нельзя прикладывать файлы")

    def test_file_count_max(self):
        """Не больше file_count_max файлов на открытую форму. Число проверяется после файла: лишний файл
        неверного формата получает текст про формат — посетитель поправит сам файл, а не их число."""
        create_form_type(is_file=True, file_count_max=1)
        form = self.open_form()
        self.assertEqual(self.upload(form).status_code, 200)
        self.assertRejected(self.upload(form), "Можно приложить не больше 1 файлов")
        self.assertRejected(self.upload(form, "справка.exe"), FORMAT_ERROR)
        self.assertRejected(self.upload(form, "пустой.pdf", b""), "Файл пустой")

    def test_name_on_disk(self):
        """Имя на диске случайное, расширение строчными: имя посетителя в путь не попадает («../», чужой файл
        с тем же именем). Исходное имя и размер хранятся в записи — под этим именем файл и скачивают."""
        create_form_type(is_file=True)
        form = self.open_form()
        content = b"%PDF-1.4 two"
        for _ in range(2):
            self.assertEqual(self.upload(form, "Справка.PDF", content).status_code, 200)
        file_list = list(FormFile.objects.all())
        self.assertNotEqual(file_list[0].file.name, file_list[1].file.name)
        for form_file in file_list:
            self.assertRegex(form_file.file.name, r"^\d{4}/\d{2}/[0-9a-f]{32}\.pdf$")
            self.assertEqual((form_file.original_name, form_file.size), ("Справка.PDF", len(content)))
            path = Path(form_file.file.path)
            self.assertTrue(path.is_relative_to(conf.FILE_ROOT))
            self.assertEqual(path.read_bytes(), content)

    def test_clear_orphan_files(self):
        """Уборка удаляет только ничьи файлы старше срока — и запись, и файл на диске. Свежий ничей (посетитель
        ещё заполняет форму) и приложенный к заявке остаются."""
        create_form_type(is_file=True)
        form = self.open_form()
        old_id, fresh_id, attached_id = [self.upload(form, f"{name}.pdf").json()["file_id"] for name in ["старый", "свежий", "приложенный"]]
        response = self.api.post("/api/form/create", json={"token": form["token"], "phone": "+79990001122", "file_id_list": [attached_id]})
        self.assertEqual(response.status_code, 200)
        self.wait_tasks()
        # date_add — auto_now_add, сдвинуть можно только запросом
        FormFile.objects.filter(id__in=[old_id, attached_id]).update(date_add=timezone.now() - timedelta(hours=conf.FILE_ORPHAN_HOURS + 1))
        old_path = Path(FormFile.objects.get(id=old_id).file.path)

        self.assertEqual(services.clear_orphan_files(), 1)
        self.assertFalse(old_path.exists())
        self.assertEqual({str(form_file.id) for form_file in FormFile.objects.all()}, {fresh_id, attached_id})
        for form_file in FormFile.objects.all():
            self.assertTrue(Path(form_file.file.path).exists())
