"""Страницы сайта и блог.

Адреса на сайте:
    /{слаг рубрики}              — рубрика со списком статей
    /{слаг рубрики}/{слаг}       — статья блога (страница с рубрикой)
    /{слаг}                      — отдельная страница (без рубрики)

Рубрики и страницы без рубрики делят корень сайта, поэтому слаг уникален сразу
в обеих таблицах. Это проверяет сервис при сохранении в админке — база сама
не проверит уникальность между двумя таблицами.

Сменился адрес — старый ведёт на новый: редиректы (PageRedirect).
"""
from django.db import models


class SeoModel(models.Model):
    """Общее у всего, что открывается на сайте по своему адресу."""

    slug = models.SlugField("Слаг", max_length=200, unique=True, blank=True, help_text="Адрес на сайте. Пусто — сформируется из названия")
    seo_title = models.CharField("SEO-заголовок", max_length=250, blank=True, help_text="Пусто — берётся название")
    seo_description = models.CharField("SEO-описание", max_length=500, blank=True, help_text="Пусто — берётся анонс или описание")
    is_indexed = models.BooleanField("Показывать поисковикам", default=True, help_text="Выключено — страница закрыта от индексации и не попадает в sitemap")
    date_add = models.DateTimeField("Дата создания", auto_now_add=True)
    date_modified = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        abstract = True


class PageCategory(SeoModel):
    """Рубрика блога: открывается по своему адресу со списком статей."""

    name = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=100)
    is_active = models.BooleanField("Показывать на сайте", default=True, help_text="Выключено — рубрика и её статьи скрыты")

    class Meta:
        verbose_name = "Рубрика"
        verbose_name_plural = "Рубрики"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class PageImage(models.Model):
    """Картинка для страниц: обложки и картинки в тексте. Лежит в media/, открыта всем."""

    file = models.ImageField("Файл", upload_to="page/%Y/%m/", max_length=300)
    original_name = models.CharField("Исходное имя", max_length=255, blank=True)
    alt = models.CharField("Описание картинки", max_length=255, blank=True, help_text="Текст для alt: его читают поисковики и экранные дикторы")
    size = models.PositiveIntegerField("Размер, байт", default=0)
    date_add = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        verbose_name = "Картинка"
        verbose_name_plural = "Картинки"
        ordering = ["-id"]

    def __str__(self):
        return self.original_name or self.file.name


class Page(SeoModel):
    """Страница сайта. С рубрикой — статья блога."""

    category = models.ForeignKey(PageCategory, models.PROTECT, verbose_name="Рубрика", null=True, blank=True, help_text="Без рубрики — отдельная страница в корне сайта")
    title = models.CharField("Заголовок", max_length=250)
    excerpt = models.TextField("Анонс", blank=True, help_text="Превью в списке статей. Пусто — соберётся из начала текста")
    content_md = models.TextField("Текст", blank=True)
    content_html = models.TextField("Текст в HTML", blank=True, editable=False, help_text="Собирается из текста при сохранении")
    cover = models.ForeignKey(PageImage, models.SET_NULL, verbose_name="Обложка", null=True, blank=True, related_name="+")
    is_published = models.BooleanField("Опубликовано", default=False)
    date_published = models.DateTimeField("Дата публикации", null=True, blank=True, db_index=True, help_text="Пусто — проставится при публикации. Дата в будущем — страница появится на сайте в этот момент")

    class Meta:
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"
        ordering = ["-date_published", "-id"]

    def __str__(self):
        return self.title


class PageRedirect(models.Model):
    """Старый адрес на сайте → новый, постоянный редирект. Сайт спрашивает о нём, только когда
    по адресу ничего нет: живую страницу редирект не перекроет."""

    path_from = models.CharField("Старый адрес", max_length=500, unique=True, help_text="Путь от корня сайта: /news/2019/staraya-statya.html. Можно вставить ссылку целиком — останется путь")
    path_to = models.CharField("Новый адрес", max_length=500, help_text="Путь от корня сайта: /novosti/statya")
    date_add = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Редирект"
        verbose_name_plural = "Редиректы"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.path_from} → {self.path_to}"
