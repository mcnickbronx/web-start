import asyncio

from django.test import SimpleTestCase

from core import cache


class CacheTtlTest(SimpleTestCase):
    def test_ttl_required(self):
        """Без срока — ошибка: ключ без срока Redis не вытесняет, при полной памяти он откажет в записи и задачам."""
        async def fetch():
            return []

        for ttl in [None, 0, -1]:
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                asyncio.run(cache.get_or_set("core:test", fetch, ttl=ttl))
