from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.urls import reverse

from core.tests.api import ApiTestCase
from form import conf, services
from form.models import FormFile, FormRequest
from form.tests.create import create_form_type
from user.tests.create import create_user


class FormApiTest(ApiTestCase):
    def open_form(self, code="callback") -> dict:
        """Описание формы с токеном — как его получает сайт при открытии формы."""
        return self.api.get(f"/api/form/detail/{code}").json()

    def send(self, form: dict, **fields):
        return self.api.post("/api/form/create", json={"token": form["token"], "phone": "+79990001122"} | fields)

    def test_request_saved_and_emailed(self):
        create_form_type()
        visit = {"landing_page": "https://site.ru/?utm_source=yandex&utm_medium=cpc"}
        self.assertEqual(self.send(self.open_form(), name="Анна", visit=visit).json(), {"message": "Заявка отправлена"})
        self.wait_tasks()
        form_request = FormRequest.objects.get()
        self.assertEqual((form_request.status, form_request.email_status, form_request.channel), ("new", "sent", "ads"))
        self.assertEqual(form_request.utm, {"utm_source": "yandex", "utm_medium": "cpc"})
        self.assertEqual(mail.outbox[0].to, ["manager@example.com"])

    def test_field_errors(self):
        create_form_type()
        response = self.send(self.open_form(), phone="")
        self.assertEqual(response.status_code, 422)
        self.assertEqual({error["loc"] for error in response.json()["full_error"]}, {"phone", "email"})

    def test_token_single_use(self):
        create_form_type()
        form = self.open_form()
        self.assertEqual(self.send(form).status_code, 200)
        response = self.send(form)
        self.assertEqual(response.status_code, 406)
        self.assertIn("Заявка уже отправлена", response.json()["message"])

    def test_bot_saved_as_spam_without_email(self):
        create_form_type(is_trap=True)
        form = self.open_form()
        self.assertEqual(form["fill_seconds_min"], 3)  # столько сайт ждёт перед отправкой сам
        response = self.send(form, leave_empty="https://spam.example")
        self.assertEqual(response.json(), {"message": "Заявка отправлена"})  # бот не узнаёт, что пойман
        self.wait_tasks()
        self.assertEqual(FormRequest.objects.get().status, "spam")
        self.assertEqual(mail.outbox, [])

    @patch.object(conf, "CAPTCHA_PROVIDER", "numeric")
    def test_numeric_captcha(self):
        create_form_type(is_captcha=True)
        form = self.open_form()
        left, right = map(int, form["captcha_question"].split(" + "))
        response = self.send(form, captcha=str(left + right + 1))
        self.assertEqual(response.json()["full_error"][0]["loc"], "captcha")
        self.assertEqual(self.send(form, captcha=str(left + right)).status_code, 200)

    def test_file_upload(self):
        """Файл к заявке: в закрытой папке, приложен к заявке, скачать — только с правом на заявки."""
        create_form_type(is_file=True)
        form = self.open_form()
        response = self.api.post("/api/form/upload-file", data={"token": form["token"]}, files={"file": ("Справка.pdf", b"%PDF-1.4", "application/pdf")})
        file_id = response.json()["file_id"]
        self.assertEqual(self.send(form, file_id_list=[file_id]).status_code, 200)
        form_file = FormFile.objects.get()
        self.addCleanup(services.delete_files, [form_file])
        self.assertEqual(form_file.form_request_id, FormRequest.objects.get().id)
        # Не в media/: оттуда файлы открыты всем по прямой ссылке
        self.assertTrue(Path(form_file.file.path).is_relative_to(conf.FILE_ROOT))

        url = reverse("admin:form_formrequest_file", args=[file_id])
        self.client.force_login(create_user(email="manager@example.com", is_staff=True))  # в админке, но без права на заявки
        with self.assertLogs("django.request", "WARNING"):  # отказ Django пишет в лог
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"%PDF-1.4")
