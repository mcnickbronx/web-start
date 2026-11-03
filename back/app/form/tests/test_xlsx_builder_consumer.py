"""Прежнее действие админки заявок действительно использует общий сборщик XLSX."""
import io
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from core.xlsx import build_xlsx


class XlsxAdminConsumerTest(TestCase):
    def test_real_action_uses_builder_with_filtered_rows_and_html_adapter(self):
        from form.models import FormRequest
        from form.tests.create import create_form_request
        from user.tests.create import create_user

        manager = create_user(email='manager@example.com', is_staff=True)
        manager.user_permissions.add(Permission.objects.get(codename='view_formrequest'))
        self.client.force_login(manager)
        create_form_request(name='Не попадает', status='new')
        chosen = create_form_request(name='Анна', status='work', data={'note': '<ok>'})
        create_form_request(name='Борис', status='work', data={'note': '& <ok>'})
        modeladmin = admin.site._registry[FormRequest]
        with patch('core.xlsx.build_xlsx', wraps=build_xlsx) as builder, \
                patch.object(modeladmin, 'get_list_display', return_value=['name', 'status', 'data_display']):
            response = self.client.post(reverse('admin:form_formrequest_changelist') + '?status=work',
                                        {'action': 'export_xlsx', '_selected_action': [chosen.id], 'select_across': '1'})
            builder.assert_called_once()
        self.assertEqual(response.status_code, 200)
        try:
            sheet = load_workbook(io.BytesIO(b''.join(response.streaming_content))).active
        finally:
            response.close()
        self.assertEqual(list(sheet.values), [('Имя', 'Статус', 'Дополнительные поля'),
                                             ('Борис', 'В работе', '{\n  "note": "& <ok>"\n}'),
                                             ('Анна', 'В работе', '{\n  "note": "<ok>"\n}')])

    def test_action_requires_view_permission(self):
        from user.tests.create import create_user

        self.client.force_login(create_user(email='staff@example.com', is_staff=True))
        with patch('core.xlsx.build_xlsx', wraps=build_xlsx) as builder:
            response = self.client.post(reverse('admin:form_formrequest_changelist'),
                                        {'action': 'export_xlsx', '_selected_action': [1]})
            self.assertEqual(response.status_code, 403)
            builder.assert_not_called()
