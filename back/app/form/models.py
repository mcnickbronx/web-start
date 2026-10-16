"""Формы на сайте и заявки с них.

Тип формы заводится в админке: куда слать письмо, какие поля обязательны, нужна ли капча,
можно ли прикладывать файлы. Поля у всех форм общие (имя, телефон, email, сообщение),
остальное — в data.
"""
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from form import conf


def form_file_storage() -> FileSystemStorage:
    """Закрытая папка для файлов заявок. Функцией — чтобы путь не попадал в миграции."""
    return FileSystemStorage(location=conf.FILE_ROOT)


class FormType(models.Model):
    """Форма на сайте: заявка на звонок, обратная связь, отклик на вакансию."""

    name = models.CharField("Название", max_length=200)
    code = models.SlugField("Код", max_length=100, unique=True, help_text="По нему сайт запрашивает форму. Менять — только вместе с сайтом")
    email_to = models.CharField("Кому отправлять", max_length=500, blank=True, help_text="Адреса через запятую. Пусто — заявки только в админке")
    email_subject = models.CharField("Тема письма", max_length=250, blank=True, help_text="Пусто — название формы")
    is_email_tech_info = models.BooleanField("Техническая информация в письме", default=False, help_text="Время заявки до секунды, откуда пришёл посетитель, метки, ID в Метрике, IP и браузер. IP и браузер — персональные данные: включать осознанно")
    is_contact_required = models.BooleanField("Нужен телефон или email", default=True, help_text="Хотя бы одно из двух — чтобы было куда ответить")
    is_name_required = models.BooleanField("Имя обязательно", default=False)
    is_phone_required = models.BooleanField("Телефон обязателен", default=False)
    is_email_required = models.BooleanField("Email обязателен", default=False)
    is_message_required = models.BooleanField("Сообщение обязательно", default=False)
    is_captcha = models.BooleanField("Капча", default=False)
    is_trap = models.BooleanField("Ловушка для ботов", default=True, help_text="Скрытое поле и проверка, что форму не отправили мгновенно")
    is_file = models.BooleanField("Можно прикладывать файлы", default=False)
    file_count_max = models.PositiveSmallIntegerField("Файлов не больше", default=5)
    is_active = models.BooleanField("Включена", default=True)
    date_add = models.DateTimeField("Дата создания", auto_now_add=True)
    date_modified = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        verbose_name = "Форма"
        verbose_name_plural = "Формы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FormRequest(models.Model):
    """Заявка с формы на сайте."""

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        WORK = "work", "В работе"
        DONE = "done", "Обработана"
        SPAM = "spam", "Спам"

    class Channel(models.TextChoices):
        ADS = "ads", "Реклама"
        SEARCH = "search", "Поиск"
        SOCIAL = "social", "Соцсети"
        EMAIL = "email", "Рассылки"
        REFERRAL = "referral", "Ссылки с сайтов"
        DIRECT = "direct", "Прямые заходы"
        OTHER = "other", "Другие метки"
        MANUAL = "manual", "Заведены вручную"

    class EmailStatus(models.TextChoices):
        WAIT = "wait", "Ждёт отправки"
        SENT = "sent", "Отправлено"
        ERROR = "error", "Ошибка"
        NONE = "none", "Не отправлялось"

    form_type = models.ForeignKey(FormType, models.PROTECT, verbose_name="Форма")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, verbose_name="Пользователь", null=True, blank=True)
    name = models.CharField("Имя", max_length=200, blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    email = models.CharField("Email", max_length=254, blank=True)
    message = models.TextField("Сообщение", blank=True)
    data = models.JSONField("Дополнительные поля", default=dict, blank=True)
    source = models.CharField("Страница", max_length=500, blank=True, help_text="Адрес, с которого отправлена заявка; «админка» — заявку завели вручную")
    ip = models.CharField("IP", max_length=45, blank=True)
    user_agent = models.CharField("Браузер", max_length=500, blank=True, help_text="Заголовок User-Agent как есть")
    # Откуда человек пришёл на сайт — присылает сайт, запомнив при первом заходе
    channel = models.CharField("Канал", max_length=10, choices=Channel.choices, blank=True, db_index=True, help_text="Вычисляется по меткам и сайту, с которого пришли")
    referrer = models.CharField("Пришёл с", max_length=1000, blank=True, help_text="Адрес, с которого человек попал на сайт")
    landing_page = models.CharField("Страница входа", max_length=1000, blank=True, help_text="Первая страница визита")
    utm = models.JSONField("Метки", default=dict, blank=True, help_text="UTM-метки и клики рекламы (yclid, gclid) из адреса страницы входа")
    ym_client_id = models.CharField("ID в Яндекс Метрике", max_length=50, blank=True, help_text="ClientID посетителя: путь до заявки — в Метрике")
    # Токен формы одноразовый: вторая отправка с тем же токеном упрётся в уникальность.
    # У заявки из админки токена нет — ставится случайный
    token_id = models.UUIDField("Токен формы", unique=True, default=uuid.uuid4, editable=False)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    email_status = models.CharField("Письмо", max_length=10, choices=EmailStatus.choices, default=EmailStatus.WAIT)
    email_error = models.TextField("Ошибка письма", blank=True)
    date_email_sent = models.DateTimeField("Письмо отправлено", null=True, blank=True)
    date_add = models.DateTimeField("Дата создания", auto_now_add=True)
    date_modified = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-id"]

    def __str__(self):
        return f"Заявка №{self.pk}"


class FormFile(models.Model):
    """Файл к заявке. Загружается до отправки заявки и привязывается к ней при отправке."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_request = models.ForeignKey(FormRequest, models.CASCADE, verbose_name="Заявка", null=True, blank=True)
    token_id = models.UUIDField("Токен формы", db_index=True, editable=False)
    file = models.FileField("Файл", upload_to="%Y/%m/", storage=form_file_storage, max_length=300)
    original_name = models.CharField("Исходное имя", max_length=255, blank=True)
    size = models.PositiveIntegerField("Размер, байт", default=0)
    date_add = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        verbose_name = "Файл"
        verbose_name_plural = "Файлы"

    def __str__(self):
        return self.original_name or self.file.name
