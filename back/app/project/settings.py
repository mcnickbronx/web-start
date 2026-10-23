"""Настройки проекта. Общие для Django (админка, миграции) и FastAPI (API).

Значения окружения — ключи, база, домены, почта — в back/.env (шаблон — back/.env.txt).
"""
import os
import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Локально .env читается отсюда. В docker файла в контейнере нет: те же переменные
# передаёт compose (env_file). Уже заданные переменные файл не перекрывает.
# Нет переменной без значения по умолчанию — проект не стартует
env = environ.Env()
ENV_FILE = BASE_DIR.parent / ".env"
if ENV_FILE.exists():
    env.read_env(ENV_FILE)
elif "SECRET_KEY" not in os.environ:
    raise ImproperlyConfigured("Нет .env — скопируйте шаблон: cp .env.txt .env")

# --- Режим и ключи

DEBUG = env.bool("DEBUG", default=False)
# Запущены тесты (manage.py test): без Redis и с тихим журналом — ниже в «Очереди задач» и «Логах»
TESTING = sys.argv[1:2] == ["test"]
SECRET_KEY = env("SECRET_KEY")
# Подпись JWT в API. Свой ключ: смена SECRET_KEY не разлогинит API, и наоборот
JWT_SECRET_KEY = env("JWT_SECRET_KEY")

# --- Домены и куки

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
# Домены веб-фронтов, которым разрешены запросы к API из браузера
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# На сервере сайт работает по HTTPS: куки сессии и CSRF не уходят по открытому HTTP.
# Локально (DEBUG) — по HTTP, иначе вход в админку на runserver не работает
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
# За прокси (Traefik) приложение получает HTTP, а о HTTPS узнаёт из заголовка прокси.
# Без этого админка считает запросы незащищёнными, и вход ломается на проверке CSRF
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Приложения

INSTALLED_APPS = [
    # core — первым: его runserver перекрывает стандартный из staticfiles
    "core",
    # Фильтр списка с подсказками по связи, сворачиваемая панель фильтров и курсор в поиске подсказок.
    # Выше django.contrib.admin: его шаблоны списка и записи дополняют стандартные
    "admin_filter_kit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "log",
    "user",
    # Необязательные модули: убрать — migrate <модуль> zero, потом строку здесь, его строку
    # в project/crontab, если есть, и папку; подробно — readme модуля
    "page",
    "form",
    "live",
]

# Только для админки: API-запросы через Django не проходят
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"
ASGI_APPLICATION = "project.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- База

# Две базы в .env: DEV=True — dev-база (DEV_DB_*), DEV=False — прод (DB_*).
# Значения по умолчанию у DEV нет: забытая строка не должна молча увести в прод.
# Читается только выбранная база — на ноутбуке прод можно оставить пустым
DEV = env.bool("DEV")
db = "DEV_DB_" if DEV else "DB_"
empty = [db + key for key in ("NAME", "USER", "HOST", "PORT") if not env(db + key, default="")]
if empty:
    raise ImproperlyConfigured(f"DEV={DEV}, а в .env не заполнены: {', '.join(empty)}")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env(db + "NAME"),
        "USER": env(db + "USER"),
        "PASSWORD": env(db + "PASSWORD", default=""),
        "HOST": env(db + "HOST"),
        "PORT": env.int(db + "PORT"),
    }
}

# Соединений в пуле Tortoise на один процесс API
API_DB_POOL_SIZE = env.int("API_DB_POOL_SIZE", default=10)

# --- Пользователи и пароли

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "user.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Очередь задач и кэш

# Фоновые задачи. Без REDIS_URL брокер выполняет задачи сразу в процессе (локальная разработка).
# Тесты — всегда без Redis: задачи выполняются в процессе теста, и их можно дождаться
REDIS_URL = "" if TESTING else env("REDIS_URL", default="")

# Кэш справочников (core/cache.py) — в том же Redis. Без Redis кэша нет, а не кэш в памяти процесса:
# процессов API бывает несколько, админка — свой, и после правки в админке остальные отдавали бы старое
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL} if REDIS_URL
          else {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

# --- Почта

# Локально письма печатаются в консоль, на сервере уходят через SMTP.
# Ссылки в письмах ведут на SITE_URL, а не на домен из запроса
EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
# У Django таймаута нет: зависший SMTP-сервер навсегда займёт воркер задач
EMAIL_TIMEOUT = 60
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SITE_URL = env("SITE_URL")
SITE_NAME = env("SITE_NAME")

# --- Язык и время

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
# В базе время хранится в UTC (timestamptz) — так же его читает и пишет API
USE_TZ = True

# --- Логи

# Логи — в stdout, их собирает docker (docker compose logs), и в журнал в БД (админка → Журнал).
# Своё: logger = logging.getLogger(__name__), дальше logger.info(...) — см. app/log/readme.md
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "filters": {"project_only": {"()": "log.handlers.ProjectOnlyFilter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
        # Журнал в БД. Очередь и поток-слушателя создаёт dictConfig, пишет db_write.
        # Уровень задан отдельно: если корневой опустят до DEBUG, журнал в БД не зальёт
        "db": {
            "class": "log.handlers.RecordQueueHandler",
            "level": "INFO",
            "filters": ["project_only"],
            # Предел очереди: при недоступной базе лишние записи отбрасываются,
            # а не съедают память. Для журнала потерять запись безопаснее
            "queue": {"()": "queue.Queue", "maxsize": 10_000},
            "handlers": ["db_write"],
        },
        "db_write": {"class": "log.handlers.DatabaseLogHandler"},
    },
    "root": {"handlers": ["console", "db"], "level": "INFO"},
    # Свои обработчики Django заменяем общим, иначе при DEBUG сообщения дублируются.
    # В журнал логи Django не идут: нужен свой код, а не шум фреймворка
    "loggers": {"django": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
if TESTING:
    # Тестам — только предупреждения и ошибки, в консоль: служебный шум прячет упавший тест
    LOGGING["root"] = {"handlers": ["console"], "level": "WARNING"}

# --- Статика и файлы

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "static"

# media/ открыта по прямой ссылке — её отдаёт сервис files в compose.yml. Закрытые файлы — в private/
# рядом, путь задаёт модуль (form/conf.py, FILE_ROOT)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR.parent / "media"
