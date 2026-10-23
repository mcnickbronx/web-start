import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    @classmethod
    def normalize_email(cls, email):
        """Email целиком в нижнем регистре — как в API. Django приводит только домен."""
        return (email or "").strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Пользователь с логином по email."""

    username = None
    email = models.EmailField("Email", unique=True)
    # Код из письма — один на активацию аккаунта и на сброс пароля
    confirmation_code = models.CharField("Код подтверждения", max_length=6, null=True, blank=True)
    confirmation_code_created_at = models.DateTimeField("Время отправки кода", null=True, blank=True)
    confirmation_code_attempts = models.PositiveSmallIntegerField("Попыток ввода кода", default=0)
    # JWT, выпущенные раньше, недействительны: смена пароля разлогинивает все устройства
    password_changed_at = models.DateTimeField("Пароль изменён", null=True, blank=True)
    # Ждущего кода отличает этот признак, а не is_active: у выключенного в админке is_active тоже снят
    is_confirmed = models.BooleanField("Подтверждён", default=True, help_text="Снят — регистрация из API ждёт кода из письма. Заведённые в админке подтверждены сразу; выключить аккаунт — галка «Активен»")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()


class UserSession(models.Model):
    """Вход с одного устройства: удалили сессию — токены этого устройства сразу недействительны."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # DB_CASCADE: правило в самой базе — пользователя можно удалить и из API, и из админки
    user = models.ForeignKey(CustomUser, models.DB_CASCADE, verbose_name="Пользователь")
    user_agent = models.CharField("Браузер", max_length=500, blank=True)
    ip = models.CharField("IP", max_length=45, blank=True)
    date_add = models.DateTimeField("Вход", auto_now_add=True)
    date_used = models.DateTimeField("Последняя активность", auto_now=True, help_text="Обновляется, когда устройство продлевает вход")

    class Meta:
        verbose_name = "Сессия"
        verbose_name_plural = "Сессии"
        ordering = ["-date_used"]

    def __str__(self):
        return f"Сессия {self.user_id} от {self.date_add:%d.%m.%Y}"
