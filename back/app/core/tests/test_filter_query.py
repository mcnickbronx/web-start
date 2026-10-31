"""Query-модели FastAPI: все ошибки сразу, соседние зависимости и изоляция запросов."""
import asyncio
from typing import Annotated

from django.test import SimpleTestCase
from fastapi import Depends, FastAPI, Query
from httpx2 import ASGITransport, AsyncClient
from pydantic import AliasChoices, ValidationError, model_validator
from starlette.testclient import TestClient

from core.filters import FilterField, FilterSchema
from core.pagination import Pagination


class QueryFilter(FilterSchema):
    count: int | None = FilterField("id__gte", alias="minimum", ge=1, description="Минимальный номер")
    id: list[int] | None = FilterField("id__in", description="Номера")

    @model_validator(mode="after")
    def check_selected(self):
        if self.count is not None and self.id and min(self.id) < self.count:
            raise ValueError("Выбранный номер меньше минимального")
        return self


async def ordinary_query(value: str = Query("default", validation_alias=AliasChoices("source", "origin"))):
    return value


class FilterQueryTest(SimpleTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.called = []

        @self.app.get("/list")
        async def item_list(pagination: Pagination, filters: Annotated[QueryFilter, Depends(QueryFilter.query)], source: Annotated[str, Depends(ordinary_query)]):
            self.called.append(True)
            return {"filters": filters.model_dump(), "page": pagination.page, "source": source}

        self.api = self.enterContext(TestClient(self.app))

    def test_combined_errors_before_endpoint(self):
        response = self.api.get("/list?minimum=zero&mistake=x&page=abc&source=test")
        self.assertEqual(response.status_code, 422)
        errors = response.json()["detail"]
        self.assertEqual({tuple(error["loc"]): error["type"] for error in errors}, {
            ("query", "page"): "int_parsing", ("query", "minimum"): "int_parsing", ("query", "mistake"): "extra_forbidden",
        })
        self.assertEqual(self.called, [])
        response = self.api.get("/list?mistake=x")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.called, [])

    def test_alias_lists_constraints_and_validator(self):
        response = self.api.get("/list?minimum=2&id=2&id=3&page=2&row=10&source=test")
        self.assertEqual((response.status_code, response.json()), (200, {
            "filters": {"count": 2, "id": [2, 3]}, "page": 2, "source": "test",
        }))
        response = self.api.get("/list?minimum=0")
        self.assertEqual((response.status_code, response.json()["detail"][0]["loc"]), (422, ["query", "minimum"]))
        response = self.api.get("/list?minimum=3&id=2")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["query"])
        self.assertIn("Выбранный номер меньше минимального", response.json()["detail"][0]["msg"])
        response = self.api.get("/list?origin=alternate")
        self.assertEqual((response.status_code, response.json()["source"]), (200, "alternate"))

    def test_openapi_query_model_fields(self):
        operation = self.app.openapi()["paths"]["/list"]["get"]
        self.assertNotIn("requestBody", operation)
        fields = {field["name"]: field for field in operation["parameters"]}
        self.assertEqual(set(fields), {"minimum", "id", "page", "row", "source"})
        self.assertTrue(all(field["in"] == "query" for field in fields.values()))
        self.assertEqual(fields["minimum"]["description"], "Минимальный номер")
        self.assertEqual(fields["minimum"]["schema"]["anyOf"][0]["minimum"], 1)
        self.assertEqual(fields["id"]["schema"]["anyOf"][0]["type"], "array")

    def test_context_reset_after_success_and_error(self):
        async def requests():
            async with AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test") as client:
                for query in ("?source=allowed", "?minimum=bad&source=allowed"):
                    response = await client.get("/list" + query)
                    self.assertEqual(response.status_code, 422 if "bad" in query else 200)
                    # Вне запроса source больше не соседняя зависимость фильтра.
                    with self.assertRaises(ValidationError):
                        QueryFilter.model_validate({"source": "must-not-leak"})
        asyncio.run(requests())

    def test_concurrent_routes_keep_their_query_names(self):
        class OtherFilter(FilterSchema):
            text: str | None = FilterField("title")

        async def requests():
            first_started, second_started, first_finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

            async def first_pause():
                first_started.set()
                await second_started.wait()

            async def second_pause():
                await first_started.wait()
                second_started.set()
                await first_finished.wait()

            app = FastAPI()

            @app.get("/first")
            async def first(filters: Annotated[QueryFilter, Depends(QueryFilter.query)], pause: Annotated[None, Depends(first_pause)], other: Annotated[OtherFilter, Depends(OtherFilter.query)], first_only: str = ""):
                first_finished.set()
                return [filters.count, other.text, first_only]

            @app.get("/second")
            async def second(other: Annotated[OtherFilter, Depends(OtherFilter.query)], pause: Annotated[None, Depends(second_pause)], filters: Annotated[QueryFilter, Depends(QueryFilter.query)], second_only: str = ""):
                return [filters.count, other.text, second_only]

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                responses = await asyncio.wait_for(asyncio.gather(
                    client.get("/first?minimum=2&text=one&first_only=first"),
                    client.get("/second?minimum=3&text=two&second_only=second"),
                ), timeout=5)
                self.assertEqual([(r.status_code, r.json()) for r in responses], [(200, [2, "one", "first"]), (200, [3, "two", "second"])])
        asyncio.run(requests())
