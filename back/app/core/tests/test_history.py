"""История изменений: что остаётся у core без модулей — разница «было → стало» и правило таблиц истории.

Админку и декоратор проверяют тесты модуля с историей (form/tests/test_history.py): без модели записи их не на чем гонять.
"""
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.test import SimpleTestCase

from core.history import HistoryModel, diff


class DiffTest(SimpleTestCase):
    def test_only_changed(self):
        """В разнице — только изменившиеся поля."""
        self.assertEqual(diff({"status": "new", "name": "Анна"}, {"status": "work", "name": "Анна"}), {"status": ["new", "work"]})

    def test_hidden(self):
        """Скрытое поле — только факт изменения; не изменилось — его нет вовсе."""
        before, after = {"phone": "+79990000000", "email": "a@example.com"}, {"phone": "+79991111111", "email": "a@example.com"}
        self.assertEqual(diff(before, after, hidden=["phone", "email"]), {"phone": None})

    def test_json_values(self):
        """Дата и деньги — строкой, как их сохранит JSON-поле changes."""
        before, after = {"day": date(2026, 10, 19), "price": Decimal("10.50")}, {"day": date(2026, 10, 20), "price": Decimal("10.50")}
        self.assertEqual(diff(before, after), {"day": ["2026-10-19", "2026-10-20"]})
        self.assertEqual(diff({"price": Decimal("10.50")}, {"price": Decimal("12.00")}), {"price": ["10.50", "12.00"]})


class HistoryTablesTest(SimpleTestCase):
    def test_history_in_record_module(self):
        """Таблица истории — в модуле записи, связь record — с related_name="history".

        Тогда `migrate <модуль> zero` уносит таблицу вместе с модулем, и в core ничего не остаётся;
        по related_name HistoryAdmin находит таблицу записи. Модулей с историей нет — проверять нечего.
        """
        for model in apps.get_models():
            if issubclass(model, HistoryModel):
                with self.subTest(model=model._meta.label):
                    record = model._meta.get_field("record")
                    self.assertEqual(record.related_model._meta.app_label, model._meta.app_label)
                    self.assertEqual(record.remote_field.related_name, "history")
