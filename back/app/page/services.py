"""Логика модуля «Страницы».

Пишет в базу только админка (Django ORM, обычные функции), API только читает
(Tortoise, async-функции ниже). Поэтому HTML, анонс и дата публикации собираются
при сохранении в админке, а API отдаёт готовое.
"""
import io
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from PIL import Image, ImageOps
from tortoise.expressions import Q, Subquery

from core.slug import slugify_text
from page import conf, models, models_async
from page.markdown import excerpt_from_html, render_markdown

#: Адреса бэкенда и служебные адреса Nuxt: до страниц сайта они не доходят, рубрике и странице их
#: не отдать. Страниц фронта здесь нет — правило проще: адрес совпал со страницей фронта, показывается
#: страница фронта. Файлов вроде sitemap.xml тоже нет: в слаге не бывает точки
SLUG_RESERVED_LIST = ["admin", "api", "static", "media", "_nuxt"]

IMAGE_EXTENSION_LIST = ["jpg", "jpeg", "png", "gif", "webp"]


def build_path(slug: str, category_slug: str | None = None) -> str:
    """Адрес на сайте: /{рубрика}/{слаг} у статьи, /{слаг} у страницы и рубрики."""
    return f"/{category_slug}/{slug}" if category_slug else f"/{slug}"


def clean_path(value: str) -> str:
    """Адрес для редиректа — путь от корня сайта: без домена, параметров и «/» в конце, кириллица буквами,
    а не процентами. Так старый адрес из админки совпадёт с тем, что пришло от сайта, как бы его ни вставили."""
    return "/" + unquote(urlsplit(value.strip()).path).strip("/")


# --- Слаги (админка) -------------------------------------------------------------------

def _is_slug_taken(slug: str, model: type[models.PageCategory | models.Page], pk: int | None) -> bool:
    """Занят ли слаг другой рубрикой или страницей. Проверяем обе таблицы: рубрики и страницы
    делят корень сайта, а страницу API ищет по одному слагу."""
    category_list = models.PageCategory.objects.filter(slug=slug)
    page_list = models.Page.objects.filter(slug=slug)
    if model is models.PageCategory:
        category_list = category_list.exclude(pk=pk)
    else:
        page_list = page_list.exclude(pk=pk)
    return category_list.exists() or page_list.exists()


def clean_slug(model: type[models.PageCategory | models.Page], slug: str, source: str, pk: int | None) -> str:
    """Слаг для сохранения: введённый — проверяем, пустой — собираем из названия с суффиксом -2, -3…

    Ошибка — ValidationError с текстом для формы админки.
    """
    if slug:
        if slug in SLUG_RESERVED_LIST:
            raise ValidationError(f"Адрес /{slug} занят самим сайтом, выберите другой")
        if _is_slug_taken(slug, model, pk):
            raise ValidationError(f"Адрес /{slug} уже занят рубрикой или страницей")
        return slug

    base = slugify_text(source) or "page"
    candidate, counter = base, 1
    while candidate in SLUG_RESERVED_LIST or _is_slug_taken(candidate, model, pk):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


# --- Страница (админка) ----------------------------------------------------------------

def prepare_page(page: models.Page) -> None:
    """Перед сохранением: HTML из Markdown, анонс, если пуст, дата публикации, если не задана."""
    page.content_html = render_markdown(page.content_md)
    if not page.excerpt.strip():
        page.excerpt = excerpt_from_html(page.content_html)
    if page.is_published and page.date_published is None:
        page.date_published = timezone.now()


def site_path(item: models.Page | models.PageCategory) -> str:
    """Адрес страницы или рубрики на сайте."""
    category = getattr(item, "category", None)
    return build_path(item.slug, category.slug if category else None)


def rerender_pages() -> int:
    """Пересобрать HTML всех страниц — после смены рендера. Возвращает число страниц."""
    count = 0
    for page in models.Page.objects.iterator():
        page.content_html = render_markdown(page.content_md)
        page.save(update_fields=["content_html"])
        count += 1
    return count


# --- Редиректы (админка) ---------------------------------------------------------------

def save_redirect(path_from: str, path_to: str) -> None:
    """Адрес сменился — старый ведёт на новый. Цепочек не копим: что вело на старый адрес, теперь ведёт
    сразу на новый. Редирект с нового адреса удаляем: по нему снова живая страница, а уйди она с сайта —
    редирект с него вёл бы по кругу."""
    if path_from == path_to:
        return
    models.PageRedirect.objects.filter(path_from=path_to).delete()
    models.PageRedirect.objects.filter(path_to=path_from).update(path_to=path_to)
    models.PageRedirect.objects.update_or_create(path_from=path_from, defaults={"path_to": path_to})


def check_redirect(path_from: str, path_to: str, pk: int | None) -> None:
    """Редирект, добавленный руками, не должен вести по кругу. Ошибка — ValidationError для формы админки."""
    if path_from == path_to:
        raise ValidationError("Старый и новый адрес совпадают")
    redirect = models.PageRedirect.objects.filter(path_from=path_to).exclude(pk=pk).first()
    if redirect is not None:
        raise ValidationError(f"С адреса {path_to} уже есть редирект на {redirect.path_to} — укажите сразу его")


# --- Картинки (админка) ----------------------------------------------------------------

def check_image(upload: UploadedFile) -> str:
    """Расширение картинки, если формат и размер подходят. Иначе ValidationError."""
    extension = Path(upload.name or "").suffix.lstrip(".").lower()
    if extension not in IMAGE_EXTENSION_LIST:
        raise ValidationError(f"Допустимые форматы: {', '.join(IMAGE_EXTENSION_LIST)}")
    if upload.size > conf.IMAGE_SIZE_MAX_MB * 1024 * 1024:
        raise ValidationError(f"Файл больше {conf.IMAGE_SIZE_MAX_MB} МБ")
    return extension


def optimize_image(content: bytes, extension: str) -> tuple[bytes, str]:
    """Ужимает до IMAGE_WIDTH_MAX и переводит в webp: фото с телефона на 8 МБ убьёт скорость страницы.

    gif не трогаем — может быть анимированным. Файл не читается — отдаём как есть:
    оптимизация некритичная и не должна мешать загрузке.
    """
    if extension == "gif":
        return content, extension
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
        # Телефон сохраняет снимок как есть, а поворот — тегом EXIF. В webp тег не переходит, и вертикальное
        # фото легло бы на бок, — поворачиваем сами
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
        if image.width > conf.IMAGE_WIDTH_MAX:
            height = round(image.height * conf.IMAGE_WIDTH_MAX / image.width)
            image = image.resize((conf.IMAGE_WIDTH_MAX, height), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=82, method=4)
        return buffer.getvalue(), "webp"
    except Exception:
        return content, extension


def prepare_image(image: models.PageImage, upload: UploadedFile) -> None:
    """Новый файл картинки: проверка, оптимизация, имя и размер. Сохраняет вызывающий."""
    extension = check_image(upload)
    upload.seek(0)  # форма админки уже читала файл, проверяя, что это картинка
    content, extension = optimize_image(upload.read(), extension)
    image.original_name = (upload.name or "")[:255]
    image.size = len(content)
    # Имя файла — случайное: исходное хранится отдельно, а в адресе кириллица и пробелы ни к чему
    image.file = ContentFile(content, name=f"{uuid.uuid4().hex[:16]}.{extension}")


def create_image(upload: UploadedFile) -> models.PageImage:
    """Картинка из редактора текста."""
    image = models.PageImage()
    prepare_image(image, upload)
    image.save()
    return image


def delete_image_file(image: models.PageImage) -> None:
    """Удаляет файл с диска — Django при удалении записи этого не делает. Нет файла — не ошибка."""
    if image.file:
        image.file.delete(save=False)


# --- Чтение для API ----------------------------------------------------------------------

def published_page_queryset():
    """Страницы, которые видны на сайте: опубликованы, дата публикации наступила,
    рубрика не скрыта (или её нет)."""
    active_category_id_list = Subquery(models_async.PageCategory.filter(is_active=True).values("id"))
    return (
        models_async.Page.filter(is_published=True, date_published__lte=timezone.now())
        .filter(Q(category_id__isnull=True) | Q(category_id__in=active_category_id_list))
        .select_related("category", "cover")
    )


def feed_queryset(category_slug: str | None, search: str | None):
    """Лента блога: только статьи с рубрикой. Отдельные страницы в ленту не попадают."""
    queryset = published_page_queryset().filter(category_id__isnull=False)
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(excerpt__icontains=search))
    return queryset


async def category_list() -> list[models_async.PageCategory]:
    """Рубрики, которые показываются на сайте, в порядке из админки."""
    return await models_async.PageCategory.filter(is_active=True)


async def get_page(slug: str) -> models_async.Page:
    """Видимая на сайте страница или статья по слагу, иначе 404."""
    return await published_page_queryset().get(slug=slug)


async def resolve(slug: str) -> dict:
    """Что лежит по адресу /{слаг}: рубрика, отдельная страница или ничего."""
    category = await models_async.PageCategory.get_or_none(slug=slug, is_active=True)
    if category is not None:
        return {"type": "category", "category": category}
    page = await published_page_queryset().get_or_none(slug=slug, category_id__isnull=True)
    if page is not None:
        return {"type": "page", "page": page}
    return {"type": "none"}


async def get_redirect(path: str) -> models_async.PageRedirect:
    """Редирект со старого адреса, иначе 404."""
    return await models_async.PageRedirect.get(path_from=clean_path(path))


async def sitemap_item_list() -> list[dict]:
    """Адреса для sitemap.xml: видимые рубрики и страницы, открытые для поисковиков."""
    item_list = [
        {"loc": build_path(category.slug), "lastmod": category.date_modified}
        for category in await models_async.PageCategory.filter(is_active=True, is_indexed=True)
    ]
    item_list += [
        {"loc": build_path(page.slug, page.category.slug if page.category else None), "lastmod": page.date_modified}
        for page in await published_page_queryset().filter(is_indexed=True)
    ]
    return item_list
