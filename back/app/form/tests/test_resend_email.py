"""«Отправить письмо ещё раз»: сервис API, вызванный из админки через мост (core/bridge.py)."""
import re
from unittest.mock import patch

from django.core import mail
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from fastapi import HTTPException
from starlette.testclient import TestClient

from core.tests.api import ApiTestCase
from form import services
from form.models import FormRequest
from form.tests.create import create_form_request, create_form_type
from user.tests.create import create_user

ERROR = FormRequest.EmailStatus.ERROR


class ResendEmailTest(TransactionTestCase):
    """Как команда manage.py: у вызова своё соединение с базой."""

    def test_resend(self):
        form_request = create_form_request(email_status=ERROR, email_error="SMTP не ответил")
        services.resend_request_email.sync(form_request.id)
        form_request.refresh_from_db()
        self.assertEqual((form_request.email_status, form_request.email_error), ("sent", ""))
        self.assertEqual(len(mail.outbox), 1)

    def test_refusals(self):
        spam = create_form_request(status=FormRequest.Status.SPAM)
        with self.assertRaisesMessage(HTTPException, "Заявка в спаме"):
            services.resend_request_email.sync(spam.id)
        silent = create_form_request(form_type=create_form_type("Без адресов", code="silent", email_to=""))
        with self.assertRaisesMessage(HTTPException, "не указано, кому отправлять"):
            services.resend_request_email.sync(silent.id)
        self.assertEqual(mail.outbox, [])

    def test_admin_action(self):
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        form_request = create_form_request(email_status=ERROR)
        data = {"action": "resend_email", "_selected_action": [form_request.id]}
        response = self.client.post(reverse("admin:form_formrequest_changelist"), data, follow=True)
        self.assertContains(response, "Письма поставлены в очередь: 1")
        self.assertEqual(len(mail.outbox), 1)


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)  # клиент ходит по http
class ResendEmailSameProcessTest(ApiTestCase):
    """Админка в одном процессе с API (профиль light, runserver): вызов идёт через соединения API."""

    def setUp(self):
        from project.asgi import application  # админка и API одним приложением, как на сервере

        self.api = self.enterContext(TestClient(application))

    def test_admin_action_through_asgi(self):
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        self.api.cookies.set("sessionid", self.client.cookies["sessionid"].value)
        form_request = create_form_request(email_status=ERROR)
        url = reverse("admin:form_formrequest_changelist")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', self.api.get(url).text).group(1)
        data = {"csrfmiddlewaretoken": token, "action": "resend_email", "_selected_action": form_request.id}
        with patch("core.bridge.TortoiseContext", side_effect=AssertionError("мост открыл своё соединение")):
            self.assertIn("Письма поставлены в очередь: 1", self.api.post(url, data=data).text)
        self.wait_tasks()
        self.assertEqual(len(mail.outbox), 1)

    def test_sync_from_thread_while_api_runs(self):
        """Обычный поток в процессе, где работает API: у вызова свой цикл — и своё соединение."""
        form_request = create_form_request(email_status=ERROR)
        services.resend_request_email.sync(form_request.id)
        form_request.refresh_from_db()
        self.assertEqual(form_request.email_status, "sent")
