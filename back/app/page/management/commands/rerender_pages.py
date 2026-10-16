"""manage.py rerender_pages — пересобрать HTML всех страниц из Markdown после изменения рендера (page/markdown.py)."""
from django.core.management.base import BaseCommand

from page.services import rerender_pages


class Command(BaseCommand):
    help = "Пересобрать HTML всех страниц из Markdown — после изменения рендера"

    def handle(self, *args, **options):
        count = rerender_pages()
        self.stdout.write(f"Пересобрано страниц: {count}")
