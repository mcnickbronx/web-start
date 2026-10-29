"""Лимит: память под конкурентной нагрузкой и контракт Redis backend (без настоящего Redis)."""
import asyncio
import threading
from unittest import mock

from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.redis import RedisCache
from django.test import SimpleTestCase

from core import cache


class CacheHitTest(SimpleTestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(cache, "_hit_memory", {}))
        self.store = DummyCache("", {})
        self.enterContext(mock.patch.object(cache, "backend", return_value=self.store))

    def hit(self, key="one", limit=2, period=10):
        return asyncio.run(cache.hit(key, limit, period))

    def test_memory_concurrency(self):
        async def many():
            return await asyncio.gather(*(cache.hit("shared", 7, 60) for _ in range(100)))

        self.assertEqual(sum(asyncio.run(many())), 7)

    def test_fixed_window_and_expired_keys_removed(self):
        with mock.patch.object(cache.time, "monotonic", return_value=100):
            self.assertTrue(self.hit())
            self.assertTrue(self.hit("other", period=3))
        with mock.patch.object(cache.time, "monotonic", return_value=109):
            self.assertTrue(self.hit())
            self.assertFalse(self.hit())
            self.assertNotIn("other", cache._hit_memory)
        with mock.patch.object(cache.time, "monotonic", return_value=110):
            self.assertTrue(self.hit())
            self.assertEqual(cache._hit_memory["one"], (1, 120))

    def test_invalid_limit_or_period(self):
        for limit, period in [(0, 1), (-1, 1), (1, 0), (1, -1)]:
            with self.subTest(limit=limit, period=period), self.assertRaises(ValueError):
                self.hit(limit=limit, period=period)

    def test_redis_failure_uses_memory_without_exception_text(self):
        store = RedisCache("redis://example.com", {})
        client = mock.Mock()
        client.eval.side_effect = ConnectionError("redis-secret-91bf")
        with mock.patch.object(cache, "backend", return_value=store), mock.patch.object(store._cache, "get_client", return_value=client):
            with self.assertLogs("core.cache", "WARNING") as logs:
                self.assertEqual([self.hit() for _ in range(3)], [True, True, False])
        self.assertNotIn("redis-secret-91bf", "\n".join(logs.output))
        self.assertTrue(all(record.exc_info is None for record in logs.records))
        with mock.patch.object(cache, "backend", side_effect=RuntimeError("redis-secret-91bf")):
            with self.assertLogs("core.cache", "WARNING"):
                self.assertFalse(self.hit())

    def test_redis_single_atomic_operation_with_expiry_and_key_prefix(self):
        """Double возвращает счётчики сервера; срок/исчезновение перед EVAL — ответственность скрипта.
        Проверяет использование RedisCache, ключ Django, поток и одну операцию вместо EXISTS+INCR.
        Исполнение Lua на Redis этим тестом не проверяется."""
        store = RedisCache("redis://example.com", {"KEY_PREFIX": "test-prefix"})
        main_thread, threads = threading.get_ident(), []
        counts = iter([1, 2, 3, 1])  # ключ исчез перед последним атомарным вызовом

        def evaluate(script, key_count, key, expiry):
            threads.append(threading.get_ident())
            self.assertEqual((key_count, key, expiry), (1, "test-prefix:1:one", 10))
            self.assertIn("redis.call('INCR', KEYS[1])", script)
            self.assertIn("if count == 1 or redis.call('TTL', KEYS[1]) < 0 then", script)
            self.assertIn("redis.call('EXPIRE', KEYS[1], ARGV[1])", script)
            return next(counts)

        client = mock.Mock(spec=["eval"])
        client.eval.side_effect = evaluate
        with mock.patch.object(cache, "backend", return_value=store), mock.patch.object(store._cache, "get_client", return_value=client) as get_client:
            self.assertEqual([self.hit() for _ in range(4)], [True, True, False, True])
        self.assertEqual(client.eval.call_count, 4)
        get_client.assert_called_with("test-prefix:1:one", write=True)
        self.assertTrue(all(thread != main_thread for thread in threads))
        self.assertEqual(cache._hit_memory, {})
