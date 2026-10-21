"""manage.py sync_async_models — Tortoise-модели для API из Django-моделей.

Схема одна — models.py, а API читает базу через Tortoise. Команда проходит все модули проекта
(сторонние приложения не трогает) и пишет каждому <module>/models_async.py: файл перезаписывается
целиком, у модуля без моделей — удаляется, неизменившиеся не трогает. Руками не править.
Модели берёт у Django, а не из файлов: модели из models_blog.py попадут, если их импортирует
models.py, — как и в миграции. Одинаковые имена моделей в разных модулях — ошибка: в Tortoise
все модели лежат в одном приложении. База не нужна.

После изменения models.py: makemigrations → sync_async_models → коммит обоих.
Забыли — локально ошибки не будет: API молча работает со старой схемой. Поймает только --check:
ничего не пишет и падает, если файлы отстали. Его запускают CI (.github/workflows/back.yml)
и выкладка (сервис deploy в compose.yml) — новая версия тогда не выходит.
Что генератор не умеет (on_delete, связи вне проекта) — в core/generator.py.

Запуск из back/app:
    python manage.py sync_async_models           # обновить файлы
    python manage.py sync_async_models --check   # только проверить
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.generator import MODULE, GeneratorError, check_name_conflicts, project_app_configs, render_app


class Command(BaseCommand):
    help = "Сгенерировать <module>/models_async.py (Tortoise) из Django-моделей"

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Только проверить, что файлы актуальны")

    def handle(self, *args, **options):
        check = options["check"]
        try:
            check_name_conflicts()
            outdated = [self.sync(app_config, check) for app_config in project_app_configs()]
        except GeneratorError as exc:
            raise CommandError(str(exc)) from exc

        outdated = [path for path in outdated if path]
        if check and outdated:
            raise CommandError("models_async.py устарели, запустите manage.py sync_async_models: " + ", ".join(outdated))
        if not outdated:
            self.stdout.write("models_async.py актуальны")

    def sync(self, app_config, check: bool) -> str | None:
        """Обновляет файл модуля. Возвращает путь, если он был устаревшим."""
        path = Path(app_config.path) / f"{MODULE}.py"
        relative = f"{app_config.label}/{MODULE}.py"
        content = render_app(app_config)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if content == current:
            return None
        if not check:
            if content is None:
                path.unlink()
                self.stdout.write(f"Удалён {relative} (у модуля нет моделей)")
            else:
                path.write_text(content, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(f"Записан {relative}"))
        return relative
