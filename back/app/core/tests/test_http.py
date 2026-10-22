"""Клиент внешних API: сессия на цикл событий, таймаут, сбой сервиса — 502 с понятным текстом.
Внешний сервис — подменный, на 127.0.0.1, без сети."""
import asyncio
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aiohttp
from django.test import SimpleTestCase

from core import http
from core.bridge import with_sync
from core.tests.api import ApiTestCase


def free_url() -> str:
    """Адрес, где никто не слушает: соединение отклонено."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}/"


class FakeServiceMixin:
    """Подменный сервис: отвечает кодом и телом из self.answer, через self.delay секунд."""

    def setUp(self):
        super().setUp()
        self.answer, self.delay = (200, json.dumps({"status": "ok"})), 0
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                time.sleep(test.delay)
                status, body = test.answer
                content = body.encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True  # спящий обработчик не держит остановку теста
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"


def run(coroutine_function):
    """Вызов в своём цикле событий, сессия этого цикла в конце закрывается — как в мосте для команд."""
    async def main():
        try:
            return await coroutine_function()
        finally:
            await http.close()
    return asyncio.run(main())


class SessionTest(SimpleTestCase):
    def test_one_session_per_loop(self):
        async def two_calls():
            return http.session(), http.session()

        first, second = run(two_calls)
        self.assertIs(first, second)
        self.assertTrue(first.closed)  # close() в конце цикла её закрыл
        self.assertEqual(first.timeout.total, 60)
        self.assertIsNot(run(two_calls)[0], first)  # новый цикл — новая сессия


class RequestJsonTest(FakeServiceMixin, SimpleTestCase):
    def request(self, url=None, **kwargs):
        return run(lambda: http.request_json("GET", url or self.url, service="Пример", **kwargs))

    def test_json(self):
        self.assertEqual(self.request(), {"status": "ok"})

    def test_timeout(self):
        self.delay = 0.5
        with self.assertRaises(http.ExternalServiceError) as context:
            self.request(timeout=aiohttp.ClientTimeout(total=0.1))
        self.assertEqual((context.exception.service, context.exception.status), ("Пример", None))
        self.assertIn("таймаут", str(context.exception))

    def test_no_connection(self):
        with self.assertRaises(http.ExternalServiceError) as context:
            self.request(free_url())
        self.assertIsNone(context.exception.status)

    def test_error_status(self):
        self.answer = (503, "Service Unavailable")
        with self.assertRaises(http.ExternalServiceError) as context:
            self.request()
        self.assertEqual(context.exception.status, 503)
        self.assertIn("ответил 503: Service Unavailable", str(context.exception))

    def test_not_json(self):
        self.answer = (200, "<html>")
        with self.assertRaises(http.ExternalServiceError):
            self.request()


@with_sync
async def current_session() -> aiohttp.ClientSession:
    return http.session()


class ApiTest(ApiTestCase):
    def test_502(self):
        """Эндпоинт, у которого сервис не ответил: 502 и понятный текст, а не 500; трейса нет ни в ответе, ни в журнале."""
        url = free_url()

        async def example():
            return await http.request_json("GET", url, service="Пример")

        self.api.app.add_api_route("/api/example", example)
        with self.assertLogs("core.errors", "WARNING") as logs:
            response = self.api.get("/api/example")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Сервис «Пример» недоступен. Попробуйте позже"})
        self.assertEqual([record.levelname for record in logs.records], ["WARNING"])
        self.assertIn("GET /api/example — Сервис «Пример»", logs.output[0])
        self.assertIsNone(logs.records[0].exc_info)

    def test_closed_on_shutdown(self):
        """Остановка API закрывает сессию, вызов из команды manage.py (мост) — тоже."""
        session = self.api.portal.call(current_session)
        self.assertFalse(session.closed)
        self.api.__exit__(None, None, None)  # остановить API до конца теста; второй выход в cleanup ничего не делает
        self.assertTrue(session.closed)
        self.assertTrue(current_session.sync().closed)
