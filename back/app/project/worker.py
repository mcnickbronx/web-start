"""Точка входа воркера задач: taskiq worker project.worker:broker

Нужен только когда задачи уходят в Redis (задан REDIS_URL). Поднимает Django,
подключает Tortoise и импортирует tasks.py всех модулей, чтобы воркер знал задачи.
"""
import os
from importlib import import_module

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.apps import apps  # noqa: E402 — только после django.setup()
from django.utils.module_loading import module_has_submodule  # noqa: E402
from taskiq import TaskiqEvents, TaskiqState  # noqa: E402
from tortoise import Tortoise  # noqa: E402

from core import http  # noqa: E402
from core.broker import broker  # noqa: E402
from core.orm import tortoise_config  # noqa: E402

for app_config in apps.get_app_configs():
    if module_has_submodule(app_config.module, "tasks"):
        import_module(f"{app_config.name}.tasks")


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    await Tortoise.init(config=tortoise_config())


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await Tortoise.close_connections()
    await http.close()
