from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone
from fastapi import HTTPException

from core.consent import consent_stamp


class ConsentTest(SimpleTestCase):
    def test_required_accepts_only_true(self):
        for value in (False, None, 0, 1, 'true', 'false'):
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                consent_stamp(value, True, '127.0.0.1')
            self.assertEqual(caught.exception.status_code, 422)
            self.assertEqual(caught.exception.detail['full_error'][0]['loc'], 'consent')
        for value in (False, None, 0, 1, 'true'):
            self.assertEqual(consent_stamp(value, False, '127.0.0.1'), (None, None))

    def test_server_time_and_valid_ip_only(self):
        now = timezone.now()
        for raw, expected in [('192.0.2.5', '192.0.2.5'), ('2001:0db8::1', '2001:db8::1'), (None, None), ('testclient', None), ('', None)]:
            with self.subTest(raw=raw), patch('core.consent.timezone.now', return_value=now):
                date, ip = consent_stamp(True, False, raw)
            self.assertEqual((date, ip), (now, expected))
            self.assertTrue(timezone.is_aware(date))
