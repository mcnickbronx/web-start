"""Текст из админки → HTML. Его чаще всего вставляют из Word или Google Docs: маркеры списка
символом «•», абзацы одним переводом строки, пустые строки и отступы из &nbsp;."""
from django.test import SimpleTestCase

from page.markdown import normalize_markdown, render_markdown


class RenderMarkdownTest(SimpleTestCase):
    def test_line_is_paragraph(self):
        """В редакторе одна строка — один абзац, а не вся статья одним <p>."""
        self.assertHTMLEqual(render_markdown("Первый абзац\nВторой абзац"), "<p>Первый абзац</p><p>Второй абзац</p>")

    def test_word_bullet_list(self):
        html = render_markdown("Услуги:\n•&nbsp;&nbsp;Медосмотр\n•&nbsp;&nbsp;Выезд на место")
        self.assertHTMLEqual(html, "<p>Услуги:</p><ul><li>Медосмотр</li><li>Выезд на место</li></ul>")

    def test_word_numbered_list(self):
        html = render_markdown("1.&nbsp;&nbsp;Позвонить\n2.&nbsp;&nbsp;Приехать")
        self.assertHTMLEqual(html, "<ol><li>Позвонить</li><li>Приехать</li></ol>")

    def test_word_spacing(self):
        """Пустые строки и отступы из &nbsp; уходят, несколько &nbsp; подряд — пробел.
        Одиночный остаётся: его ставят осознанно («10&nbsp;млн»)."""
        self.assertHTMLEqual(render_markdown("Текст\n&nbsp;\n&nbsp;&nbsp;\nЕщё текст"), "<p>Текст</p><p>Ещё текст</p>")
        self.assertEqual(normalize_markdown("&nbsp;&nbsp;Отступ, 10&nbsp;млн и&nbsp;&nbsp;&nbsp;пачка"), "Отступ, 10&nbsp;млн и пачка")

    def test_code_block_untouched(self):
        code = "```\n•&nbsp;не список\nстрока два\n```"
        self.assertEqual(normalize_markdown(code), code)

    def test_author_markdown_kept(self):
        """Markdown автора чистка не ломает: список — одним списком, явный перенос строки — <br>."""
        self.assertHTMLEqual(render_markdown("- раз\n- два\n\nПосле списка"), "<ul><li>раз</li><li>два</li></ul><p>После списка</p>")
        self.assertIn("<br>", render_markdown("Строка  \nпродолжение"))

    def test_dangerous_html_removed(self):
        html = render_markdown('<script>alert(1)</script>\n\n<iframe src="https://example.com"></iframe>\n\nТекст')
        self.assertHTMLEqual(html, "<p>Текст</p>")
