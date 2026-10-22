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
import inspect
from typing import Annotated, Any, ClassVar

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from tortoise.expressions import Q
from tortoise.queryset import QuerySet


def FilterField(q: str | list[str], description: str = "", **kwargs: Any) -> Any:
    """Поле фильтра: лукап Tortoise (`status`, `title__icontains`, `date_published__gte`, `status__in`);
    список лукапов — любой из них (ИЛИ). Остальные аргументы — как у Field: `max_length=200`."""
    return Field(None, description=description, json_schema_extra={"q": q}, **kwargs)


class FilterSchema(BaseModel):
    """Основа фильтра списка. Поля — через FilterField, в эндпоинт — `Depends(ИмяФильтра.query)`."""

    query: ClassVar[Any]  # зависимость FastAPI, своя у каждого подкласса — собирается ниже

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Зависимость с полями фильтра в сигнатуре: FastAPI проверит каждое и покажет в Swagger."""
        super().__pydantic_init_subclass__(**kwargs)
        parameter_list = [inspect.Parameter("request", inspect.Parameter.KEYWORD_ONLY, annotation=Request)]
        parameter_list += [
            inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=None,
                              annotation=Annotated[field.annotation, *field.metadata, Query(description=field.description)])
            for name, field in cls.model_fields.items()
        ]

        async def query(request: Request, **values: Any) -> FilterSchema:
            check_unknown_params(request)
            try:
                return cls(**values)
            except ValidationError as error:  # проверки всей схемы (свои валидаторы) — тоже 422, а не 500
                raise RequestValidationError([{**item, "loc": ("query", *item["loc"])} for item in error.errors()]) from None

        query.__signature__ = inspect.Signature(parameter_list)
        cls.query = query

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


def check_unknown_params(request: Request) -> None:
    """Параметр, которого эндпоинт не объявил (ни фильтр, ни page, row, sort), — 422."""
    known = _query_names(request.scope["route"].dependant)
    unknown = [name for name in request.query_params if name not in known]
    if unknown:
        raise RequestValidationError([
            {"type": "extra_forbidden", "loc": ("query", name), "msg": "Неизвестный параметр", "input": request.query_params[name]}
            for name in unknown
        ])


def _query_names(dependant: Any) -> set[str]:
    """Параметры запроса эндпоинта вместе с его зависимостями."""
    names = {param.alias for param in dependant.query_params}
    for sub in dependant.dependencies:
        names |= _query_names(sub)
    return names
