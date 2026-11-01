import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.contrib import admin
from django.core import mail
from django.utils import timezone
from fastapi import HTTPException
from tortoise.transactions import in_transaction

from core.broker import broker
from core.tests.api import ApiTestCase
from user import conf, models, models_async, services
from user.tests.create import PASSWORD, auth_header, create_user


class RegistrationConsentTest(ApiTestCase):
    def send(self, **values):
        return self.api.post('/api/user/register', json={'email': 'reader@example.com', 'first_name': 'Читатель', **values})

    def pending(self, **values):
        return create_user(email='reader@example.com', is_confirmed=False, is_active=False, first_name='Первое имя', **values)

    def test_default_info_legacy_body_and_false(self):
        self.assertIs(conf.CONSENT_REQUIRED, False)
        self.assertEqual(self.api.get('/api/user/registration/info').json(), {'is_consent_required': False})
        for values in ({}, {'consent': False, 'email': 'other@example.com'}):
            self.assertEqual(self.send(**values).status_code, 200)
        self.wait_tasks()
        self.assertEqual(models.CustomUser.objects.count(), 2)
        for user in models.CustomUser.objects.all():
            self.assertIsNone(user.date_consent)
            self.assertIsNone(user.consent_ip)

    def test_info_public_without_db_or_cookies_and_post_checks_same_requirement(self):
        for required in (False, True):
            with self.subTest(required=required), patch.object(conf, 'CONSENT_REQUIRED', required):
                with patch.object(models_async.CustomUser, 'get_or_none', side_effect=AssertionError('DB')):
                    response = self.api.get('/api/user/registration/info', headers={'authorization': 'Bearer invalid'})
                self.assertEqual(response.json(), {'is_consent_required': required})
                self.assertNotIn('set-cookie', response.headers)
                if required:
                    for values in ({}, {'consent': False}):
                        response = self.send(**values)
                        self.assertEqual(response.status_code, 422)
                        self.assertEqual(response.json()['full_error'][0]['loc'], 'consent')
                    self.assertFalse(models.CustomUser.objects.filter(email='reader@example.com').exists())
                self.assertEqual(self.send(email=f'{required}@example.com', consent=True).status_code, 200)
                self.assertIsNotNone(models.CustomUser.objects.get(email=f'{required}@example.com'.lower()).date_consent)

    def test_required_pending_needs_new_action_even_with_old_fact(self):
        date = timezone.now() - timedelta(days=1)
        user = self.pending(date_consent=date, consent_ip='192.0.2.1')
        with patch.object(conf, 'CONSENT_REQUIRED', True):
            for values in ({}, {'consent': False}):
                self.assertEqual(self.send(**values).status_code, 422)
        user.refresh_from_db()
        self.assertEqual((user.date_consent, user.consent_ip, user.first_name), (date, '192.0.2.1', 'Первое имя'))
        self.assertIsNone(user.confirmation_code)

    def test_successful_repeat_preserves_or_updates_fact_and_never_name(self):
        date = timezone.now() - timedelta(days=1)
        user = self.pending(date_consent=date, consent_ip='192.0.2.1')
        for values in ({}, {'consent': False}, {'consent': True}):
            models.CustomUser.objects.filter(id=user.id).update(confirmation_code_created_at=None)
            self.assertEqual(self.send(**values).status_code, 200)
            user.refresh_from_db()
            self.assertEqual(user.first_name, 'Первое имя')
            if values.get('consent'):
                self.assertGreater(user.date_consent, date)
                self.assertIsNone(user.consent_ip)  # testclient — не IP
            else:
                self.assertEqual((user.date_consent, user.consent_ip), (date, '192.0.2.1'))

    def test_interval_and_queue_failure_do_not_rewrite_fact(self):
        date = timezone.now() - timedelta(days=1)
        user = self.pending(date_consent=date, consent_ip='192.0.2.1', confirmation_code='123456', confirmation_code_created_at=timezone.now())
        self.assertEqual(self.send(consent=True).status_code, 406)
        user.refresh_from_db()
        self.assertEqual((user.date_consent, user.consent_ip, user.confirmation_code), (date, '192.0.2.1', '123456'))
        models.CustomUser.objects.filter(id=user.id).update(confirmation_code_created_at=None)
        with patch.object(services.send_code, 'kiq', new_callable=AsyncMock, side_effect=RuntimeError('synthetic queue failure')):
            with self.assertRaisesMessage(RuntimeError, 'synthetic queue failure'):
                self.send(consent=True)
        user.refresh_from_db()
        self.assertEqual((user.date_consent, user.consent_ip, user.confirmation_code), (date, '192.0.2.1', '123456'))
        self.assertIsNone(user.confirmation_code_created_at)
        models.CustomUser.objects.all().delete()
        with patch.object(services.send_code, 'kiq', new_callable=AsyncMock, side_effect=RuntimeError('synthetic queue failure')):
            with self.assertRaises(RuntimeError):
                self.send(consent=True)
        self.assertFalse(models.CustomUser.objects.exists())

    def test_confirmed_and_disabled_unchanged_and_no_private_fields_in_me(self):
        date = timezone.now() - timedelta(days=1)
        for active in (True, False):
            user = create_user(email=f'{active}@example.com', is_active=active, date_consent=date, consent_ip='192.0.2.1')
            for values in ({}, {'consent': True}):
                response = self.send(email=user.email, **values)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['full_error'][0]['loc'], 'email')
            user.refresh_from_db()
            self.assertEqual((user.date_consent, user.consent_ip, user.is_active, user.is_confirmed), (date, '192.0.2.1', active, True))
            if active:
                data = self.api.get('/api/user/me', headers=auth_header(user)).json()
                self.assertNotIn('date_consent', data)
                self.assertNotIn('consent_ip', data)
        self.assertEqual(mail.outbox, [])

    def test_non_boolean_rejected(self):
        for value in ('true', 'false', 1, 0, None):
            self.assertEqual(self.send(consent=value).status_code, 422)
        self.assertFalse(models.CustomUser.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_true_uses_server_time_request_host_and_not_xff(self):
        for index, (host, expected) in enumerate([('192.0.2.9', '192.0.2.9'), ('2001:db8::9', '2001:db8::9'), ('testclient', None), (None, None)]):
            with self.subTest(host=host), patch.object(self.api._transport, 'client', None if host is None else (host, 4321)):
                api = self.api
                before = timezone.now()
                response = api.post('/api/user/register', json={'email': f'ip{index}@example.com', 'consent': True, 'date_consent': '2000-01-01', 'consent_ip': '203.0.113.1'}, headers={'x-forwarded-for': '203.0.113.100'})
                self.assertEqual(response.status_code, 200)
                user = models.CustomUser.objects.get(email=f'ip{index}@example.com')
                self.assertEqual(user.consent_ip, expected)
                self.assertGreaterEqual(user.date_consent, before)
                self.assertLessEqual(user.date_consent, timezone.now())
                api.portal.call(broker.wait_all)

    def test_resend_activate_reset_preserve_fact(self):
        date = timezone.now() - timedelta(days=1)
        user = self.pending(date_consent=date, consent_ip='192.0.2.1')
        self.assertEqual(self.api.post('/api/user/activate/resend', json={'email': user.email}).status_code, 200)
        user.refresh_from_db()
        response = self.api.post('/api/user/activate', json={'email': user.email, 'code': user.confirmation_code, 'password': PASSWORD, 'password_confirm': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api.post('/api/user/password/reset', json={'email': user.email}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(self.api.post('/api/user/password/reset/confirm', json={'email': user.email, 'code': user.confirmation_code, 'password_new': PASSWORD, 'password_new_confirm': PASSWORD}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual((user.date_consent, user.consent_ip), (date, '192.0.2.1'))

    def test_repeat_waiting_for_concurrent_confirmation_cannot_change_fact(self):
        date = timezone.now() - timedelta(days=1)
        user = self.pending(date_consent=date, consent_ip='192.0.2.1')
        async def scenario():
            locked, repeating = asyncio.Event(), asyncio.Event()
            async def confirmation():
                async with in_transaction():
                    current = await models_async.CustomUser.select_for_update().get(id=user.id)
                    locked.set()
                    await repeating.wait()
                    # Дать повтору дойти до реального блокирующего SELECT.
                    await asyncio.sleep(0.05)
                    self.assertFalse(repeat_task.done())
                    current.is_confirmed, current.is_active = True, True
                    await current.save(update_fields=['is_confirmed', 'is_active'])
            async def repeat():
                await locked.wait()
                repeating.set()
                with self.assertRaises(HTTPException) as caught:
                    await services.register(user.email, 'Подмена', '', True, '203.0.113.5')
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(caught.exception.detail['full_error'][0]['loc'], 'email')
            confirm_task = asyncio.create_task(confirmation())
            repeat_task = asyncio.create_task(repeat())
            await asyncio.wait_for(asyncio.gather(confirm_task, repeat_task), 5)
        self.api.portal.call(scenario)
        user.refresh_from_db()
        self.assertTrue(user.is_confirmed)
        self.assertTrue(user.is_active)
        self.assertEqual((user.date_consent, user.consent_ip, user.first_name), (date, '192.0.2.1', 'Первое имя'))
        self.assertIsNone(user.confirmation_code)

    def test_manual_user_has_no_fact_and_admin_cannot_edit(self):
        user = create_user()
        self.assertIsNone(user.date_consent)
        self.assertIsNone(user.consent_ip)
        model_admin = admin.site._registry[models.CustomUser]
        for field in ('date_consent', 'consent_ip'):
            self.assertIn(field, model_admin.readonly_fields)
            self.assertNotIn(field, model_admin.add_form.base_fields)

    def test_service_itself_enforces_required_consent(self):
        with patch.object(conf, 'CONSENT_REQUIRED', True), self.assertRaises(HTTPException) as caught:
            self.api.portal.call(services.register, 'reader@example.com', 'Читатель', '')
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(caught.exception.detail['full_error'][0]['loc'], 'consent')
        self.assertFalse(models.CustomUser.objects.exists())

    def test_resend_activate_reset_do_not_invent_fact(self):
        user = self.pending()
        self.assertEqual(self.api.post('/api/user/activate/resend', json={'email': user.email}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(self.api.post('/api/user/activate', json={'email': user.email, 'code': user.confirmation_code, 'password': PASSWORD, 'password_confirm': PASSWORD}).status_code, 200)
        self.assertEqual(self.api.post('/api/user/password/reset', json={'email': user.email}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(self.api.post('/api/user/password/reset/confirm', json={'email': user.email, 'code': user.confirmation_code, 'password_new': PASSWORD, 'password_new_confirm': PASSWORD}).status_code, 200)
        user.refresh_from_db()
        self.assertIsNone(user.date_consent)
        self.assertIsNone(user.consent_ip)
