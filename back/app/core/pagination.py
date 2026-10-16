"""Пагинация и сортировка списков API.

Формат ответа общий для всех списков с пагинацией — фронт разбирает их одинаково:

    {"items": [{"row_number": 1, ...}, ...], "total": {"count": 120}}

Эндпоинт:

    @router.get("/list", response_model=ListOut[ProductOut])
    async def product_list(pagination: Pagination, sort: str = "-id"):
        queryset = sort_queryset(Product.all(), sort, ["id", "title", "price"])
        return await paginate(queryset, pagination)
"""
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from tortoise.queryset import QuerySet

ItemT = TypeVar("ItemT")


class PaginationParams(BaseModel):
    # Граница — от мусорных адресов: смещение за пределом bigint — ошибка базы и 500 вместо 422
    page: int = Field(1, ge=1, le=10_000, description="Номер страницы")
    row: int = Field(20, ge=1, le=1000, description="Записей на странице")


class Total(BaseModel):
    count: int = Field(..., description="Всего записей с учётом фильтров")


class ListOut(BaseModel, Generic[ItemT]):
    items: list[ItemT] = Field(..., description="Записи страницы")
    total: Total = Field(..., description="Итоги по всей выборке")


#: Параметры `page` и `row` как зависимость: `pagination: Pagination` в сигнатуре эндпоинта
Pagination = Annotated[PaginationParams, Depends()]


def sort_queryset(queryset: QuerySet, sort: str | None, allowed: list[str]) -> QuerySet:
    """Сортировка по полю из списка разрешённых. Префикс «-» — по убыванию.

    Второй ключ — id, новые первыми: равные записи база отдаёт в любом порядке, и на границе
    страниц одни повторялись бы, а другие пропадали.
    """
    if not sort:
        return queryset
    if sort.removeprefix("-") not in allowed:
        raise HTTPException(406, f"Сортировка по «{sort}» недоступна. Можно: {', '.join(allowed)}")
    return queryset.order_by(sort, "-id")


async def paginate(queryset: QuerySet, pagination: PaginationParams) -> dict:
    """Страница записей и общее количество. Двумя запросами: count и сама выборка.

    Каждая запись получает row_number — сквозной номер по всей выборке, а не по странице
    (в схеме ответа нужно поле row_number). Записи уходят как есть: по схеме их один раз
    проверяет FastAPI, по response_model эндпоинта.
    """
    count = await queryset.count()
    offset = (pagination.page - 1) * pagination.row
    items = await queryset.offset(offset).limit(pagination.row)
    for number, item in enumerate(items, start=offset + 1):
        item.row_number = number
    return {"items": items, "total": {"count": count}}
