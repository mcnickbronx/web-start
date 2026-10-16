from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from core.user_agent import describe_user_agent
from user.models import CustomUser, UserSession


class CustomUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = CustomUser
        fields = ("email",)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = "__all__"


class UserSessionInline(admin.TabularInline):
    """Где пользователь вошёл. Удалить сессию — выйти на том устройстве: его токены перестанут работать сразу."""

    model = UserSession
    fields = ["device", "ip", "date_add", "date_used"]
    readonly_fields = fields
    extra = 0

    def has_add_permission(self, request, obj=None) -> bool:
        return False  # сессию создаёт только вход

    @admin.display(description="Устройство")
    def device(self, obj: UserSession) -> str:
        return describe_user_agent(obj.user_agent) or obj.user_agent or "—"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    inlines = [UserSessionInline]
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "first_name", "last_name"]
    readonly_fields = ["last_login", "date_joined", "confirmation_code_created_at", "password_changed_at"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Персональные данные", {"fields": ("first_name", "last_name")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Код подтверждения", {"fields": ("confirmation_code", "confirmation_code_created_at", "confirmation_code_attempts")}),
        ("Даты", {"fields": ("last_login", "date_joined", "password_changed_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "usable_password", "password1", "password2")}),
    )
