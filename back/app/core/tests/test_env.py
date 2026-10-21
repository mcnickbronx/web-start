"""Настройки модулей из .env: нет строки — значение по умолчанию, своё — из .env, неверное — ошибка запуска."""
import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from core.env import env_int, env_list


class EnvTest(SimpleTestCase):
    def test_int(self):
        self.assertEqual(env_int("CORE_TEST_MISSING", 5), 5)
        with mock.patch.dict(os.environ, {"CORE_TEST_VALUE": " 7 "}):
            self.assertEqual(env_int("CORE_TEST_VALUE", 5), 7)
        for raw in ["", "abc", "1.5", "0", "11"]:
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"CORE_TEST_VALUE": raw}):
                with self.assertRaisesMessage(ImproperlyConfigured, "CORE_TEST_VALUE"):
                    env_int("CORE_TEST_VALUE", 5, max_value=10)

    def test_list(self):
        self.assertEqual(env_list("CORE_TEST_MISSING", ["jpg"]), ["jpg"])
        with mock.patch.dict(os.environ, {"CORE_TEST_LIST": "PDF, zip,"}):
            self.assertEqual(env_list("CORE_TEST_LIST", ["jpg"]), ["pdf", "zip"])
        with mock.patch.dict(os.environ, {"CORE_TEST_LIST": " , "}), self.assertRaises(ImproperlyConfigured):
            env_list("CORE_TEST_LIST", ["jpg"])
