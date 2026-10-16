from django import forms


class MarkdownWidget(forms.Textarea):
    """Поле Markdown с редактором Toast UI: визуальный режим и исходник, вкладками внизу.

    В базу уходит Markdown. Картинки, вставленные или перетащенные в редактор, загружаются
    на `upload_url` — адрес в админке, закрытый её авторизацией. Редактор поднимает
    markdown-editor.js по метке data-markdown-editor. Файлы редактора лежат в статике
    модуля, без внешнего CDN, и подключаются только на формах с этим полем. Тёмная тема
    редактора включается вместе с тёмной темой админки.
    """

    def __init__(self, upload_url: str = "", attrs: dict | None = None):
        super().__init__({"data-markdown-editor": "1", "data-upload-url": upload_url, **(attrs or {})})

    class Media:
        css = {"all": ["page/toastui/toastui-editor.min.css", "page/toastui/toastui-editor-dark.css"]}
        js = ["page/toastui/toastui-editor-all.min.js", "page/toastui/toastui-editor-ru-ru.js", "page/markdown-editor.js"]
