"""Telegram без живых отправок: настоящий HTTP на loopback и безопасный полный traceback."""
import asyncio
import importlib
import io
import json
import logging
import os
import socket
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase

from core import env, http, telegram

TOKEN = "123456:synthetic-token"
PROXY_SECRET = "http://proxy-user:proxy-password@127.0.0.1:9"


class FakeTelegramMixin:
    def setUp(self):
        super().setUp()
        self.message_list = []
        self.answer = (200, {"ok": True, "result": {"message_id": 1}})
        self.delay = 0
        self.is_disconnect = False
        self.is_first_chat_failed = False
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.message_list.append((self.path, data))
                if test.is_disconnect:
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                time.sleep(test.delay)
                status, body = test.answer
                if test.is_first_chat_failed and data["chat_id"] == "-101":
                    status, body = 500, {"description": TOKEN + PROXY_SECRET}
                content = (json.dumps(body) if not isinstance(body, str) else body).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.enterContext(mock.patch.object(telegram, "TOKEN", TOKEN))
        self.enterContext(mock.patch.object(telegram, "PROXY", ""))
        self.request_json = http.request_json

        async def local_request(method, url, **kwargs):
            self.assertEqual(url, f"https://api.telegram.org/bot{TOKEN}/sendMessage")
            return await self.request_json(method, self.url + urlsplit(url).path, **kwargs)

        self.http_mock = self.enterContext(mock.patch.object(http, "request_json", side_effect=local_request))

    def send(self, text="Заявка", chat="-101"):
        async def run():
            try:
                await telegram.send_message(chat, text)
            finally:
                await http.close()
        return asyncio.run(run())


class TelegramTest(FakeTelegramMixin, SimpleTestCase):
    def test_plain_text_and_limit(self):
        text = '<b>Привет & пока</b> _* https://example.com/ 😀'
        self.send(text)
        self.assertEqual(self.message_list[0], (f"/bot{TOKEN}/sendMessage", {
            "chat_id": "-101", "text": text, "link_preview_options": {"is_disabled": True},
        }))
        for character in ["а", "😀"]:
            with self.subTest(character=character):
                self.send(character * 4096)
                self.assertEqual(self.message_list[-1][1]["text"], character * 4096)
                self.send(character * 5000)
                clipped = self.message_list[-1][1]["text"]
                self.assertEqual(clipped, character * 4095 + "…")
                self.assertEqual(len(clipped), 4096)

    def test_empty_token_no_http(self):
        with mock.patch.object(telegram, "TOKEN", ""):
            self.send()
        self.http_mock.assert_not_called()
        self.assertEqual(self.message_list, [])

    def assert_safe_failure(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logger = logging.getLogger("telegram-safe-error")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.enterContext(mock.patch.object(logger, "propagate", False))
        try:
            self.send()
        except http.ExternalServiceError as error:
            logger.exception("Уведомление не отправлено")
            formatted = "".join(traceback.format_exception(error))
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
        else:
            self.fail("Ожидалась безопасная ExternalServiceError")
        for secret in [TOKEN, PROXY_SECRET, "proxy-password", "api.telegram.org", "reflected-secret"]:
            self.assertNotIn(secret, formatted + output.getvalue())
        self.assertIn("Сервис «Telegram»: не удалось отправить сообщение", formatted)

    def test_rejected_and_bad_responses(self):
        for answer in [(200, {"ok": False, "description": TOKEN + PROXY_SECRET}),
                       (200, {"ok": 1}), (200, []), (200, TOKEN),
                       (500, TOKEN + PROXY_SECRET + "reflected-secret")]:
            with self.subTest(answer=answer):
                self.answer = answer
                self.assert_safe_failure()

    def test_disconnect_and_timeout(self):
        self.is_disconnect = True
        self.assert_safe_failure()
        self.is_disconnect = False
        self.delay = 0.15
        with mock.patch.object(http, "TIMEOUT", 0.02):
            self.assert_safe_failure()

    def test_arbitrary_network_error_is_safe(self):
        self.http_mock.side_effect = RuntimeError(TOKEN + PROXY_SECRET + "reflected-secret")
        self.assert_safe_failure()

    def test_http_proxy_route(self):
        # Настоящий HTTP-прокси получает полный адрес; никакого соединения с example.com.
        async def proxy_request(method, url, **kwargs):
            return await self.request_json(method, "http://example.com/bot-token/sendMessage", **kwargs)

        self.http_mock.side_effect = proxy_request
        with mock.patch.object(telegram, "PROXY", self.url):
            self.send("Через прокси")
        self.assertEqual(self.message_list[-1][0], "http://example.com/bot-token/sendMessage")


class TelegramSettingsTest(SimpleTestCase):
    def test_secrets_registered_at_startup(self):
        setting_map = {setting.name: setting for setting in env.SETTING_LIST}
        self.assertTrue(setting_map["TELEGRAM_TOKEN"].is_secret)
        self.assertTrue(setting_map["TELEGRAM_PROXY"].is_secret)
        with mock.patch.object(env, "SETTING_LIST", [
            env.Setting("TELEGRAM_TOKEN", TOKEN, "", True, True),
            env.Setting("TELEGRAM_PROXY", PROXY_SECRET, "", True, True),
        ]):
            output = io.StringIO()
            call_command("env_settings", stdout=output)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(PROXY_SECRET, output.getvalue())
        self.assertIn("TELEGRAM_TOKEN = задан", output.getvalue())

    def test_proxy_validation_hides_credentials(self):
        try:
            with mock.patch.object(env, "SETTING_LIST", []):
                for proxy in ["socks5://user:password@example.com:1080", "http://user:password@example.com:bad", "https:///", "http://example.com:0"]:
                    with self.subTest(proxy=proxy), mock.patch.dict(os.environ, {"TELEGRAM_PROXY": proxy}):
                        with self.assertRaises(ImproperlyConfigured) as context:
                            importlib.reload(telegram)
                        self.assertIn("TELEGRAM_PROXY", str(context.exception))
                        self.assertNotIn(proxy, str(context.exception))
                        self.assertNotIn("password", str(context.exception))
                for proxy in ["", "http://user:password@example.com:8080", "https://example.com:443"]:
                    with mock.patch.dict(os.environ, {"TELEGRAM_PROXY": proxy}):
                        importlib.reload(telegram)
        finally:
            with mock.patch.object(env, "SETTING_LIST", []):
                importlib.reload(telegram)
