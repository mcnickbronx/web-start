import uuid
from urllib.parse import unquote

from core.tests.api import ApiTestCase
from form import services
from form.models import FormFile
from form.tests.create import create_form_type
from user.tests.create import auth_header, create_user


class FileDownloadTest(ApiTestCase):
    """Свой файл заявки из API: скачивает только автор заявки, остальным — тот же 404, что на файл, которого нет."""

    def setUp(self):
        super().setUp()
        # Файлы с диска — до очистки таблиц: уборки теста выполняются раньше неё
        self.addCleanup(lambda: services.delete_files(list(FormFile.objects.all())))
        create_form_type(is_file=True)
        self.owner = create_user()

    def upload(self, name="справка.pdf", content=b"%PDF-1.4") -> tuple[dict, str]:
        """Открыть форму и загрузить файл, как сайт. Возвращает форму и file_id."""
        form = self.api.get("/api/form/detail/callback").json()
        response = self.api.post("/api/form/upload-file", data={"token": form["token"]}, files={"file": (name, content, "application/pdf")})
        return form, response.json()["file_id"]

    def send_with_file(self, user=None, name="справка.pdf", content=b"%PDF-1.4") -> str:
        """Заявка с файлом; user — заявку отправил вошедший, без него — гость. Возвращает file_id."""
        form, file_id = self.upload(name, content)
        headers = auth_header(user) if user else {}
        response = self.api.post("/api/form/create", json={"token": form["token"], "phone": "+79990001122", "file_id_list": [file_id]}, headers=headers)
        self.assertEqual(response.status_code, 200)
        return file_id

    def download(self, file_id, user=None):
        return self.api.get(f"/api/form/file/{file_id}", headers=auth_header(user) if user else {})

    def test_owner(self):
        """Автор заявки получает свой файл: те же байты, тип по расширению, имя посетителя с кириллицей и кавычками
        целиком, скачивание вместо показа в браузере, без кэша на прокси."""
        file_id = self.send_with_file(self.owner, "справка.PDF", b"%PDF-1.4 content")
        # Кавычку в имени файла браузер, как и клиент теста, присылает как %22 — имя с кавычками кладём в запись сами:
        # здесь проверяется выдача, а не загрузка
        name = 'Справка "№1"; копия.PDF'
        FormFile.objects.filter(id=file_id).update(original_name=name)
        response = self.download(file_id, self.owner)
        self.assertEqual((response.status_code, response.content), (200, b"%PDF-1.4 content"))
        self.assertEqual(response.headers["content-type"], "application/pdf")
        disposition_type, filename = response.headers["content-disposition"].split("; filename*=utf-8''")
        self.assertEqual((disposition_type, unquote(filename)), ("attachment", name))
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("private", response.headers["cache-control"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_others_get_not_found(self):
        """Чужой вошедший, админ через API, файл заявки гостя, файл, ещё не приложенный к заявке (даже тому, кто его
        загрузил), — ровно тот же ответ, что на несуществующий файл: по ответу не узнать, что файл есть."""
        own_file_id = self.send_with_file(self.owner)
        guest_file_id = self.send_with_file()
        _, orphan_file_id = self.upload()
        stranger = create_user(email="stranger@example.com")
        admin = create_user(email="admin@example.com", is_staff=True, is_superuser=True)
        missing = self.download(uuid.uuid4(), self.owner)
        self.assertEqual(missing.status_code, 404)
        for case, file_id, user in [
            ("чужой", own_file_id, stranger),
            ("админ — в API как чужой, файлы заявок он скачивает в админке", own_file_id, admin),
            ("заявка гостя", guest_file_id, self.owner),
            ("не приложен", orphan_file_id, self.owner),
        ]:
            with self.subTest(case):
                response = self.download(file_id, user)
                self.assertEqual((response.status_code, response.json()), (missing.status_code, missing.json()))
                self.assertNotIn("content-disposition", response.headers)
        self.assertEqual(self.download(own_file_id, self.owner).status_code, 200)

    def test_anonymous(self):
        """Без входа и с негодным токеном — 401, файл не отдаётся."""
        file_id = self.send_with_file(self.owner)
        self.assertEqual(self.download(file_id).status_code, 401)
        response = self.api.get(f"/api/form/file/{file_id}", headers={"Authorization": "Bearer forged.token.value"})
        self.assertEqual(response.status_code, 401)

    def test_missing_on_disk(self):
        """Запись есть, а файла на диске нет (удалили руками) — 404, а не 500."""
        file_id = self.send_with_file(self.owner)
        FormFile.objects.get(id=file_id).file.delete(save=False)
        response = self.download(file_id, self.owner)
        self.assertEqual((response.status_code, response.json()), (404, {"message": "Не найдено"}))
