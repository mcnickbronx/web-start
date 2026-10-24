from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html

from core.tree import check_parent
from page import services
from page.models import Page, PageCategory, PageImage, PageRedirect
from page.widgets import MarkdownWidget


class SlugForm(forms.ModelForm):
    """Слаг: введённый — проверяется, пустой — собирается из названия.
    Уникален сразу у рубрик и страниц: они делят корень сайта."""

    slug_source = "name"

    def clean(self):
        cleaned_data = super().clean()
        try:
            cleaned_data["slug"] = services.clean_slug(
                self._meta.model, cleaned_data.get("slug", ""), cleaned_data.get(self.slug_source, ""), self.instance.pk,
            )
        except ValidationError as exc:
            self.add_error("slug", exc)
        return cleaned_data


class PageCategoryForm(SlugForm):
    """Перенос рубрики — без цикла: не в саму себя и не в свою подрубрику, иначе ветка пропала бы с сайта."""

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get("parent")
        if parent is not None:
            # parent.pk, а не строка из запроса: со строковым id check_parent цикла не узнаёт
            try:
                check_parent(PageCategory.objects.values("id", "parent_id"), node_id=self.instance.pk, parent_id=parent.pk)
            except ValueError:
                self.add_error("parent", "Нельзя вложить рубрику в саму себя или в её подрубрику")
        return cleaned_data


class PageForm(SlugForm):
    slug_source = "title"


class PageRedirectForm(forms.ModelForm):
    """Адреса — путями от корня сайта: ссылку можно вставить целиком, останется путь."""

    def clean_path_from(self):
        return services.clean_path(self.cleaned_data["path_from"])

    def clean_path_to(self):
        return services.clean_path(self.cleaned_data["path_to"])

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("path_from") and cleaned_data.get("path_to"):
            try:
                services.check_redirect(cleaned_data["path_from"], cleaned_data["path_to"], self.instance.pk)
            except ValidationError as exc:
                self.add_error("path_to", exc)
        return cleaned_data


class PageImageForm(forms.ModelForm):
    def clean_file(self):
        file = self.cleaned_data["file"]
        if isinstance(file, UploadedFile):
            services.check_image(file)
        return file


@admin.register(PageCategory)
class PageCategoryAdmin(admin.ModelAdmin):
    form = PageCategoryForm
    list_display = ["name", "parent", "slug", "sort_order", "is_active", "date_modified"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    readonly_fields = ["date_add", "date_modified"]
    fieldsets = [
        (None, {"fields": ["name", "parent", "slug", "description", "sort_order", "is_active"]}),
        ("SEO", {"fields": ["seo_title", "seo_description", "is_indexed"]}),
        ("Даты", {"fields": ["date_add", "date_modified"]}),
    ]

    # Сменился слаг рубрики, которая была на сайте, — старый адрес ведёт на новый. Статьи рубрики редирект
    # не нужен: статья ищется по своему слагу, а неверную рубрику в адресе сайт исправляет сам
    def save_model(self, request, obj, form, change):
        previous = PageCategory.objects.filter(pk=obj.pk, is_active=True).first() if change else None
        super().save_model(request, obj, form, change)
        if previous is not None:
            services.save_redirect(services.site_path(previous), services.site_path(obj))


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageForm
    list_display = ["title", "category", "slug", "is_published", "date_published", "date_modified"]
    list_filter = ["is_published", "category"]
    list_select_related = ["category"]
    search_fields = ["title", "slug", "excerpt"]
    autocomplete_fields = ["cover"]
    readonly_fields = ["date_add", "date_modified"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "category", "cover", "excerpt", "content_md"]}),
        ("Публикация", {"fields": ["is_published", "date_published"]}),
        ("SEO", {"fields": ["seo_title", "seo_description", "is_indexed"]}),
        ("Даты", {"fields": ["date_add", "date_modified"]}),
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "content_md":
            kwargs["widget"] = MarkdownWidget(upload_url=reverse("admin:page_page_upload_image"))
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    # Сменился адрес опубликованной страницы — старый ведёт на новый: ссылки и закладки не ломаются,
    # поисковик переносит позиции. Черновик ещё нигде не стоит — его адрес не запоминаем
    def save_model(self, request, obj, form, change):
        services.prepare_page(obj)
        previous = Page.objects.select_related("category").filter(pk=obj.pk, is_published=True).first() if change else None
        super().save_model(request, obj, form, change)
        if previous is not None:
            services.save_redirect(services.site_path(previous), services.site_path(obj))

    def get_urls(self):
        # Раньше стандартных: иначе адрес примет за id страницы
        upload = path("upload-image/", self.admin_site.admin_view(self.upload_image), name="page_page_upload_image")
        return [upload, *super().get_urls()]

    def upload_image(self, request):
        """Картинка из редактора текста. Адрес внутри админки — закрыт её авторизацией и CSRF."""
        if request.method != "POST":
            return JsonResponse({"message": "Только POST"}, status=405)
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            return JsonResponse({"message": "Нет прав на редактирование страниц"}, status=403)
        upload = request.FILES.get("image")
        if upload is None:
            return JsonResponse({"message": "Файл не передан"}, status=400)
        try:
            image = services.create_image(upload)
        except ValidationError as exc:
            return JsonResponse({"message": " ".join(exc.messages)}, status=400)
        return JsonResponse({"id": image.id, "url": image.file.url})


@admin.register(PageImage)
class PageImageAdmin(admin.ModelAdmin):
    form = PageImageForm
    list_display = ["preview", "original_name", "alt", "size", "date_add"]
    search_fields = ["original_name", "alt"]
    readonly_fields = ["preview", "original_name", "size", "date_add"]
    fields = ["file", "preview", "alt", "original_name", "size", "date_add"]

    @admin.display(description="Превью")
    def preview(self, obj: PageImage) -> str:
        if not obj.file:
            return "—"
        return format_html('<img src="{}" alt="" style="height: 60px; width: auto;">', obj.file.url)

    def save_model(self, request, obj, form, change):
        if "file" not in form.changed_data:
            super().save_model(request, obj, form, change)
            return
        previous = PageImage.objects.filter(pk=obj.pk).first() if change else None
        services.prepare_image(obj, form.cleaned_data["file"])
        super().save_model(request, obj, form, change)
        if previous is not None:
            services.delete_image_file(previous)

    # Django удаляет запись, но не файл — убираем и его, иначе media/ зарастает мусором
    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        services.delete_image_file(obj)

    def delete_queryset(self, request, queryset):
        image_list = list(queryset)
        super().delete_queryset(request, queryset)
        for image in image_list:
            services.delete_image_file(image)


@admin.register(PageRedirect)
class PageRedirectAdmin(admin.ModelAdmin):
    form = PageRedirectForm
    list_display = ["path_from", "path_to", "date_add"]
    search_fields = ["path_from", "path_to"]
    readonly_fields = ["date_add"]
    fields = ["path_from", "path_to", "date_add"]
