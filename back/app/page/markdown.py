"""Markdown → безопасный HTML для страниц.

HTML собирается на бэкенде при сохранении: фронт получает готовую разметку и не тащит
парсер к себе. Источник правды — Markdown: если поменяется рендер, всё пересобирается
командой `manage.py rerender_pages`.

Текст в редактор чаще всего вставляют из Word или Google Docs, и Markdown при этом
получается кривой: маркеры списка приезжают символом «•» с пачкой &nbsp;, пустые
абзацы — строками из &nbsp;, абзацы разделены одним переводом строки. Для Markdown
одиночный перевод строки — не новый абзац, и вся статья схлопывается в один <p>.
Поэтому перед рендером текст нормализуется. В базе он остаётся как есть.
"""
import html
import re

import markdown_it
import nh3

# Теги, которые может породить Markdown. Остальное (script, iframe, style, произвольный
# HTML из текста) вырезается: автор в админке доверенный, но хранить неотфильтрованный
# HTML всё равно не стоит
ALLOWED_TAG_SET = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "s", "del", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTE_MAP = {
    # rel не добавлять: nh3 сам ставит ссылкам rel="noopener noreferrer" и падает, если rel разрешён явно
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align"},
}

_markdown = markdown_it.MarkdownIt("commonmark", {"linkify": True, "typographer": True}).enable(
    ["table", "strikethrough", "linkify"]
)

# --- Нормализация текста из Word ----------------------------------------------------

_NBSP = r"(?:&nbsp;|&#160;|&#xa0;| )"
#: Символы, которыми Word рисует маркер списка вместо разметки
_WORD_BULLET_CHARS = "•▪◦‣∙·"

_BLANK_LINE_RE = re.compile(rf"^(?:{_NBSP}|\s)*$")
_FENCE_RE = re.compile(r"^\s{0,3}(?:```|~~~)")
_WORD_BULLET_RE = re.compile(rf"^(?:{_NBSP}|\s)*[{_WORD_BULLET_CHARS}](?:{_NBSP}|[ \t])+")
#: Нумерованный пункт из Word: цифра, точка или скобка и отступ из &nbsp;
_WORD_NUMBER_RE = re.compile(rf"^(?:{_NBSP}|\s)*(\d{{1,3}})[.)](?:{_NBSP})+")
#: Несколько &nbsp; подряд — форматирование Word. Одиночный оставляем: его ставят осознанно («10&nbsp;млн»)
_NBSP_RUN_RE = re.compile(rf"(?:{_NBSP}){{2,}}")
_NBSP_TAIL_RE = re.compile(rf"(?:{_NBSP})+$")
#: Картинка без адреса — след вставки из Word: файл в media так и не попал
_EMPTY_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*\)")

_LIST_ITEM_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d{1,9}[.)])\s")
_TABLE_ROW_RE = re.compile(r"^\s{0,3}\|")
_QUOTE_RE = re.compile(r"^\s{0,3}>")
#: Продолжение предыдущего блока: пункта списка или кода с отступом
_CONTINUATION_RE = re.compile(r"^(?:[ ]{2,}|\t)\S")
#: Подчёркивание заголовка (=== или ---) — отрывать от своей строки нельзя
_SETEXT_RE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
#: Отступ в начале строки. Если в нём есть &nbsp; — это форматирование Word, убираем целиком
_LEADING_INDENT_RE = re.compile(rf"^(?:{_NBSP}|[ \t])+")
_HAS_NBSP_RE = re.compile(_NBSP)


def _normalize_line(line: str) -> str:
    """Одна строка вне блока кода: маркеры Word → Markdown, отступы из &nbsp; → пробел."""
    if _BLANK_LINE_RE.match(line):
        return ""

    line = _EMPTY_IMAGE_RE.sub("", line)

    indent = _LEADING_INDENT_RE.match(line)
    if indent and _HAS_NBSP_RE.search(indent.group(0)):
        line = line[indent.end():]

    bullet = _WORD_BULLET_RE.match(line)
    if bullet:
        line = "- " + line[bullet.end():]
    else:
        number = _WORD_NUMBER_RE.match(line)
        if number:
            line = f"{number.group(1)}. " + line[number.end():]

    line = _NBSP_TAIL_RE.sub("", line)
    line = _NBSP_RUN_RE.sub(" ", line)
    return line if line.strip() else ""


def _needs_blank_line(current: str, following: str, in_list: bool) -> bool:
    """Нужна ли пустая строка между двумя соседними непустыми строками.

    В редакторе одна строка — один абзац, поэтому по умолчанию разделяем. Не разделяем
    то, что по построению один блок: пункты списка (иначе каждый обернётся в <p>),
    строки таблицы и цитаты, продолжение пункта с отступом, подчёркивание заголовка
    и явный перенос строки, поставленный автором.
    """
    if current.endswith("  ") or current.endswith("\\"):
        return False
    if _CONTINUATION_RE.match(following) or _SETEXT_RE.match(following):
        return False
    if _TABLE_ROW_RE.match(current) and _TABLE_ROW_RE.match(following):
        return False
    if _QUOTE_RE.match(current) and _QUOTE_RE.match(following):
        return False
    if in_list and _LIST_ITEM_RE.match(following):
        return False
    return True


def normalize_markdown(content_md: str) -> str:
    """Текст из редактора → корректный Markdown. Блоки кода не трогаем."""
    line_list = content_md.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    cleaned: list[str] = []
    in_fence = False
    for line in line_list:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            cleaned.append(line)
            continue
        cleaned.append(line if in_fence else _normalize_line(line))

    result: list[str] = []
    in_fence = False
    in_list = False
    for index, line in enumerate(cleaned):
        result.append(line)
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        if in_fence:
            continue
        if not line:
            in_list = False
            continue
        if _LIST_ITEM_RE.match(line):
            in_list = True

        following = cleaned[index + 1] if index + 1 < len(cleaned) else ""
        if following and _needs_blank_line(line, following, in_list):
            result.append("")
            in_list = False

    return "\n".join(result)


def render_markdown(content_md: str) -> str:
    """Markdown → безопасный HTML. Пустой текст — пустая строка."""
    if not content_md or not content_md.strip():
        return ""
    rendered = _markdown.render(normalize_markdown(content_md))
    return nh3.clean(rendered, tags=ALLOWED_TAG_SET, attributes=ALLOWED_ATTRIBUTE_MAP)


def excerpt_from_html(content_html: str, limit: int = 300) -> str:
    """Анонс из начала текста — если в админке его не заполнили."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", content_html or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
