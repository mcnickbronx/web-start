import asyncio
import importlib.util
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.db import connection, models
from django.test import TransactionTestCase
from django.test.utils import isolate_apps
from tortoise import Tortoise

from core.generator import TORTOISE_APP, ModuleWriter
from core.orm import connection_config


class RareFieldTypesTest(TransactionTestCase):
    @isolate_apps("core")
    def test_decimal_m2m_o2o_tortoise_writes_and_reads_django_tables(self):
        """Генератор на DecimalField, многие-ко-многим и один-к-одному: Tortoise пишет и читает таблицы, созданные Django."""
        class Tag(models.Model):
            name = models.CharField(max_length=50)

            class Meta:
                app_label = "core"
                db_table = "core_gentest_tag"

        class Product(models.Model):
            price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
            tags = models.ManyToManyField(Tag, related_name="products")

            class Meta:
                app_label = "core"
                db_table = "core_gentest_product"

        class Stock(models.Model):
            product = models.OneToOneField(Product, models.CASCADE, related_name="stock")
            count = models.IntegerField()

            class Meta:
                app_label = "core"
                db_table = "core_gentest_stock"

        model_list = [Tag, Product, Stock]
        writer = ModuleWriter()
        with patch("core.generator.is_generated", return_value=True):
            for model in model_list:
                writer.add_model(model)
        source = writer.render()
        # Запись и чтение не проверяют max_digits и default — их сверяем по тексту
        self.assertIn("fields.DecimalField(max_digits=12, decimal_places=2, default=Decimal(\"0.00\"))", source)

        # Обратный порядок: сначала таблицы со ссылками на другие
        tables = [Stock._meta.db_table, Product.tags.through._meta.db_table, Product._meta.db_table, Tag._meta.db_table]
        try:
            with connection.schema_editor() as editor:
                for model in model_list:
                    editor.create_model(model)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "gentest_models_async.py"
                path.write_text(source, encoding="utf-8")
                spec = importlib.util.spec_from_file_location("gentest_models_async", path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                try:
                    asyncio.run(self.write_and_read(module))
                finally:
                    del sys.modules[spec.name]
        finally:
            # IF EXISTS: создание могло упасть на середине, а --keepdb сохраняет базу между прогонами
            with connection.cursor() as cursor:
                for table in tables:
                    cursor.execute(f"DROP TABLE IF EXISTS {connection.ops.quote_name(table)}")

    async def write_and_read(self, module):
        await Tortoise.init(config={
            "connections": {"default": connection_config()},
            "apps": {TORTOISE_APP: {"models": [module.__name__], "default_connection": "default"}},
            "use_tz": True, "timezone": "UTC",
        })
        try:
            # Лишний тег — чтобы id тега и товара разошлись и перепутанные ключи M2M не прошли
            await module.Tag.create(name="Другой")
            tag = await module.Tag.create(name="Новинка")
            product = await module.Product.create(price=Decimal("990.10"))
            # Значение проходит через поле Tortoise: FloatField вместо DecimalField дал бы неточный float.
            # Прочитанное из базы не проверяет — asyncpg отдаёт numeric как Decimal при любом поле
            self.assertIsInstance(product.price, Decimal)
            await product.tags.add(tag)
            await module.Stock.create(product=product, count=3)
            await module.Product.filter(pk=product.pk).update(price=Decimal("1200.30"))
            product = await module.Product.get(pk=product.pk).prefetch_related("tags", "stock")
            self.assertEqual(product.price, Decimal("1200.30"))
            self.assertEqual([item.name for item in product.tags], ["Новинка"])
            self.assertEqual(product.stock.count, 3)
            self.assertEqual(await tag.products.all().count(), 1)
        finally:
            await Tortoise.close_connections()
