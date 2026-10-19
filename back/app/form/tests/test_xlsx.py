"""Выгрузка списка заявок в Excel — действие core.xlsx.export_xlsx."""
import datetime
import io

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from form.tests.create import create_form_request
from user.tests.create import create_user


class ExportXlsxTest(TestCase):
    def setUp(self):
        # Менеджер, который заявки только смотрит: выгружает тот, кто видит список
        manager = create_user(email="manager@example.com", is_staff=True)
        manager.user_permissions.add(Permission.objects.get(codename="view_formrequest"))
        self.client.force_login(manager)

    def export(self, *form_request_list):
        response = self.client.post(reverse("admin:form_formrequest_changelist"), {
            "action": "export_xlsx", "_selected_action": [form_request.id for form_request in form_request_list],
        })
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        return load_workbook(io.BytesIO(b"".join(response.streaming_content))).active

    def test_columns_as_list(self):
        """Колонки и подписи — как в списке заявок; статус — подписью, дата — датой Excel, в порядке списка."""
        first, second = create_form_request(), create_form_request(name="Борис", status="work")
        rows = list(self.export(first, second).values)
        self.assertEqual(rows[0], ("Заявка", "Дата создания", "Форма", "Имя", "Телефон", "Email", "Канал", "Статус", "Письмо"))
        self.assertEqual(rows[1][0], f"Заявка №{second.id}")  # новые сверху, как в списке
        self.assertEqual(rows[1][2:5] + rows[1][7:], ("Обратный звонок", "Борис", "+79990001122", "В работе", "Ждёт отправки"))
        self.assertIsInstance(rows[1][1], datetime.datetime)
        self.assertEqual(len(rows), 3)

    def test_formula_is_text(self):
        """Имя-формула от посетителя — текстом: иначе Excel менеджера выполнит её при открытии."""
        name = '=HYPERLINK("http://example.com","Открыть")'
        cell = self.export(create_form_request(name=name))["D2"]
        self.assertEqual((cell.value, cell.data_type), (name, "s"))

    def test_control_characters(self):
        """Символы, недопустимые в xlsx (управляющий, U+FFFF), из текста посетителя убраны: файл открывается."""
        self.assertEqual(self.export(create_form_request(name="Ан\x0bна￿"))["D2"].value, "Анна")
