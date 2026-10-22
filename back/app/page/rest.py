from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.pagination import ListOut, Pagination, paginate, sort_queryset
from core.schemas import MessageOut
from page import services
from page.schemas import (
    PageCategoryOut,
    PageDetailOut,
    PageListFilter,
    PageListOut,
    PageRedirectOut,
    ResolveOut,
    SitemapOut,
)

router = APIRouter()

NOT_FOUND = {404: {"model": MessageOut, "description": "Не найдено, не опубликовано или скрыто"}}


@router.get("/category/info", response_model=list[PageCategoryOut], summary="Справочник рубрик",
            description="Без авторизации. Показываемые на сайте рубрики в порядке из админки — для меню "
                        "и фильтра ленты. У каждой рубрики свой адрес в корне сайта: `path`.")
async def category_info():
    return await services.category_list()


@router.get("/list", response_model=ListOut[PageListOut], summary="Лента блога",
            responses={406: {"model": MessageOut, "description": "Сортировка по полю, которого нет в списке"}},
            description="Без авторизации. Опубликованные статьи — страницы с рубрикой. Отдельные страницы "
                        "без рубрики в ленту не попадают, их открывают по адресу.\n\n"
                        "Фильтры: `category_slug` — слаг рубрики (справочник `/category/info`), "
                        "`search` — по заголовку и анонсу.\n\n"
                        "Сортировка `sort`: `date_published`, `title`, `id`, префикс `-` — по убыванию. "
                        "По умолчанию сначала новые.")
async def page_list(
    pagination: Pagination,
    filters: Annotated[PageListFilter, Depends(PageListFilter.query)],
    sort: str = Query("-date_published", description="date_published, title, id; «-» — по убыванию"),
):
    queryset = sort_queryset(filters.apply(services.feed_queryset()), sort, ["date_published", "title", "id"])
    return await paginate(queryset, pagination)


@router.get("/detail/{slug}", response_model=PageDetailOut, summary="Страница или статья по слагу",
            responses=NOT_FOUND,
            description="Без авторизации. Слаг уникален на весь сайт, поэтому одинаково отдаёт и статью "
                        "из рубрики, и отдельную страницу. `path` — готовый адрес на сайте, SEO-поля уже "
                        "с подставленными запасными значениями.")
async def page_detail(slug: str):
    return await services.get_page(slug)


@router.get("/resolve/{slug}", response_model=ResolveOut, summary="Что лежит по адресу /{slug}",
            description="Без авторизации. Для страницы сайта вида `/{slug}`: одним запросом узнать, рубрика это "
                        "или отдельная страница. `type=none` — ничего нет, фронт показывает 404.\n\n"
                        "Свои статические страницы фронт проверяет раньше: они важнее слагов из админки.")
async def resolve(slug: str):
    return await services.resolve(slug)


@router.get("/redirect", response_model=PageRedirectOut, summary="Куда переехал старый адрес",
            responses={404: {"model": MessageOut, "description": "Редиректа с этого адреса нет"}},
            description="Без авторизации. Сайт спрашивает, когда по адресу ничего нет: старый адрес из раздела "
                        "«Редиректы» админки — `path_to`, куда вести постоянным редиректом (301). Адрес можно "
                        "передать как пришёл — с «/» в конце, кириллицу процентами: сравнивается только путь.")
async def redirect(path: str = Query(..., max_length=2000, description="Путь от корня сайта: /news/staraya-statya.html")):
    return await services.get_redirect(path)


@router.get("/sitemap", response_model=SitemapOut, summary="Адреса для sitemap.xml",
            description="Без авторизации. Все видимые рубрики и страницы, открытые для поисковиков, "
                        "с датой изменения. Адреса без домена: фронт добавляет домен, склеивает со своими "
                        "страницами и списками других модулей и отдаёт `/sitemap.xml`.")
async def sitemap():
    item_list = await services.sitemap_item_list()
    return {"items": item_list, "total": {"count": len(item_list)}}
