"""Генерация Tortoise-моделей из Django-моделей (manage.py sync_async_models).

Django — единственный источник схемы: модели, миграции, админка. Для API из моделей
каждого модуля проекта строится <module>/models_async.py: те же таблицы и колонки,
но с асинхронным Tortoise ORM. Файл руками не правится и лежит в git.

Ограничения (сознательные):
- Обычный on_delete (CASCADE, PROTECT, SET_NULL) Django выполняет в Python, в базе
  такого правила нет: в Tortoise ставится NO_ACTION, а связанные записи при удалении
  из API удаляются явно, в services.py. Если нужно удалять из API — объявляйте связь
  с DB_CASCADE / DB_SET_NULL / DB_SET_DEFAULT: правило уходит в базу и работает для всех.
- Связи на модели вне проекта (auth.Group, contenttypes) не генерируются:
  ForeignKey становится простым полем <name>_id, ManyToMany пропускается.
- Незнакомое поле — ошибка генерации, а не молчаливая подмена.
"""
import enum
from decimal import Decimal
from pathlib import Path

from django.apps import AppConfig, apps
from django.conf import settings
from django.db import models
from django.db.models import deletion
from django.db.models.fields import NOT_PROVIDED

COMMAND = "sync_async_models"
MODULE = "models_async"
TORTOISE_APP = "models"

HEADER = f'''"""Файл сгенерирован автоматически командой manage.py {COMMAND}.

Не редактировать: источник схемы — models.py этого же модуля, правки затрёт
следующая генерация. После изменения моделей: makemigrations → {COMMAND}.
Когда файл менялся и почему — в истории git.
"""
'''


class GeneratorError(Exception):
    pass


# Правило удаления есть в самой базе только у DB_*; остальное Django делает в Python,
# и для базы (а значит и для Tortoise) внешний ключ обычный.
DB_LEVEL_ON_DELETE = {
    deletion.DB_CASCADE: "CASCADE",
    deletion.DB_SET_NULL: "SET_NULL",
    deletion.DB_SET_DEFAULT: "SET_DEFAULT",
}


def project_app_configs() -> list[AppConfig]:
    """Модули проекта (лежат в BASE_DIR) — сторонние приложения не генерируются."""
    return [
        app_config for app_config in apps.get_app_configs()
        if Path(app_config.path).resolve().is_relative_to(Path(settings.BASE_DIR).resolve())
    ]


def is_generated(model: type[models.Model]) -> bool:
    return model._meta.app_config in project_app_configs() and not model._meta.proxy


def concrete_models(app_config: AppConfig) -> list[type[models.Model]]:
    return [model for model in app_config.get_models() if not model._meta.proxy]


# Порядок важен: подклассы раньше базовых (EmailField — это CharField, DateTimeField — DateField)
SIMPLE_FIELDS: list[tuple[type[models.Field], str]] = [
    (models.BigAutoField, "BigIntField"),
    (models.SmallAutoField, "SmallIntField"),
    (models.AutoField, "IntField"),
    (models.BigIntegerField, "BigIntField"),
    (models.SmallIntegerField, "SmallIntField"),
    (models.IntegerField, "IntField"),
    (models.CharField, "CharField"),
    (models.FileField, "CharField"),  # в базе — путь к файлу
    (models.TextField, "TextField"),
    (models.BooleanField, "BooleanField"),
    (models.FloatField, "FloatField"),
    (models.DecimalField, "DecimalField"),
    (models.DateTimeField, "DatetimeField"),
    (models.DateField, "DateField"),
    (models.TimeField, "TimeField"),
    (models.UUIDField, "UUIDField"),
    (models.JSONField, "JSONField"),
    (models.BinaryField, "BinaryField"),
]


class ModuleWriter:
    """Собирает текст одного models_async.py: импорты + классы."""

    def __init__(self):
        self.imports: set[str] = {"from tortoise import fields", "from tortoise.models import Model"}
        self.classes: list[str] = []

    def default_repr(self, field: models.Field) -> str | None:
        default = field.default
        if default is NOT_PROVIDED:
            # Как Django: обязательная строка без default создаётся пустой, а не NULL
            if field.empty_strings_allowed and not field.null and not field.unique and not field.primary_key:
                return 'b""' if isinstance(field, models.BinaryField) else '""'
            return None
        if default is None:
            return None
        if callable(default):
            if default in (dict, list):
                return default.__name__
            module, qualname = default.__module__, default.__qualname__
            if "<" in qualname or "." in qualname:
                raise GeneratorError(f"{field}: default={qualname} — нужна функция уровня модуля, не lambda")
            self.imports.add(f"from {module} import {qualname}")
            return qualname
        if isinstance(default, enum.Enum):  # TextChoices / IntegerChoices
            default = default.value
        if isinstance(default, Decimal):
            self.imports.add("from decimal import Decimal")
            return f'Decimal("{default}")'
        if type(default) in (str, int, float, bool):
            return repr(default)
        raise GeneratorError(f"{field}: default={default!r} — тип не поддерживается генератором")

    def common_kwargs(self, field: models.Field) -> list[str]:
        kwargs = []
        if field.primary_key:
            kwargs.append("primary_key=True")
        if field.null:
            kwargs.append("null=True")
        if field.unique and not field.primary_key:
            kwargs.append("unique=True")
        if field.db_index and not field.unique:
            kwargs.append("db_index=True")
        if field.column != field.attname:
            kwargs.append(f'source_field="{field.column}"')
        default = self.default_repr(field)
        if default is not None:
            kwargs.append(f"default={default}")
        return kwargs

    def simple_field(self, field: models.Field) -> str:
        for django_class, tortoise_class in SIMPLE_FIELDS:
            if isinstance(field, django_class):
                break
        else:
            raise GeneratorError(f"{field}: {type(field).__name__} не поддерживается — добавьте в core/generator.py")

        kwargs = []
        if tortoise_class == "CharField":
            kwargs.append(f"max_length={field.max_length}")
        elif tortoise_class == "DecimalField":
            kwargs += [f"max_digits={field.max_digits}", f"decimal_places={field.decimal_places}"]
        elif tortoise_class == "DatetimeField":
            if field.auto_now:
                kwargs.append("auto_now=True")
            if field.auto_now_add:
                kwargs.append("auto_now_add=True")
        elif tortoise_class == "DateField" and (field.auto_now or field.auto_now_add):
            raise GeneratorError(f"{field}: auto_now у DateField Tortoise не поддерживает — используйте DateTimeField")
        kwargs += self.common_kwargs(field)
        return f"fields.{tortoise_class}({', '.join(kwargs)})"

    def relation_field(self, field: models.ForeignKey) -> tuple[str, str]:
        """(имя атрибута, объявление) для ForeignKey / OneToOneField."""
        target = field.related_model
        if not is_generated(target):
            # Связь на модель вне проекта — только колонка с id
            return field.attname, self._raw_fk_column(field)

        tortoise_class = "OneToOneField" if isinstance(field, models.OneToOneField) else "ForeignKeyField"
        kwargs = [f'"{TORTOISE_APP}.{target._meta.object_name}"']
        remote = field.remote_field
        related_name = "False" if remote.hidden else f'"{remote.get_accessor_name()}"'
        kwargs.append(f"related_name={related_name}")
        on_delete = DB_LEVEL_ON_DELETE.get(field.remote_field.on_delete, "NO_ACTION")
        kwargs.append(f"on_delete=fields.{on_delete}")
        if field.primary_key:
            raise GeneratorError(f"{field}: связь как первичный ключ (наследование таблиц) не поддерживается")
        if field.null:
            kwargs.append("null=True")
        if field.column != field.attname:
            kwargs.append(f'source_field="{field.column}"')
        if not field.db_constraint:
            kwargs.append("db_constraint=False")
        return field.name, f"fields.{tortoise_class}({', '.join(kwargs)})"

    def _raw_fk_column(self, field: models.ForeignKey) -> str:
        target_pk = field.target_field
        for django_class, tortoise_class in SIMPLE_FIELDS:
            if isinstance(target_pk, django_class):
                break
        else:
            raise GeneratorError(f"{field}: тип ключа {type(target_pk).__name__} не поддерживается")
        kwargs = [f"max_length={target_pk.max_length}"] if tortoise_class == "CharField" else []
        if field.null:
            kwargs.append("null=True")
        if field.unique:
            kwargs.append("unique=True")
        elif field.db_index:
            kwargs.append("db_index=True")
        if field.column != field.attname:
            kwargs.append(f'source_field="{field.column}"')
        comment = f"  # связь на {field.related_model._meta.label} (вне проекта)"
        return f"fields.{tortoise_class}({', '.join(kwargs)}){comment}"

    def many_to_many(self, field: models.ManyToManyField) -> str | None:
        target = field.related_model
        if not is_generated(target):
            return None
        remote = field.remote_field
        related_name = f'"{remote.get_accessor_name()}"' if not remote.hidden else f'"_{field.model._meta.model_name}_{field.name}"'
        kwargs = [
            f'"{TORTOISE_APP}.{target._meta.object_name}"',
            f"related_name={related_name}",
            f'through="{field.m2m_db_table()}"',
            f'backward_key="{field.m2m_column_name()}"',
            f'forward_key="{field.m2m_reverse_name()}"',
            "on_delete=fields.NO_ACTION",  # промежуточную таблицу Django чистит сам
        ]
        return f"fields.ManyToManyField({', '.join(kwargs)})"

    def add_model(self, model: type[models.Model]) -> None:
        opts = model._meta
        if opts.pk.is_relation:
            raise GeneratorError(f"{opts.label}: первичный ключ-связь (наследование таблиц) не поддерживается")

        lines = [f"class {opts.object_name}(Model):"]
        if model.__doc__ and not model.__doc__.startswith(f"{opts.object_name}("):
            lines.append(f'    """{model.__doc__.strip()}"""')
            lines.append("")

        for field in opts.local_fields:
            if field.is_relation:
                name, declaration = self.relation_field(field)
            else:
                name, declaration = field.name, self.simple_field(field)
            lines.append(f"    {name} = {declaration}")

        for field in opts.local_many_to_many:
            declaration = self.many_to_many(field)
            if declaration is None:
                lines.append(f"    # {field.name}: связь на {field.related_model._meta.label} (вне проекта) не генерируется")
            else:
                lines.append(f"    {field.name} = {declaration}")

        lines += ["", "    class Meta:", f'        table = "{opts.db_table}"']
        if opts.ordering and all(isinstance(item, str) for item in opts.ordering):
            lines.append(f"        ordering = {list(opts.ordering)!r}")
        lines += ["", "    def __str__(self):", f"        return f\"{opts.object_name} {{self.pk}}\""]
        self.classes.append("\n".join(lines))

    def render(self) -> str:
        std = sorted(line for line in self.imports if not line.startswith(("from tortoise", "from django")))
        django = sorted(line for line in self.imports if line.startswith("from django"))
        tortoise = sorted(line for line in self.imports if line.startswith("from tortoise"))
        import_block = "\n\n".join("\n".join(group) for group in (std, django, tortoise) if group)
        return HEADER + import_block + "\n\n\n" + "\n\n\n".join(self.classes) + "\n"


def render_app(app_config: AppConfig) -> str | None:
    """Текст models_async.py для модуля или None, если у модуля нет моделей."""
    model_list = concrete_models(app_config)
    if not model_list:
        return None
    writer = ModuleWriter()
    for model in model_list:
        writer.add_model(model)
    return writer.render()


def check_name_conflicts() -> None:
    """Все Tortoise-модели живут в одном приложении Tortoise — имена классов не должны совпадать."""
    seen: dict[str, str] = {}
    for app_config in project_app_configs():
        for model in concrete_models(app_config):
            name = model._meta.object_name
            if name in seen:
                raise GeneratorError(f"Модель {name} есть в {seen[name]} и {app_config.label} — переименуйте одну")
            seen[name] = app_config.label
