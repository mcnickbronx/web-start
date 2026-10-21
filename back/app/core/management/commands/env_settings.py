"""manage.py env_settings — настройки модулей, что действует сейчас: значение и откуда оно.

Видно, применилась ли правка .env: после `docker compose restart` в контейнере старый .env,
нужно пересоздать контейнеры. Ключи не печатаются — только «задан» или «пусто». База не нужна.

На сервере, в папке проекта — в работающем приложении (app, в профиле full — app-full):
    docker compose exec app python manage.py env_settings
`run` вместо `exec` создаёт новый контейнер с новым .env: покажет, что будет после пересоздания,
а не то, что действует сейчас.
"""
from django.core.management.base import BaseCommand

from core import env


class Command(BaseCommand):
    help = "Настройки модулей из .env: что действует сейчас и откуда"

    def handle(self, *args, **options):
        prefix = None
        for setting in sorted(env.SETTING_LIST, key=lambda item: item.name):
            if setting.name.split("_")[0] != prefix:
                prefix = setting.name.split("_")[0]
                self.stdout.write(f"\n{prefix}")
            value = ("задан" if setting.value else "пусто") if setting.is_secret else self.show(setting.value)
            source = ".env" if setting.is_set else "по умолчанию"
            if setting.is_set and setting.value != setting.default and not setting.is_secret:
                source += f", по умолчанию {self.show(setting.default)}"
            self.stdout.write(f"  {setting.name} = {value}  ({source})")

    @staticmethod
    def show(value) -> str:
        return ",".join(value) if isinstance(value, list) else str(value)
