from page import services
from page.models import Page, PageCategory, PageImage


def create_page_image(file="page/2026/10/oblozhka.webp", alt="Обложка", **kwargs) -> PageImage:
    """Картинка — только запись: адрес в API собирается из пути, файл на диске не нужен."""
    return PageImage.objects.create(file=file, alt=alt, **kwargs)


def create_page_category(name="Новости", slug="", is_active=True, **kwargs) -> PageCategory:
    """Рубрика блога. Слаг — как в админке: пустой соберётся из названия."""
    category = PageCategory(name=name, is_active=is_active, **kwargs)
    category.slug = services.clean_slug(PageCategory, slug, name, None)
    category.save()
    return category


def create_page(title="О компании", category=None, content_md="Работаем **с 2010 года**.", is_published=True, slug="", **kwargs) -> Page:
    """Страница, как её сохраняет админка: слаг, HTML из Markdown, анонс, дата публикации.
    Без рубрики — отдельная страница, с рубрикой — статья блога (create_article)."""
    page = Page(title=title, category=category, content_md=content_md, is_published=is_published, **kwargs)
    page.slug = services.clean_slug(Page, slug, title, None)
    services.prepare_page(page)
    page.save()
    return page


def create_article(title="Как выбрать подрядчика", category=None, **kwargs) -> Page:
    """Статья блога. Рубрика — первая из уже созданных, нет ни одной — новая."""
    category = category or PageCategory.objects.first() or create_page_category()
    return create_page(title=title, category=category, **kwargs)
