"""Уведомления о заявках: реальные HTTP, транзакция, независимые чаты и приватные поля."""
import json
from unittest import mock

from django.core import mail
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from core import telegram
from core.tests.api import ApiTestCase
from core.tests.test_telegram import FakeTelegramMixin, TOKEN
from form import services
from form.models import FormFile, FormRequest, FormType
from form.tests.create import create_form_type


class TelegramFormTest(FakeTelegramMixin, ApiTestCase):
    contact_map = {"name": "УникальноеИмя", "phone": "+79998887766", "email": "private@example.com",
                   "message": "УникальноеСообщение", "data": {"УникальноеПоле": ["СекретныйОтвет", 7]}}
    tech_list = ["testclient", "UniqueUserAgent", "unique-ym", "unique-landing", "unique-referrer", "unique-utm", "unique-source"]

    def submit(self, detail=None, **fields):
        detail = detail or self.api.get("/api/form/detail/callback").json()
        return self.api.post("/api/form/create", json={
            "token": detail["token"], **self.contact_map, "source": "unique-source",
            "visit": {"landing_page": "https://example.com/unique-landing?utm_medium=cpc&utm_source=unique-utm",
                      "referrer": "https://example.com/unique-referrer", "ym_client_id": "unique-ym"},
            **fields,
        }, headers={"user-agent": "UniqueUserAgent"})

    def test_default_two_chats_no_personal_data(self):
        form_type = create_form_type(telegram_chat=" -101, , -102 ", is_email_tech_info=True)
        self.assertFalse(form_type.is_telegram_contacts)
        self.assertEqual(self.submit().status_code, 200)
        self.wait_tasks()
        record = FormRequest.objects.get()
        self.assertEqual(record.email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([body["chat_id"] for _, body in self.message_list], ["-101", "-102"])
        text = self.message_list[0][1]["text"]
        self.assertEqual(text, f"Заявка №{record.id}\nФорма: {form_type.name}\nКанал: Реклама\nФайлов: 0")
        for value in [*self.contact_map.values(), "УникальноеПоле", "СекретныйОтвет", *self.tech_list]:
            self.assertNotIn(str(value), text)

    def test_explicit_contacts_and_file_count_but_no_technical_data(self):
        form_type = create_form_type(telegram_chat="-101", is_telegram_contacts=True, is_email_tech_info=True, is_file=True)
        detail = self.api.get("/api/form/detail/callback").json()
        # Только запись файла: задача передаёт число, а не имя или содержимое.
        from form.services import read_token
        token_id = read_token(detail["token"])["id"]
        file = FormFile.objects.create(token_id=token_id, file="private-name.pdf", original_name="SecretFileName.pdf")
        response = self.submit(detail, file_id_list=[str(file.id)])
        self.assertEqual(response.status_code, 200)
        self.wait_tasks()
        text = self.message_list[0][1]["text"]
        for value in ["УникальноеИмя", "+79998887766", "private@example.com", "УникальноеСообщение", "УникальноеПоле: СекретныйОтвет, 7", "Файлов: 1"]:
            self.assertIn(value, text)
        for value in [*self.tech_list, "SecretFileName", "private-name"]:
            self.assertNotIn(value, text)
        record = FormRequest.objects.get()
        self.assertEqual(record.form_type_id, form_type.id)
        self.assertEqual((record.ip, record.user_agent, record.ym_client_id), ("testclient", "UniqueUserAgent", "unique-ym"))
        self.assertTrue(record.utm and record.referrer and record.landing_page and record.source)

    def test_no_token_no_chat_and_spam_do_not_send(self):
        form_type = create_form_type(telegram_chat="-101", is_trap=True)
        with mock.patch.object(services.send_request_telegram, "kiq") as queued:
            self.assertEqual(self.submit(leave_empty="bot").status_code, 200)
            self.wait_tasks()
        queued.assert_not_called()
        self.assertEqual(FormRequest.objects.get().status, "spam")
        form_type.is_trap = False
        form_type.telegram_chat = " , "
        form_type.save()
        with mock.patch.object(services.send_request_telegram, "kiq") as queued:
            self.assertEqual(self.submit().status_code, 200)
            self.wait_tasks()
        queued.assert_not_called()
        form_type.telegram_chat = "-101"
        form_type.save()
        with mock.patch.object(telegram, "TOKEN", ""), mock.patch.object(services.send_request_telegram, "kiq") as queued:
            self.assertEqual(self.submit().status_code, 200)
            self.wait_tasks()
        queued.assert_not_called()
        self.assertEqual(self.message_list, [])
        self.http_mock.assert_not_called()

    def test_failed_chat_does_not_stop_second_or_email(self):
        create_form_type(telegram_chat="-101,-102")
        self.is_first_chat_failed = True
        with self.assertLogs("form.tasks", "WARNING") as logs:
            self.assertEqual(self.submit().status_code, 200)
            self.wait_tasks()
        self.assertEqual([body["chat_id"] for _, body in self.message_list], ["-101", "-102"])
        self.assertEqual(FormRequest.objects.get().email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(TOKEN, "\n".join(logs.output))
        self.assertTrue(all(record.exc_info is None for record in logs.records))

    def test_enqueue_error_is_safe_and_preserves_request_and_email(self):
        create_form_type(telegram_chat="-101")
        with mock.patch.object(services.send_request_telegram, "kiq", side_effect=RuntimeError(TOKEN)), self.assertLogs("form.services", "WARNING") as logs:
            self.assertEqual(self.submit().status_code, 200)
            self.wait_tasks()
        self.assertEqual(FormRequest.objects.get().email_status, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.message_list, [])
        self.assertNotIn(TOKEN, "\n".join(logs.output))
        self.assertTrue(all(record.exc_info is None for record in logs.records))

    def test_queue_runs_after_transaction(self):
        create_form_type(telegram_chat="-101")
        original = services.send_request_telegram.kiq

        async def enqueue(record_id):
            # Читаем по независимому соединению Django: незакоммиченную заявку оно не увидит.
            from asgiref.sync import sync_to_async
            self.assertTrue(await sync_to_async(FormRequest.objects.filter(id=record_id).exists)())
            return await original(record_id)

        with mock.patch.object(services.send_request_telegram, "kiq", side_effect=enqueue) as queued:
            self.assertEqual(self.submit().status_code, 200)
            self.wait_tasks()
        queued.assert_awaited_once()
        self.assertEqual(len(self.message_list), 1)

    def test_private_settings_are_absent_in_detail_and_openapi(self):
        create_form_type(telegram_chat="-101", is_telegram_contacts=True)
        detail = self.api.get("/api/form/detail/callback").json()
        schema = self.api.app.openapi()
        serialized = json.dumps({"detail": detail, "schema": schema})
        for value in ["telegram_chat", "is_telegram_contacts", "-101"]:
            self.assertNotIn(value, serialized)


class TelegramMigrationTest(TestCase):
    def test_old_form_type_insert_uses_disabled_database_defaults(self):
        # Модель до0008 пишет ровно старые колонки; на новой схеме должна продолжать работать.
        state = MigrationLoader(connection).project_state([("form", "0007_history")])
        old_form_type = state.apps.get_model("form", "FormType")
        old = old_form_type.objects.create(name="Старая форма", code="old-process")
        current = FormType.objects.get(id=old.pk)
        self.assertEqual(current.telegram_chat, "")
        self.assertIs(current.is_telegram_contacts, False)
