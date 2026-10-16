"""Сборка FastAPI-приложения.

Роутеры собираются из модулей: если в Django-приложении есть rest.py с `router`,
он подключается на /api/{app_label}/, а раздел в Swagger называется по verbose_name
из apps.py. Новый модуль с API — достаточно добавить его в INSTALLED_APPS.
"""
import asyncio
from contextlib import asynccontextmanager
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.utils.module_loading import module_has_submodule
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from taskiq import InMemoryBroker
from tortoise.contrib.fastapi import RegisterTortoise

from core import bridge
from core.broker import broker
from core.errors import register_error_handlers
from core.orm import tortoise_config
from core.schemas import ValidationErrorOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=tortoise_config()):
        # Мосту — где соединения API: вызов из админки в этом же процессе пойдёт через них
        bridge.api_loop = asyncio.get_running_loop()
        await broker.startup()
        try:
            yield
        finally:
            # Без Redis задачи выполняются в этом процессе: начатые (письмо уходит за секунду)
            # дождаться, пока база открыта, — иначе остановка оборвёт их на полпути
            if isinstance(broker, InMemoryBroker):
                await broker.wait_all()
            await broker.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="API",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        # У всех эндпоинтов в Swagger — наш формат ошибки 422, а не стандартный FastAPI
        responses={422: {"model": ValidationErrorOut, "description": "Ошибка валидации запроса"}},
        swagger_ui_parameters={
            "filter": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
            "defaultModelsExpandDepth": -1,  # скрыть раздел Schemas внизу
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/api/health", include_in_schema=False)
    async def health():
        """Для uptime-проверок: жив ли HTTP-стек (БД и Redis не проверяет)."""
        return {"status": "ok"}

    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "rest"):
            rest = import_module(f"{app_config.name}.rest")
            app.include_router(
                rest.router,
                prefix=f"/api/{app_config.label}",
                tags=[str(app_config.verbose_name)],
            )

    return app
