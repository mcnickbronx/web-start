"""Сериализация очереди и команды Redis при подтверждении выполненной задачи, без сети."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase
from taskiq.message import TaskiqMessage
from taskiq_redis import RedisStreamBroker


class BrokerPayloadTest(SimpleTestCase):
    def test_code_payload_is_serialized_and_ack_does_not_request_erasure(self):
        broker = RedisStreamBroker("redis://127.0.0.1:1/0", queue_name="tasks", maxlen=10_000)
        message = TaskiqMessage(task_id="synthetic-38", task_name="user.tasks:send_code",
                                labels={}, args=["reader@example.com", "123456", "activation"], kwargs={})
        encoded = broker.formatter.dumps(message)
        decoded = broker.formatter.loads(encoded.message)
        self.assertEqual(decoded.args, ["reader@example.com", "123456", "activation"])
        redis = MagicMock()
        redis.xadd = AsyncMock()
        redis.xack = AsyncMock()
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=redis)
        context.__aexit__ = AsyncMock(return_value=False)

        async def scenario():
            with patch("taskiq_redis.redis_broker.Redis", return_value=context):
                await broker.kick(encoded)
                await broker._ack_generator("1-0", "tasks")()
            await broker.connection_pool.disconnect()

        asyncio.run(scenario())
        redis.xadd.assert_awaited_once_with("tasks", {b"data": encoded.message}, maxlen=10_000, approximate=True)
        redis.xack.assert_awaited_once_with("tasks", "taskiq", "1-0")
        self.assertEqual([call[0] for call in redis.mock_calls], ["xadd", "xack"])
