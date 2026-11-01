from unittest.mock import AsyncMock, patch

from django.contrib import admin
from django.core import mail
from django.utils import timezone
from django.test import RequestFactory
from user.tests.create import create_user

from core.broker import broker
from core.tests.api import ApiTestCase
from form import services
from form.schemas import FormRequestIn
from fastapi import HTTPException
from form.models import FormFile, FormRequest, FormType
from form.tests.create import create_form_type


class FormConsentTest(ApiTestCase):
    def open_form(self):
        return self.api.get('/api/form/detail/callback').json()

    def send(self, detail, **values):
        return self.api.post('/api/form/create', json={'token': detail['token'], 'phone': '+79990001122', **values})

    def test_default_and_legacy_body_without_fact(self):
        form = create_form_type()
        self.assertFalse(form.is_consent_required)
        self.assertIs(FormType._meta.get_field('is_consent_required').db_default, False)
        for values in ({}, {'consent': False}):
            detail = self.open_form()
            self.assertFalse(detail['is_consent_required'])
            self.assertEqual(self.send(detail, **values).status_code, 200)
        self.wait_tasks()
        self.assertEqual(FormRequest.objects.count(), 2)
        self.assertFalse(FormRequest.objects.exclude(date_consent=None, consent_ip=None).exists())

    def test_required_before_captcha_and_file_binding_same_token_succeeds(self):
        create_form_type(is_consent_required=True, is_captcha=True, is_file=True)
        detail = self.open_form()
        self.assertTrue(detail['is_consent_required'])
        upload = self.api.post('/api/form/upload-file', data={'token': detail['token']}, files={'file': ('test.pdf', b'%PDF-test', 'application/pdf')})
        file = FormFile.objects.get(id=upload.json()['file_id'])
        self.addCleanup(services.delete_files, [file])
        with patch.object(services, '_is_captcha_valid', new_callable=AsyncMock, return_value=True) as captcha:
            for values in ({}, {'consent': False}):
                response = self.send(detail, file_id_list=[str(file.id)], **values)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['full_error'][0]['loc'], 'consent')
                self.assertIn('Подтвердите согласие', response.json()['message'])
            captcha.assert_not_awaited()
            self.assertFalse(FormRequest.objects.exists())
            self.assertEqual(mail.outbox, [])
            file.refresh_from_db()
            self.assertIsNone(file.form_request_id)
            self.assertEqual(self.send(detail, consent=True, file_id_list=[str(file.id)]).status_code, 200)
            captcha.assert_awaited_once()
        self.wait_tasks()
        file.refresh_from_db()
        saved = FormRequest.objects.get()
        self.assertEqual(file.form_request_id, saved.id)
        self.assertTrue(timezone.is_aware(saved.date_consent))
        self.assertEqual(self.send(detail, consent=True).status_code, 406)

    def test_optional_true_server_time_and_client_host_only(self):
        create_form_type()
        for host, expected in [('192.0.2.4', '192.0.2.4'), ('2001:db8::2', '2001:db8::2'), ('testclient', None), (None, None)]:
            with self.subTest(host=host), patch.object(self.api._transport, 'client', None if host is None else (host, 123)):
                api = self.api
                detail = api.get('/api/form/detail/callback').json()
                before = timezone.now()
                response = api.post('/api/form/create', json={'token': detail['token'], 'phone': '123', 'consent': True, 'date_consent': '2000-01-01', 'consent_ip': '203.0.113.9'}, headers={'x-forwarded-for': '203.0.113.99'})
                self.assertEqual(response.status_code, 200)
                saved = FormRequest.objects.latest('id')
                self.assertEqual(saved.consent_ip, expected)
                self.assertGreaterEqual(saved.date_consent, before)
                self.assertLessEqual(saved.date_consent, timezone.now())
                api.portal.call(broker.wait_all)

    def test_non_boolean_rejected_without_side_effect(self):
        create_form_type()
        detail = self.open_form()
        for value in ('true', 'false', 1, 0, None):
            self.assertEqual(self.send(detail, consent=value).status_code, 422)
        self.assertFalse(FormRequest.objects.exists())
        self.assertEqual(self.send(detail, consent=True).status_code, 200)

    def test_trap_keeps_response_and_records_only_explicit_fact(self):
        create_form_type(is_consent_required=True, is_trap=True)
        for values, has_fact in [({}, False), ({'consent': False}, False), ({'consent': True}, True)]:
            response = self.send(self.open_form(), leave_empty='bot', **values)
            self.assertEqual(response.json(), {'message': 'Заявка отправлена'})
            saved = FormRequest.objects.latest('id')
            self.assertEqual(saved.status, 'spam')
            self.assertEqual(saved.date_consent is not None, has_fact)
        self.wait_tasks()
        self.assertEqual(mail.outbox, [])

    def test_manual_creation_and_admin_readonly(self):
        form = create_form_type(is_consent_required=True)
        saved = FormRequest.objects.create(form_type=form, phone='123')
        self.assertIsNone(saved.date_consent)
        self.assertIsNone(saved.consent_ip)
        model_admin = admin.site._registry[FormRequest]
        request = RequestFactory().get('/admin/')
        request.user = create_user(is_staff=True, is_superuser=True)
        for field in ('date_consent', 'consent_ip'):
            self.assertIn(field, model_admin.get_readonly_fields(None, saved))
            self.assertNotIn(field, model_admin.get_form(request, obj=None).base_fields)

    def test_service_itself_enforces_required_consent(self):
        create_form_type(is_consent_required=True)
        detail = self.open_form()
        with self.assertRaises(HTTPException) as caught:
            self.api.portal.call(services.create_request, FormRequestIn(token=detail['token'], phone='123'), None, '192.0.2.1')
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(caught.exception.detail['full_error'][0]['loc'], 'consent')
        self.assertFalse(FormRequest.objects.exists())
