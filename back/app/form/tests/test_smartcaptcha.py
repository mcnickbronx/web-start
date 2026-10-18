"""Яндекс SmartCaptcha: токен виджета проверяется у подменного «Яндекса» на 127.0.0.1, без сети."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs

from django.test import SimpleTestCase

from core.tests.api import ApiTestCase
from form import captcha, conf
from form.models import FormRequest
from form.tests.create import create_form_type


class FakeYandexMixin:
    """Подменный Яндекс: отвечает кодом и JSON из self.answer, поля запросов копит в self.request_list.
    HTTP_PROXY из окружения не мешает: aiohttp по умолчанию его не читает (trust_env=False)."""

    def setUp(self):
        super().setUp()
        self.answer = (200, {"status": "ok", "message": ""})
        self.request_list = []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode()
                test.request_list.append({key: value[0] for key, value in parse_qs(body).items()})
                status, data = test.answer
                content = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):  # без строки на каждый запрос в выводе тестов
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # shutdown() ждёт до poll_interval: по умолчанию это полсекунды на каждый тест
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)  # cleanup идёт с конца: сначала остановить, потом закрыть
        url = f"http://127.0.0.1:{self.server.server_port}/validate"
        self.enterContext(patch.object(captcha, "SMARTCAPTCHA_URL", url))
        self.enterContext(patch.object(conf, "SMARTCAPTCHA_SERVER_KEY", "server-key"))


class CheckYandexTest(FakeYandexMixin, SimpleTestCase):
    def check(self, token="widget-token") -> bool:
        return asyncio.run(captcha.check_yandex(token, "203.0.113.5"))

    def test_passed(self):
        self.assertTrue(self.check())
        self.assertEqual(self.request_list, [{"secret": "server-key", "token": "widget-token", "ip": "203.0.113.5"}])

    def test_failed(self):
        self.answer = (200, {"status": "failed", "message": "Token invalid or expired."})
        self.assertFalse(self.check())

    def test_empty_token(self):
        self.assertFalse(self.check(""))
        self.assertEqual(self.request_list, [])  # к Яндексу не ходили

    def test_yandex_error(self):
        """Сбой Яндекса — заявка проходит, в журнале предупреждение."""
        self.answer = (500, {"message": "Internal error"})
        with self.assertLogs("form.captcha", "WARNING") as logs:
            self.assertTrue(self.check())
        self.assertEqual([record.levelname for record in logs.records], ["WARNING"])
        self.assertIn("SmartCaptcha ответила 500", logs.output[0])

    def test_wrong_server_key(self):
        """403 — неверный ключ сервера: заявка проходит, но в журнале ошибка, а не предупреждение —
        по ней form/readme.md советует проверить капчу после включения."""
        self.answer = (403, {"status": "failed", "message": "Authentication failed. Secret has not provided."})
        with self.assertLogs("form.captcha", "ERROR") as logs:
            self.assertTrue(self.check())
        self.assertIn("SmartCaptcha ответила 403", logs.output[0])

    def test_no_connection(self):
        self.server.shutdown()
        self.server.server_close()  # порт закрыт: соединение отклонено
        with self.assertLogs("form.captcha", "WARNING") as logs:
            self.assertTrue(self.check())
        self.assertEqual([record.levelname for record in logs.records], ["WARNING"])
        self.assertIn("SmartCaptcha не ответила", logs.output[0])


class SmartCaptchaApiTest(FakeYandexMixin, ApiTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(conf, "CAPTCHA_PROVIDER", "yandex"))
        self.enterContext(patch.object(conf, "SMARTCAPTCHA_CLIENT_KEY", "client-key"))

    def test_yandex_captcha(self):
        create_form_type(is_captcha=True)
        form = self.api.get("/api/form/detail/callback").json()
        self.assertEqual((form["captcha_provider"], form["captcha_client_key"], form["captcha_question"]), ("yandex", "client-key", None))
        data = {"token": form["token"], "phone": "+79990001122", "captcha": "widget-token"}

        self.answer = (200, {"status": "failed", "message": "Token invalid or expired."})
        response = self.api.post("/api/form/create", json=data)
        self.assertEqual(response.status_code, 422)
        self.assertEqual([error["loc"] for error in response.json()["full_error"]], ["captcha"])

        self.answer = (200, {"status": "ok", "message": ""})
        self.assertEqual(self.api.post("/api/form/create", json=data).status_code, 200)
        self.assertEqual(FormRequest.objects.count(), 1)
