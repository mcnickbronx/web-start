"""Настройки модулей из .env: нет строки — значение по умолчанию, своё — из .env, неверное — ошибка запуска."""
import io
import os
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase

from core import env as core_env
from core.env import env_int, env_list, env_str


class EnvTest(SimpleTestCase):
    def setUp(self):
        # Пробные имена — не настройки проекта: в общий список они не попадают
        patcher = mock.patch.object(core_env, "SETTING_LIST", [])
        patcher.start()
        self.addCleanup(patcher.stop)

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
        with mock.patch.dict(os.environ, {"CORE_TEST_LIST": ".PDF, zip,"}):
            self.assertEqual(env_list("CORE_TEST_LIST", ["jpg"]), ["pdf", "zip"])
        with mock.patch.dict(os.environ, {"CORE_TEST_LIST": " , . "}), self.assertRaises(ImproperlyConfigured):
            env_list("CORE_TEST_LIST", ["jpg"])

    def test_str(self):
        self.assertEqual(env_str("CORE_TEST_MISSING", "numeric", choice_list=["numeric", "yandex"]), "numeric")
        with mock.patch.dict(os.environ, {"CORE_TEST_VALUE": "google"}), self.assertRaisesMessage(ImproperlyConfigured, "CORE_TEST_VALUE"):
            env_str("CORE_TEST_VALUE", "numeric", choice_list=["numeric", "yandex"])


class EnvSettingsTest(SimpleTestCase):
    def test_template_lists_every_setting(self):
        # .env.txt — список настроек для администратора: новая настройка без строки в нём — ошибка
        template = (settings.BASE_DIR.parent / ".env.txt").read_text(encoding="utf-8")
        self.assertTrue(core_env.SETTING_LIST)
        self.assertEqual([item.name for item in core_env.SETTING_LIST if item.name not in template], [])

    def test_command_hides_keys(self):
        with mock.patch.object(core_env, "SETTING_LIST", [
            core_env.Setting("FORM_FILE_SIZE_MAX_MB", 20, 10, True, False),
            core_env.Setting("FORM_SMARTCAPTCHA_SERVER_KEY", "secret-key", "", True, True),
        ]):
            out = io.StringIO()
            call_command("env_settings", stdout=out)
        self.assertIn("FORM_FILE_SIZE_MAX_MB = 20  (.env, по умолчанию 10)", out.getvalue())
        self.assertIn("FORM_SMARTCAPTCHA_SERVER_KEY = задан", out.getvalue())
        self.assertNotIn("secret-key", out.getvalue())
