"""Фильтры списков API: поле схемы → лукап Tortoise.

    class ArticleFilter(FilterSchema):
        category_slug: str | None = FilterField("category__slug", description="Слаг рубрики")
        search: str | None = FilterField(["title__icontains", "excerpt__icontains"], description="По заголовку и анонсу")

    @router.get("/list", response_model=ListOut[ArticleOut])
    async def article_list(pagination: Pagination, filters: Annotated[ArticleFilter, Depends(ArticleFilter.query)]):
        return await paginate(filters.apply(Article.all()), pagination)

В Swagger каждое поле — отдельным параметром с описанием. Неверное значение — 422 у поля,
неизвестный параметр — тоже 422: опечатка в имени фильтра не должна молча отдавать весь список.
"""
from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import Annotated, Any, ClassVar

from fastapi import Depends, Query, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

_known_query: ContextVar[frozenset[str]] = ContextVar("filter_known_query", default=frozenset())


def FilterField(q: str | list[str], description: str = "", **kwargs: Any) -> Any:
    """Поле фильтра: лукап Tortoise (`status`, `title__icontains`, `date_published__gte`, `status__in`);
    список лукапов — любой из них (ИЛИ). Остальные аргументы — как у Field: `max_length=200`."""
    return Field(None, description=description, json_schema_extra={"q": q}, **kwargs)


class FilterSchema(BaseModel):
    """Основа фильтра списка. Поля — через FilterField, в эндпоинт — `Depends(ИмяФильтра.query)`."""

    model_config = ConfigDict(extra="forbid")

    query: ClassVar[Any]  # своя Query-модель у каждого подкласса

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """FastAPI сам разбирает поля модели, ограничения, списки и валидаторы."""
        super().__pydantic_init_subclass__(**kwargs)

        async def query(values: Annotated[cls, Query()], _context: Annotated[None, Depends(_query_context, scope="function")]) -> FilterSchema:
            return values

        cls.query = query

    @model_validator(mode="before")
    @classmethod
    def allow_sibling_query(cls, values: Any) -> Any:
        # Query-модель получает всю строку запроса. Чужие объявленные поля проверят их
        # собственные зависимости; остальные остаются для штатного extra="forbid".
        if isinstance(values, dict):
            sibling_names = _known_query.get() - _model_query_names(cls)
            return {name: value for name, value in values.items() if name not in sibling_names}
        return values

    def apply(self, queryset: QuerySet) -> QuerySet:
        """Запрос с заданными полями. Не задано или пустая строка — по этому полю не фильтруем."""
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if value is None or value == "":
                continue
            q = field.json_schema_extra["q"]
            lookup_list = [q] if isinstance(q, str) else q
            queryset = queryset.filter(Q(*[Q(**{lookup: value}) for lookup in lookup_list], join_type="OR"))
        return queryset


async def _query_context(request: Request) -> AsyncIterator[None]:
    """Имена соседних query-полей принадлежат только текущему запросу."""
    token = _known_query.set(frozenset(_query_names(request.scope["route"].dependant)))
    try:
        yield
    finally:
        _known_query.reset(token)


def _model_query_names(model: type[BaseModel]) -> set[str]:
    names = set()
    for name, field in model.model_fields.items():
        if model.model_config.get("validate_by_alias") is not False:
            names |= _field_query_names(field, name)
        if model.model_config.get("validate_by_alias") is False or model.model_config.get("validate_by_name") or model.model_config.get("populate_by_name"):
            names.add(name)
    return names


def _field_query_names(field: Any, name: str) -> set[str]:
    alias = field.validation_alias
    if isinstance(alias, str):
        return {alias}
    if isinstance(alias, AliasChoices) and all(isinstance(choice, str) for choice in alias.choices):
        return set(alias.choices)
    return {field.alias or name}


def _query_names(dependant: Any) -> set[str]:
    """Параметры запроса эндпоинта вместе с его зависимостями."""
    names = set()
    for param in dependant.query_params:
        annotation = param.field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            names |= _model_query_names(annotation)
        else:
            names |= _field_query_names(param.field_info, param.name)
    for sub in dependant.dependencies:
        names |= _query_names(sub)
    return names
