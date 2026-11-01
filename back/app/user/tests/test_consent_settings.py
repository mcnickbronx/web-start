import importlib.util
import io
import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase

from core import env
from user import conf


class ConsentSettingsTest(SimpleTestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location('consent_test_settings', conf.__file__)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_missing_false_true_and_invalid_startup(self):
        with patch.object(env, 'SETTING_LIST', []), patch.dict(os.environ):
            os.environ.pop('USER_CONSENT_REQUIRED', None)
            self.assertIs(self.load().CONSENT_REQUIRED, False)
            for raw, expected in [('false', False), ('true', True)]:
                os.environ['USER_CONSENT_REQUIRED'] = raw
                self.assertIs(self.load().CONSENT_REQUIRED, expected)
            for raw in ('True', 'False', '1', 'yes', '', 'wrong'):
                os.environ['USER_CONSENT_REQUIRED'] = raw
                with self.subTest(raw=raw), self.assertRaisesMessage(ImproperlyConfigured, 'USER_CONSENT_REQUIRED'):
                    self.load()

    def test_env_settings_lists_documented_setting(self):
        with patch.object(env, 'SETTING_LIST', []), patch.dict(os.environ, {'USER_CONSENT_REQUIRED': 'true'}):
            self.assertIs(self.load().CONSENT_REQUIRED, True)
            output = io.StringIO()
            call_command('env_settings', stdout=output)
            self.assertIn('USER_CONSENT_REQUIRED = true', output.getvalue())
            self.assertIn('по умолчанию false', output.getvalue())
