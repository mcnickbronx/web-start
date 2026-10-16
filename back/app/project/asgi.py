"""Админка и API: локально (manage.py runserver) и на сервере (uvicorn, compose.yml). В профиле full
админку обслуживает свой процесс — контейнер admin с этой же точкой входа, Traefik шлёт туда /admin.

Запросы делятся до Django: /api/* уходит в FastAPI и middleware Django не проходит.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django_application = get_asgi_application()

from django.conf import settings  # noqa: E402 — только после django.setup()
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler  # noqa: E402

from project.api import create_app  # noqa: E402

api_application = create_app()

if settings.DEBUG:
    # Стандартный runserver отдаёт статику админки сам, под uvicorn — этот обработчик
    django_application = ASGIStaticFilesHandler(django_application)


async def application(scope, receive, send):
    # Django умеет только http: lifespan (старт/стоп) и websocket — в API
    path = scope.get("path", "")
    if scope["type"] != "http" or path == "/api" or path.startswith("/api/"):
        await api_application(scope, receive, send)
    else:
        await django_application(scope, receive, send)
