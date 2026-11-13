"""Сброс справочника переживает сборку мусора без отладочного удержания Django."""
import gc
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from django.core.cache.backends.locmem import LocMemCache
from django.dispatch import Signal
from django.test import SimpleTestCase, override_settings

from core import cache


@override_settings(DEBUG=False)
class CacheSignalLifetimeTest(SimpleTestCase):
    def test_post_save_after_gc(self):
        self.assert_cleared_after_gc("post_save")

    def test_post_delete_after_gc(self):
        self.assert_cleared_after_gc("post_delete")

    def assert_cleared_after_gc(self, signal_name):
        class SyntheticCategory:
            _meta = SimpleNamespace(label="test.SyntheticCategory")

        class OtherCategory:
            pass

        store = LocMemCache(f"cache-signal-lifetime-{uuid4()}", {})
        self.addCleanup(store.clear)
        signals = {name: Signal(use_caching=True) for name in ("post_save", "post_delete")}
        self.enterContext(mock.patch.multiple(cache, **signals))
        self.enterContext(mock.patch.object(cache, "backend", new=lambda: store))
        # Проверяем жизнь получателя, а не границу транзакции: callback исполняется сразу.
        self.enterContext(mock.patch.object(cache.transaction, "on_commit", new=lambda callback, using: callback()))
        store.set("test:category_list", ["Новости"])
        store.set("test:untouched", "оставить")

        cache.clear_on_change(SyntheticCategory, "test:category_list")
        gc.collect()

        signal = signals[signal_name]
        signal.send(sender=OtherCategory, using="default")
        self.assertEqual(store.get("test:category_list"), ["Новости"])
        self.assertEqual(store.get("test:untouched"), "оставить")

        signal.send(sender=SyntheticCategory, using="default")
        self.assertIsNone(store.get("test:category_list"))
        self.assertEqual(store.get("test:untouched"), "оставить")
