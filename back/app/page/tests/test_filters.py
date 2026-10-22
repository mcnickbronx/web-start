"""Фильтры списков из core.filters — на страницах шаблона: каждый оператор, пустой фильтр, неверное значение."""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import model_validator
from starlette.testclient import TestClient

from core.filters import FilterField, FilterSchema
from core.pagination import Pagination, paginate, sort_queryset
from core.tests.api import ApiTestCase
from page import models_async
from page.tests.create import create_article, create_page, create_page_category
from project.api import create_app


class PageFilter(FilterSchema):
    title: str | None = FilterField("title", description="Заголовок целиком")
    search: str | None = FilterField(["title__icontains", "excerpt__icontains"], description="По заголовку и анонсу", max_length=20)
    category_slug: str | None = FilterField("category__slug", description="Слаг рубрики")
    is_published: bool | None = FilterField("is_published", description="Опубликована")
    date_published_from: datetime | None = FilterField("date_published__gte", description="Опубликована с")
    date_published_to: datetime | None = FilterField("date_published__lte", description="Опубликована по")
    id: list[int] | None = FilterField("id__in", description="Только эти id")

    @model_validator(mode="after")
    def check_dates(self):
        if self.date_published_from and self.date_published_to and self.date_published_from > self.date_published_to:
            raise ValueError("Начало периода позже конца")
        return self


router = APIRouter()


@router.get("/api/test-filter/list")
async def page_list(pagination: Pagination, filters: Annotated[PageFilter, Depends(PageFilter.query)], sort: str = "title"):
    queryset = sort_queryset(filters.apply(models_async.Page.all()), sort, ["title"])
    return [page.title for page in (await paginate(queryset, pagination))["items"]]


class FilterTest(ApiTestCase):
    def setUp(self):
        app = create_app()
        app.include_router(router)
        self.api = self.enterContext(TestClient(app, base_url="https://testserver"))
        self.price = create_article("Цены на ремонт", excerpt="Сколько стоит", date_published=datetime(2026, 1, 10, tzinfo=UTC))
        self.company = create_page_category("Компания")
        create_article("Отзыв клиента", excerpt="Ремонт кухни за неделю", category=self.company, date_published=datetime(2026, 1, 20, tzinfo=UTC))
        self.contacts = create_page("Контакты", is_published=False)

    def get(self, **params):
        return self.api.get("/api/test-filter/list", params=params)

    def test_empty_filter(self):
        """Без параметров и с пустой строкой — весь список: пустое поле формы на сайте не прячет записи."""
        all_list = ["Контакты", "Отзыв клиента", "Цены на ремонт"]
        self.assertEqual(self.get().json(), all_list)
        self.assertEqual(self.get(title="", search="", category_slug="").json(), all_list)

    def test_each_operator(self):
        for params, title_list in [
            ({"title": "Контакты"}, ["Контакты"]),
            ({"title": "контакты"}, []),  # без лукапа — точное совпадение
            ({"search": "РЕМОНТ"}, ["Отзыв клиента", "Цены на ремонт"]),  # icontains, заголовок или анонс
            ({"category_slug": self.company.slug}, ["Отзыв клиента"]),  # через связь
            ({"is_published": "false"}, ["Контакты"]),
            ({"date_published_from": "2026-01-15T00:00:00Z"}, ["Отзыв клиента"]),  # gte
            ({"date_published_to": "2026-01-15T00:00:00Z"}, ["Цены на ремонт"]),  # lte
            ({"date_published_from": "2026-01-10T00:00:00Z", "date_published_to": "2026-01-20T00:00:00Z"}, ["Отзыв клиента", "Цены на ремонт"]),
            ({"id": [self.price.id, self.contacts.id]}, ["Контакты", "Цены на ремонт"]),  # in, параметр повторяется
            ({"search": "ремонт", "date_published_from": "2026-01-15T00:00:00Z"}, ["Отзыв клиента"]),  # поля — через И
        ]:
            with self.subTest(params):
                response = self.get(**params)
                self.assertEqual((response.status_code, response.json()), (200, title_list))

    def test_wrong_value(self):
        """Неверное значение — 422 у своего поля, в базу запрос не уходит."""
        for params, field in [
            ({"date_published_from": "abc"}, "date_published_from"),
            ({"is_published": "может быть"}, "is_published"),
            ({"id": "первый"}, "id"),
            ({"search": "р" * 21}, "search"),
        ]:
            with self.subTest(params):
                response = self.get(**params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual([error["loc"] for error in response.json()["full_error"]], [field])
        # своя проверка схемы — тоже 422 с её текстом, а не 500
        response = self.get(date_published_from="2026-01-20T00:00:00Z", date_published_to="2026-01-10T00:00:00Z")
        self.assertEqual((response.status_code, response.json()["message"]), (422, "Начало периода позже конца"))

    def test_unknown_param(self):
        """Опечатка в имени фильтра — 422, а не весь список. Параметры эндпоинта и пагинации — не лишние."""
        response = self.get(titel="Контакты")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["full_error"], [{"type": "extra_forbidden", "loc": "titel", "msg": "Дополнительные поля не допускаются"}])
        response = self.get(search="ремонт", page=1, row=1, sort="-title")
        self.assertEqual((response.status_code, response.json()), (200, ["Цены на ремонт"]))

    def test_swagger(self):
        """В Swagger — каждое поле фильтра отдельным параметром с описанием, без служебного request."""
        parameter_list = self.api.get("/api/openapi.json").json()["paths"]["/api/test-filter/list"]["get"]["parameters"]
        description_map = {parameter["name"]: parameter.get("description") for parameter in parameter_list}
        self.assertEqual(set(description_map), {"page", "row", "sort", *PageFilter.model_fields})
        self.assertEqual(description_map["search"], "По заголовку и анонсу")
