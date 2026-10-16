"""Tortoise ORM для API: подключение берётся из Django DATABASES, модели — из */models_async.py."""
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.utils.module_loading import module_has_submodule

from core.generator import TORTOISE_APP


def model_modules() -> list[str]:
    return [
        f"{app_config.name}.models_async"
        for app_config in apps.get_app_configs()
        if module_has_submodule(app_config.module, "models_async")
    ]


def connection_config() -> dict:
    """Та же база, что у Django. Только PostgreSQL: на SQLite Django и Tortoise хранят UUID по-разному."""
    database = settings.DATABASES["default"]
    return {
        "engine": "tortoise.backends.asyncpg",
        "credentials": {
            "host": database["HOST"],
            "port": int(database["PORT"]),
            "user": database["USER"],
            "password": database["PASSWORD"],
            "database": database["NAME"],
            # Пул на один процесс uvicorn: воркеров × maxsize ≤ max_connections Postgres
            "minsize": 1,
            "maxsize": settings.API_DB_POOL_SIZE,
        },
    }


def tortoise_config() -> dict:
    for module in model_modules():
        import_module(module)  # ошибка в сгенерированном файле — сразу на старте
    return {
        "connections": {"default": connection_config()},
        "apps": {TORTOISE_APP: {"models": model_modules(), "default_connection": "default"}},
        # Django пишет в базу UTC (USE_TZ = True) — API читает и пишет так же
        "use_tz": True,
        "timezone": "UTC",
    }
