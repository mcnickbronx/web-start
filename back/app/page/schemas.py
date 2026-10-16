from datetime import datetime
from typing import Literal

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from core.pagination import Total
from page.services import build_path


class PageImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # В базе — путь внутри media/ (поле file), наружу — адрес от корня сайта
    url: str = Field(..., validation_alias="file", description="Адрес файла")
    alt: str = Field("", description="Описание картинки для alt")

    @field_validator("url")
    @classmethod
    def media_url(cls, value: str) -> str:
        return f"{settings.MEDIA_URL}{value}"


class PageCategoryOut(BaseModel):
    """Рубрика в справочнике и вложенным объектом у статьи."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID рубрики")
    name: str = Field(..., description="Название")
    slug: str = Field(..., description="Слаг")

    @computed_field(description="Адрес рубрики на сайте")
    @property
    def path(self) -> str:
        return build_path(self.slug)


class PageCategoryDetailOut(PageCategoryOut):
    description: str = Field("", description="Описание рубрики")
    seo_title: str = Field(..., description="SEO-заголовок, пустой заменён названием")
    seo_description: str = Field("", description="SEO-описание, пустое заменено описанием рубрики")
    is_indexed: bool = Field(True, description="Показывать поисковикам: false — noindex")

    @model_validator(mode="after")
    def fill_seo(self):
        self.seo_title = self.seo_title.strip() or self.name
        self.seo_description = self.seo_description.strip() or self.description
        return self


class PageBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID страницы")
    title: str = Field(..., description="Заголовок")
    slug: str = Field(..., description="Слаг")
    excerpt: str = Field("", description="Анонс")
    cover: PageImageOut | None = Field(None, description="Обложка")
    category: PageCategoryOut | None = Field(None, description="Рубрика; пусто — отдельная страница")
    date_published: datetime | None = Field(None, description="Дата публикации")

    @computed_field(description="Адрес на сайте")
    @property
    def path(self) -> str:
        return build_path(self.slug, self.category.slug if self.category else None)


class PageListOut(PageBaseOut):
    """Карточка статьи в ленте блога."""

    row_number: int = Field(0, description="Порядковый номер в выборке")


class PageDetailOut(PageBaseOut):
    """Страница целиком."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": {
        "id": 12, "title": "Как проверить договор за 10 минут", "slug": "kak-proverit-dogovor",
        "path": "/novosti/kak-proverit-dogovor", "excerpt": "Короткий чек-лист перед подписанием.",
        "cover": {"url": "/media/page/2026/09/a1b2c3d4e5f60718.webp", "alt": "Договор"},
        "category": {"id": 1, "name": "Новости", "slug": "novosti", "path": "/novosti"},
        "content_html": "<p>Текст статьи</p>", "seo_title": "Как проверить договор за 10 минут",
        "seo_description": "Короткий чек-лист перед подписанием.", "is_indexed": True,
        "date_published": "2026-09-27T10:00:00Z", "date_modified": "2026-09-27T10:00:00Z",
    }})

    content_html: str = Field("", description="Текст в HTML, уже очищен от опасной разметки")
    seo_title: str = Field(..., description="SEO-заголовок, пустой заменён заголовком")
    seo_description: str = Field("", description="SEO-описание, пустое заменено анонсом")
    is_indexed: bool = Field(True, description="Показывать поисковикам: false — noindex")
    date_modified: datetime = Field(..., description="Дата изменения")

    @model_validator(mode="after")
    def fill_seo(self):
        self.seo_title = self.seo_title.strip() or self.title
        self.seo_description = self.seo_description.strip() or self.excerpt
        return self


class ResolveOut(BaseModel):
    type: Literal["category", "page", "none"] = Field(..., description="Что лежит по адресу")
    category: PageCategoryDetailOut | None = Field(None, description="Рубрика, если type=category")
    page: PageDetailOut | None = Field(None, description="Страница, если type=page")


class PageRedirectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path_to: str = Field(..., description="Новый адрес на сайте, без домена")


class SitemapItemOut(BaseModel):
    loc: str = Field(..., description="Адрес на сайте, без домена")
    lastmod: datetime = Field(..., description="Дата изменения")


class SitemapOut(BaseModel):
    items: list[SitemapItemOut] = Field(..., description="Адреса")
    total: Total = Field(..., description="Итоги")
