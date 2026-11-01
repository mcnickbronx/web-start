"""Новая миграция не создаёт согласие за старые строки и допускает старые INSERT."""
import uuid

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ConsentMigrationTest(TransactionTestCase):
    old = [('form', '0008_formtype_is_telegram_contacts_formtype_telegram_chat_and_more'), ('user', '0004_customuser_is_confirmed')]
    new = [('form', '0009_formrequest_consent_ip_formrequest_date_consent_and_more'), ('user', '0005_customuser_consent_ip_customuser_date_consent')]

    def test_existing_rows_and_database_default_and_reverse(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        executor.migrate(self.old)
        apps = executor.loader.project_state(self.old).apps
        FormType = apps.get_model('form', 'FormType')
        User = apps.get_model('user', 'CustomUser')
        Request = apps.get_model('form', 'FormRequest')
        form = FormType.objects.create(name='Старая форма', code='old', telegram_chat='-1234', is_telegram_contacts=True)
        user = User.objects.create(email='old@example.com', password='!', first_name='Читатель', is_active=False, is_confirmed=False)
        request = Request.objects.create(form_type=form, user=user, name='Анна', phone='123', message='Старая заявка', token_id=uuid.uuid4())
        old_records = [(record, {field.attname: getattr(record, field.attname) for field in record._meta.concrete_fields}) for record in (form, request, user)]
        executor = MigrationExecutor(connection)
        executor.migrate(self.new)
        apps_new = executor.loader.project_state(self.new).apps
        for record, snapshot in old_records:
            current = apps_new.get_model(record._meta.app_label, record._meta.model_name).objects.get(pk=record.pk)
            self.assertEqual({name: getattr(current, name) for name in snapshot}, snapshot)
        form_new = apps_new.get_model('form', 'FormType').objects.get(id=form.id)
        request_new = apps_new.get_model('form', 'FormRequest').objects.get(id=request.id)
        user_new = apps_new.get_model('user', 'CustomUser').objects.get(id=user.id)
        self.assertEqual((form_new.telegram_chat, form_new.is_telegram_contacts, form_new.is_consent_required), ('-1234', True, False))
        self.assertEqual((request_new.name, request_new.phone, request_new.message, request_new.user_id), ('Анна', '123', 'Старая заявка', user.id))
        self.assertEqual((user_new.email, user_new.first_name, user_new.is_confirmed), ('old@example.com', 'Читатель', False))
        for record in (request_new, user_new):
            self.assertIsNone(record.date_consent)
            self.assertIsNone(record.consent_ip)
        # Историческая модель не знает новой колонки: INSERT как у ещё работающего старого процесса.
        inserted = FormType.objects.create(name='Старый процесс', code='old-process')
        self.assertFalse(apps_new.get_model('form', 'FormType').objects.get(id=inserted.id).is_consent_required)
        self.assertEqual(len([node for node in executor.loader.graph.leaf_nodes() if node[0] == 'form']), 1)
        executor = MigrationExecutor(connection)
        executor.migrate(self.old)
        old_apps = executor.loader.project_state(self.old).apps
        self.assertEqual(old_apps.get_model('form', 'FormRequest').objects.get(id=request.id).message, 'Старая заявка')
        self.assertEqual(old_apps.get_model('form', 'FormType').objects.get(id=form.id).telegram_chat, '-1234')
        MigrationExecutor(connection).migrate(latest)
