"""Файл сгенерирован автоматически командой manage.py sync_async_models.

Не редактировать: источник схемы — models.py этого же модуля, правки затрёт
следующая генерация. После изменения моделей: makemigrations → sync_async_models.
Когда файл менялся и почему — в истории git.
"""
from tortoise import fields
from tortoise.models import Model


class PageCategory(Model):
    """Рубрика блога: открывается по своему адресу со списком статей."""

    id = fields.BigIntField(primary_key=True)
    slug = fields.CharField(max_length=200, unique=True)
    seo_title = fields.CharField(max_length=250, default="")
    seo_description = fields.CharField(max_length=500, default="")
    is_indexed = fields.BooleanField(default=True)
    date_add = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)
    name = fields.CharField(max_length=200, default="")
    parent = fields.ForeignKeyField("models.PageCategory", related_name="child_set", on_delete=fields.NO_ACTION, null=True)
    description = fields.TextField(default="")
    sort_order = fields.IntField(default=100)
    is_active = fields.BooleanField(default=True)

    class Meta:
        table = "page_pagecategory"
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"PageCategory {self.pk}"


class PageImage(Model):
    """Картинка для страниц: обложки и картинки в тексте. Лежит в media/, открыта всем."""

    id = fields.BigIntField(primary_key=True)
    file = fields.CharField(max_length=300, default="")
    original_name = fields.CharField(max_length=255, default="")
    alt = fields.CharField(max_length=255, default="")
    size = fields.IntField(default=0)
    date_add = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "page_pageimage"
        ordering = ['-id']

    def __str__(self):
        return f"PageImage {self.pk}"


class Page(Model):
    """Страница сайта. С рубрикой — статья блога."""

    id = fields.BigIntField(primary_key=True)
    slug = fields.CharField(max_length=200, unique=True)
    seo_title = fields.CharField(max_length=250, default="")
    seo_description = fields.CharField(max_length=500, default="")
    is_indexed = fields.BooleanField(default=True)
    date_add = fields.DatetimeField(auto_now_add=True)
    date_modified = fields.DatetimeField(auto_now=True)
    category = fields.ForeignKeyField("models.PageCategory", related_name="page_set", on_delete=fields.NO_ACTION, null=True)
    title = fields.CharField(max_length=250, default="")
    excerpt = fields.TextField(default="")
    content_md = fields.TextField(default="")
    content_html = fields.TextField(default="")
    cover = fields.ForeignKeyField("models.PageImage", related_name=False, on_delete=fields.NO_ACTION, null=True)
    is_published = fields.BooleanField(default=False)
    date_published = fields.DatetimeField(null=True, db_index=True)

    class Meta:
        table = "page_page"
        ordering = ['-date_published', '-id']

    def __str__(self):
        return f"Page {self.pk}"


class PageRedirect(Model):
    """Старый адрес на сайте → новый, постоянный редирект. Сайт спрашивает о нём, только когда
по адресу ничего нет: живую страницу редирект не перекроет."""

    id = fields.BigIntField(primary_key=True)
    path_from = fields.CharField(max_length=500, unique=True)
    path_to = fields.CharField(max_length=500, default="")
    date_add = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "page_pageredirect"
        ordering = ['-id']

    def __str__(self):
        return f"PageRedirect {self.pk}"
