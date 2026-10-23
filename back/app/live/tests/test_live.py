"""Живые события: вход токеном первым сообщением, событие только своему пользователю, рассылка через Redis.

Redis в тестах нет: его транспорт (hub._publish, hub._listen) подменяет канал в памяти."""
import asyncio
import json
from contextlib import contextmanager
from unittest import mock

from django.test import override_settings
from starlette.websockets import WebSocketDisconnect

from core.tests.api import ApiTestCase
from live import hub
from user.auth import create_token
from user.models import UserSession
from user.tests.create import auth_header, create_user

NOTICE = {"type": "notice", "text": "Заказ оплачен"}


def access_token(user) -> str:
    return auth_header(user)["Authorization"].removeprefix("Bearer ")


class LiveTest(ApiTestCase):
    @contextmanager
    def live(self, user):
        """Соединение пользователя, который вошёл: на токен ответ ready."""
        with self.api.websocket_connect("/api/live/ws") as websocket:
            websocket.send_json({"type": "auth", "token": access_token(user)})
            self.assertEqual(websocket.receive_json(), {"type": "ready"})
            yield websocket

    def assert_pong(self, websocket):
        """Следующее в соединении — ответ на ping, а не событие."""
        websocket.send_json({"type": "ping"})
        self.assertEqual(websocket.receive_json(), {"type": "pong"})

    def assert_unauthorized(self, send_first):
        with self.api.websocket_connect("/api/live/ws") as websocket:
            send_first(websocket)
            with self.assertRaises(WebSocketDisconnect) as context:
                websocket.receive_json()
        self.assertEqual(context.exception.code, 4401)

    def test_event_to_own_user_only(self):
        anna, boris = create_user(), create_user(email="boris@example.com")
        with self.live(anna) as anna_websocket, self.live(boris) as boris_websocket:
            self.api.portal.call(hub.send, anna.id, NOTICE)
            self.assertEqual(anna_websocket.receive_json(), NOTICE)
            self.assert_pong(boris_websocket)

    def test_unauthorized(self):
        """Без годного access-токена в первом сообщении — закрытие 4401."""
        session = UserSession.objects.create(user=create_user())
        refresh = create_token(session.user_id, session.id, "refresh")
        inactive = create_user(email="inactive@example.com", is_active=False)
        case_list = [
            ("негодный токен", lambda websocket: websocket.send_json({"type": "auth", "token": "x"})),
            ("refresh вместо access", lambda websocket: websocket.send_json({"type": "auth", "token": refresh})),
            ("выключенный пользователь", lambda websocket: websocket.send_json({"type": "auth", "token": access_token(inactive)})),
            ("без токена", lambda websocket: websocket.send_json({"type": "auth"})),
            ("токен не строкой", lambda websocket: websocket.send_json({"type": "auth", "token": 1})),
            ("не JSON", lambda websocket: websocket.send_text("hello")),
            ("JSON не объектом", lambda websocket: websocket.send_text('["auth"]')),
            ("глубокая вложенность", lambda websocket: websocket.send_text("[" * 100_000)),
            ("двоичное сообщение", lambda websocket: websocket.send_bytes(b'{"type": "auth"}')),
        ]
        for name, send_first in case_list:
            with self.subTest(name):
                self.assert_unauthorized(send_first)

    def test_silence(self):
        """Первое сообщение не пришло в срок — 4401: соединение без входа не держит место в лимите Traefik."""
        with mock.patch("live.rest.AUTH_TIMEOUT", 0.1):
            self.assert_unauthorized(lambda websocket: None)

    def test_closed_connection_forgotten(self):
        anna = create_user()
        with self.live(anna):
            self.assertEqual(self.api.portal.call(hub.deliver, anna.id, NOTICE), 1)
        self.assertEqual(hub._connection_set_by_user_id, {})
        self.assertEqual(self.api.portal.call(hub.deliver, anna.id, NOTICE), 0)


class MemoryChannel:
    """Канал Redis в памяти вместо hub._publish и hub._listen. Опубликованное копится в published,
    а слушатель получает то, что тест положил в канал, — как событие из другого процесса."""

    def __init__(self, portal):
        self.portal, self.queue, self.published = portal, asyncio.Queue(), []

    async def publish(self, text):
        self.published.append(text)

    async def listen(self):
        while True:
            yield await self.queue.get()

    def put(self, message):
        self.portal.call(self.queue.put, message if isinstance(message, str) else json.dumps(message))


@override_settings(REDIS_URL="redis://test")
class LiveRedisTest(LiveTest):
    """Несколько процессов: send публикует в канал, слушатель отдаёт событие соединениям своего процесса."""

    def setUp(self):
        super().setUp()
        self.channel = MemoryChannel(self.api.portal)
        self.enterContext(mock.patch.object(hub, "_publish", self.channel.publish))
        self.enterContext(mock.patch.object(hub, "_listen", self.channel.listen))

    def test_event_to_own_user_only(self):
        """Тот же тест, что без Redis, но событие проходит через канал."""
        anna, boris = create_user(), create_user(email="boris@example.com")
        with self.live(anna) as anna_websocket, self.live(boris) as boris_websocket:
            self.api.portal.call(hub.send, anna.id, NOTICE)
            self.channel.put(self.channel.published[0])
            self.assertEqual(anna_websocket.receive_json(), NOTICE)
            self.assert_pong(boris_websocket)

    def test_send_publishes(self):
        """send в соединения сам не пишет — только в канал: иначе вкладка этого процесса получила бы событие дважды."""
        anna = create_user()
        with self.live(anna) as websocket:
            self.api.portal.call(hub.send, anna.id, NOTICE)
            self.assertEqual([json.loads(text) for text in self.channel.published], [{"user_id": anna.id, "event": NOTICE}])
            self.assert_pong(websocket)

    def test_event_from_channel(self):
        """Событие из канала — в каждое соединение пользователя по разу; непонятное — предупреждение, слушатель жив."""
        anna = create_user()
        with self.live(anna) as first, self.live(anna) as second:
            self.channel.put({"user_id": anna.id, "event": NOTICE})
            self.assertEqual(first.receive_json(), NOTICE)
            self.assertEqual(second.receive_json(), NOTICE)
            with self.assertLogs("live.hub", "WARNING") as logs:
                self.channel.put("не JSON")
                self.channel.put({"event": NOTICE})
                self.channel.put({"user_id": str(anna.id), "event": NOTICE})
                self.channel.put({"user_id": anna.id, "event": {"type": "next"}})
                self.assertEqual(first.receive_json(), {"type": "next"})
            self.assertEqual(len(logs.output), 3)
            self.assertEqual(second.receive_json(), {"type": "next"})
            self.assert_pong(first)
            self.assert_pong(second)

    def test_redis_unavailable(self):
        """Redis не ответил: send не падает, слушатель пробует снова, соединение браузера не закрывается."""
        anna = create_user()
        listen = self.channel.listen
        attempt_list, retried = [], asyncio.Event()

        async def listen_after_failure():
            attempt_list.append(len(attempt_list) + 1)
            if len(attempt_list) == 1:
                raise ConnectionError("Redis недоступен")
            retried.set()
            async for text in listen():
                yield text

        with (
            mock.patch.object(hub, "_listen", listen_after_failure),
            mock.patch.object(hub, "_publish", side_effect=ConnectionError("Redis недоступен")),
            mock.patch.object(hub, "RETRY_SECONDS", (0, 0)),
            self.assertLogs("live.hub", "WARNING") as logs,
            self.live(anna) as websocket,
        ):
            self.api.portal.call(hub.send, anna.id, NOTICE)
            self.api.portal.call(asyncio.wait_for, retried.wait(), 5)  # без новой попытки — TimeoutError, а не зависший тест
            self.channel.put({"user_id": anna.id, "event": NOTICE})
            self.assertEqual(websocket.receive_json(), NOTICE)
        self.assertEqual(attempt_list, [1, 2])
        self.assertEqual(len(logs.output), 2)
        self.assertIn("Redis не принял событие", logs.output[0] + logs.output[1])
