"""Сторож правила денег (back/CLAUDE.md, «Стандартные поля API»): поле DecimalField отдаёт ровно decimal_places знаков."""
from decimal import Decimal

from django.test import SimpleTestCase
from tortoise import fields


class DecimalFieldTest(SimpleTestCase):
    def setUp(self):
        self.price = fields.DecimalField(max_digits=12, decimal_places=2)

    def test_two_places(self):
        """Нули не срезаны (tortoise-orm 1.1.9): «100.00», а не «1E+2» — в ответ как есть, без quantize."""
        self.assertEqual(str(self.price.to_python_value(Decimal("100.00"))), "100.00")
        self.assertEqual(str(self.price.to_python_value(Decimal("990.5"))), "990.50")

    def test_bankers_rounding(self):
        """Лишние знаки (чтение, create()) Tortoise округляет по-банковски — своё посчитанное округлять самим, ROUND_HALF_UP."""
        self.assertEqual(str(self.price.to_python_value(Decimal("84.925"))), "84.92")
        self.assertEqual(str(self.price.to_python_value(Decimal("84.935"))), "84.94")
