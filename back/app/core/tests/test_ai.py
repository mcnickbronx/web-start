"""ИИ: настоящий локальный HTTP, ограниченные повторы, схема, лимит и тайна ошибок."""
import asyncio
import copy
import importlib
import io
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import aiohttp
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from starlette.testclient import TestClient

from core import ai, cache, env, http
from core.errors import register_error_handlers
from core.tests.test_http import run

TEXT_SECRET = "text-secret-21f3"
VALIDATOR_SECRET = "validator-secret-508a"
KEY_SECRET = "key-secret-78b1"
PROXY_SECRET = "http://name:proxy-secret-11fe@example.com:3128"


class Answer(BaseModel):
    count: int


class PrivateValidator(Answer):
    @field_validator("count")
    @classmethod
    def reject(cls, value):
        raise ValueError(VALIDATOR_SECRET)


def completion(content='{"count":2}', **kwargs):
    return {"choices": [{"message": {"content": content, **kwargs}}],
            "usage": {"total_tokens": 9, "secret": TEXT_SECRET}}


def rejecting_schema(error_type):
    class RejectingAnswer(Answer):
        @field_validator("count")
        @classmethod
        def reject(cls, value):
            raise error_type(VALIDATOR_SECRET)
    return RejectingAnswer


class ChatTest(SimpleTestCase):
    def setUp(self):
        self.responses, self.requests = [], []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.requests.append((self.path, self.headers.get("Authorization"), body))
                status, content = test.responses.pop(0) if test.responses else (200, completion())
                if status is None:
                    self.connection.close()
                    return
                data = (json.dumps(content) if not isinstance(content, str) else content).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.enterContext(mock.patch.multiple(ai, BASE_URL=f"http://127.0.0.1:{server.server_port}/v1", API_KEY=KEY_SECRET,
                                             PROXY="", MODEL="test-model", TIMEOUT=60, USER_LIMIT=2))
        self.enterContext(mock.patch.object(cache, "_hit_memory", {}))

    def chat(self, messages=None, **kwargs):
        options = {"service": "Пример", "user_id": 7, **kwargs}
        return run(lambda: ai.chat(messages or [{"role": "user", "content": TEXT_SECRET}], **options))

    def error_text(self, schema=Answer, **kwargs):
        with self.assertLogs("core.errors", "WARNING") as logs:
            try:
                self.chat(schema=schema, **kwargs)
            except http.ExternalServiceError as error:
                trace = "".join(traceback.format_exception(error))
                app = FastAPI()
                register_error_handlers(app)

                @app.get("/example")
                async def example():
                    raise error

                # Вызов внутри except: переменная error доступна до выхода из блока.
                with TestClient(app) as client:
                    response = client.get("/example")
                self.assertEqual(response.status_code, 502)
                return trace + response.text + "\n".join(logs.output)
        self.fail("Ожидалась безопасная ошибка сервиса")

    def assert_private(self, text):
        for secret in [TEXT_SECRET, VALIDATOR_SECRET, KEY_SECRET, PROXY_SECRET, "proxy-secret-11fe"]:
            self.assertNotIn(secret, text)

    def test_disabled_no_http_or_slot(self):
        with mock.patch.object(ai, "API_KEY", ""), mock.patch.object(cache, "hit") as hit:
            self.assertIn("ИИ выключен", self.error_text())
        hit.assert_not_called()
        self.assertEqual(self.requests, [])

    def test_schema_and_string_keep_messages(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": TEXT_SECRET}]}]
        original = copy.deepcopy(messages)
        with self.assertLogs("core.ai", "INFO") as logs:
            result = self.chat(messages, schema=Answer)
        self.assertEqual(result.count, 2)
        self.assertEqual(messages, original)
        path, auth, body = self.requests[0]
        self.assertEqual((path, auth), ("/v1/chat/completions", "Bearer " + KEY_SECRET))
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn('"count"', body["messages"][0]["content"])
        self.assert_private("\n".join(logs.output))
        self.assertIn("total_tokens", logs.output[0])
        self.assertEqual(self.chat(), '{"count":2}')
        self.assertNotIn("response_format", self.requests[1][2])

    def test_json_repair_once_and_same_slot(self):
        for invalid in [TEXT_SECRET, json.dumps({"count": TEXT_SECRET})]:
            with self.subTest(invalid=invalid):
                self.responses = [(200, completion(invalid)), (200, completion())]
                cache._hit_memory.clear()
                self.requests.clear()
                messages = [{"role": "user", "content": TEXT_SECRET}]
                self.assertEqual(self.chat(messages, schema=Answer).count, 2)
                self.assertEqual(len(self.requests), 2)
                repair = self.requests[1][2]["messages"]
                self.assertEqual(repair[-2], {"role": "assistant", "content": invalid})
                self.assertIn("Исправь JSON", repair[-1]["content"])
                self.assertEqual(len(messages), 1)
                self.assertTrue(self.chat())
                with self.assertRaises(HTTPException):
                    self.chat()
                self.assertEqual(len(self.requests), 3)

    def test_invalid_twice_private_in_trace_and_handler(self):
        for schema, content in [(Answer, TEXT_SECRET), (Answer, json.dumps({"count": TEXT_SECRET})),
                                (PrivateValidator, '{"count":1}')]:
            with self.subTest(schema=schema):
                cache._hit_memory.clear()
                self.requests.clear()
                self.responses = [(200, completion(content))] * 2
                self.assert_private(self.error_text(schema))
                self.assertEqual(len(self.requests), 2)
                self.assertNotIn(VALIDATOR_SECRET, self.requests[-1][2]["messages"][-1]["content"])

    def test_invalid_body_and_refusal(self):
        for body in [TEXT_SECRET, {}, [], {"choices": []}, {"choices": [None]}, completion(""), completion("  "),
                     completion(None), completion(refusal=TEXT_SECRET), {"choices": [{"message": []}]}]:
            with self.subTest(body=body):
                self.responses = [(200, body)]
                before = len(self.requests)
                self.assert_private(self.error_text(user_id=None))
                self.assertEqual(len(self.requests), before + 1)

    def test_unexpected_validator_error_has_private_traceback(self):
        for error_type in [TypeError, RuntimeError]:
            with self.subTest(error_type=error_type):
                before = len(self.requests)
                try:
                    self.chat(schema=rejecting_schema(error_type), user_id=None)
                except http.ExternalServiceError as error:
                    self.assert_private("".join(traceback.format_exception(error)))
                    self.assertIsNone(error.__cause__)
                    self.assertTrue(error.__suppress_context__)
                else:
                    self.fail("Ожидалась безопасная ошибка выполнения схемы")
                self.assertEqual(len(self.requests), before + 1)

    def test_unexpected_validator_error_uses_safe_api_handler(self):
        for error_type in [TypeError, RuntimeError]:
            with self.subTest(error_type=error_type):
                schema = rejecting_schema(error_type)
                app = FastAPI()
                register_error_handlers(app)

                @app.get("/example")
                async def example():
                    try:
                        return await ai.chat([], service="Пример", user_id=None, schema=schema)
                    finally:
                        await http.close()

                with self.assertLogs("core.errors", "WARNING") as logs:
                    with TestClient(app, raise_server_exceptions=False) as client:
                        response = client.get("/example")
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"message": "Сервис «Пример» недоступен. Попробуйте позже"})
                self.assert_private(response.text + "\n".join(logs.output))
                self.assertEqual([record.levelname for record in logs.records], ["WARNING"])
                self.assertIsNone(logs.records[0].exc_info)

    def test_validator_cancellation_is_not_a_schema_error(self):
        with self.assertRaises(asyncio.CancelledError):
            self.chat(schema=rejecting_schema(asyncio.CancelledError), user_id=None)
        self.assertEqual(len(self.requests), 1)

    def test_http_and_network_errors_are_private(self):
        for status, hint in [(400, "400"), (401, "AI_API_KEY"), (403, "доступ"), (404, "AI_MODEL")]:
            with self.subTest(status=status):
                self.responses = [(status, TEXT_SECRET + KEY_SECRET + PROXY_SECRET)]
                before = len(self.requests)
                text = self.error_text(user_id=None)
                self.assertIn(hint, text)
                self.assert_private(text)
                self.assertEqual(len(self.requests), before + 1)
        self.responses = [(None, None)]  # реальный разрыв HTTP до заголовков
        before = len(self.requests)
        self.assert_private(self.error_text(user_id=None))
        self.assertEqual(len(self.requests), before + 1)
        with mock.patch.object(ai, "PROXY", PROXY_SECRET), mock.patch.object(http, "session") as session:
            session.return_value.request.side_effect = aiohttp.ClientConnectionError(KEY_SECRET + PROXY_SECRET)
            self.assert_private(self.error_text(user_id=None))

    def test_http_retries_bounded_across_schema_repair(self):
        with mock.patch.object(ai.asyncio, "sleep", new_callable=mock.AsyncMock) as sleep:
            self.responses = [(429, TEXT_SECRET), (200, completion(TEXT_SECRET)), (503, KEY_SECRET), (500, PROXY_SECRET)]
            self.assert_private(self.error_text())
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(sleep.await_args_list, [mock.call(1), mock.call(2)])

    def test_all_retryable_statuses(self):
        for status in [429, 500, 502, 503]:
            with self.subTest(status=status), mock.patch.object(ai.asyncio, "sleep", new_callable=mock.AsyncMock) as sleep:
                self.responses = [(status, TEXT_SECRET)] * 2 + [(200, completion())]
                before = len(self.requests)
                self.assertTrue(self.chat(user_id=None))
                self.assertEqual(len(self.requests), before + 3)
                self.assertEqual(sleep.await_count, 2)

    def test_shared_user_limit_and_standard_429(self):
        self.chat(service="Первый", model="model-one")
        self.chat(service="Второй", model="model-two")
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/example")
        async def example():
            return await ai.chat([], service="Третий", user_id=7)

        with TestClient(app) as client:
            response = client.get("/example")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json(), {"message": "Лимит запросов к ИИ — 2 в час. Попробуйте позже"})
        self.assertEqual(len(self.requests), 2)
        self.chat(user_id=8)
        self.assertEqual(len(self.requests), 3)
        with mock.patch.object(cache, "hit") as hit:
            self.chat(user_id=None)
            with mock.patch.object(ai, "USER_LIMIT", 0):
                self.chat()
        hit.assert_not_called()
        self.assertEqual(len(self.requests), 5)

    def test_command_success_disabled_and_401(self):
        self.responses = [(200, completion('{"answer":"готово"}'))]
        out = io.StringIO()
        with mock.patch.object(http, "close", wraps=http.close) as close:
            call_command("ai_check", stdout=out)
        self.assertIn('"answer":"готово"', out.getvalue())
        self.assertIn("Время:", out.getvalue())
        self.assert_private(out.getvalue())
        self.assertEqual(close.await_count, 1)
        self.assertIsNone(http._session)
        for key, responses, count in [("", [], 1), (KEY_SECRET, [(401, TEXT_SECRET + KEY_SECRET)], 2)]:
            self.responses = responses
            out = io.StringIO()
            with mock.patch.object(ai, "API_KEY", key), mock.patch.object(ai, "PROXY", PROXY_SECRET if not key else ""):
                with self.assertRaises(CommandError) as context:
                    call_command("ai_check", stdout=out)
            if not key:
                self.assertIn("Прокси: задан", out.getvalue())
            self.assert_private(out.getvalue())
            self.assert_private("".join(traceback.format_exception(context.exception)))
            self.assertEqual(len(self.requests), count)


class AiSettingsTest(SimpleTestCase):
    def load(self, changes):
        current = {key: value for key, value in os.environ.items() if not key.startswith("AI_")}
        with mock.patch.dict(os.environ, current | changes, clear=True), mock.patch.object(env, "SETTING_LIST", []):
            importlib.reload(ai)
            out = io.StringIO()
            call_command("env_settings", stdout=out)
            return out.getvalue()

    def tearDown(self):
        # reload не оставляет пробные значения/дубликаты реестра для остальных тестов.
        with mock.patch.object(env, "SETTING_LIST", []):
            importlib.reload(ai)

    def test_startup_and_secret_settings(self):
        self.assertTrue({"AI_BASE_URL", "AI_API_KEY", "AI_PROXY", "AI_TIMEOUT", "AI_USER_LIMIT", "AI_MODEL"}
                        <= {item.name for item in env.SETTING_LIST})
        output = self.load({"AI_API_KEY": KEY_SECRET, "AI_BASE_URL": "http://name:url-secret@example.com/v1", "AI_PROXY": PROXY_SECRET})
        self.assertIn("AI_API_KEY = задан", output)
        self.assertIn("AI_PROXY = задан", output)
        self.assertIn("AI_BASE_URL = задан", output)
        self.assertNotIn(KEY_SECRET, output)
        self.assertNotIn(PROXY_SECRET, output)
        self.assertNotIn("url-secret", output)

    def test_defaults(self):
        self.load({})
        self.assertEqual((ai.MODEL, ai.TIMEOUT, ai.USER_LIMIT, ai.API_KEY, ai.PROXY), ("gpt-5.6-terra", 60, 100, "", ""))

    def test_invalid_configuration_hides_values(self):
        for name, value in [("AI_PROXY", "socks5://name:password-hidden@example.com:1080"),
                            ("AI_BASE_URL", "https://[password-hidden"), ("AI_PROXY", "http://example.com:password-hidden"),
                            ("AI_TIMEOUT", "password-hidden"), ("AI_TIMEOUT", "0"), ("AI_TIMEOUT", "601"),
                            ("AI_USER_LIMIT", "-1")]:
            with self.subTest(name=name, value=value), self.assertRaises(ImproperlyConfigured) as context:
                self.load({name: value})
            self.assertIn(name, str(context.exception))
            trace = "".join(traceback.format_exception(context.exception))
            self.assertNotIn(f"{name}={value}", trace)
            self.assertNotIn("password-hidden", trace)
