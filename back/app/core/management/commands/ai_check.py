"""Платная проверка подключения: один короткий запрос по схеме, без БД."""
import asyncio
import time

from django.core.management.base import BaseCommand, CommandError
from pydantic import BaseModel, Field

from core import ai, http


class CheckOut(BaseModel):
    answer: str = Field(min_length=1, max_length=100)


class Command(BaseCommand):
    help = "Платный короткий запрос к ИИ по JSON-схеме (без пользовательского лимита)"

    def handle(self, *args, **options):
        self.stdout.write(f"Прокси: {'задан' if ai.PROXY else 'нет'}")

        async def check():
            try:
                return await ai.chat([{"role": "user", "content": 'Ответь словом «готово» в поле answer.'}],
                                     service="Проверка ИИ", user_id=None, schema=CheckOut)
            finally:
                await http.close()

        started = time.monotonic()
        try:
            result = asyncio.run(check())
        except http.ExternalServiceError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"{result.model_dump_json()}\nВремя: {time.monotonic() - started:.2f} с")
