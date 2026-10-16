# Тема админки Unfold
Как подключить в своём проекте · 09.10.2026

В движке — стандартная админка Django. Тема [Unfold](https://github.com/unfoldadmin/django-unfold)
даёт новый вид, тёмную тему, выпадающие фильтры и порядок строк перетаскиванием, но это ещё одна
зависимость и свои классы во всех `admin.py`. Поэтому в движке её нет, а проект подключает её сам,
если хочет.

Движок версий 2.1.0–2.1.1 работал на Unfold — готовый код берётся оттуда:
`git show v2.1.1:back/<путь к файлу>`.

## Шаги

1. **Пакет** — в `requirements.txt`: `django-unfold==0.108.0` (на этой версии проверено).
2. **Настройки** (`project/settings.py`, как в v2.1.1):
   - в `INSTALLED_APPS` до `django.contrib.admin` — `"unfold"` и `"unfold.contrib.filters"`;
   - `UNFOLD = {"SITE_TITLE": "Администрирование", "SITE_HEADER": SITE_NAME, "SITE_URL": SITE_URL}` —
     в шапке название сайта, «Открыть сайт» ведёт на фронт;
   - `LOGIN_REDIRECT_URL = "/admin/"` — шаблон входа Unfold не передаёт `next`, без строки после
     входа Django ведёт на несуществующий `/accounts/profile/`.
3. **Все `admin.py`** — `ModelAdmin` и инлайны из `unfold.admin`, иначе формы без стилей. Админка
   пользователей — формы из `unfold.forms`: образец — `app/user/admin.py` в v2.1.1.
4. **Фильтр «Форма» в заявках** — вместо `AutocompleteFilter` движка фильтр Unfold:
   `unfold.contrib.filters.admin.AutocompleteSelectFilter` и `list_filter_submit = True`
   (`app/form/admin.py` в v2.1.1). Порядок рубрик перетаскиванием — `ordering_field` в `app/page/admin.py`.
5. **Перевод.** В Unfold 0.108 русского нет: свой — `app/locale/ru/` из v2.1.1 и
   `LOCALE_PATHS = [BASE_DIR / "locale"]`. Новая строка на английском — дописать в `.po`
   и собрать: `msgfmt -o django.mo django.po`.
6. **Тёмный редактор статей.** Unfold ставит класс `dark` на `<html>`, а не `data-theme`, как
   Django, — условие темы в `app/page/static/page/markdown-editor.js` взять из v2.1.1.

Обновили Unfold — проверить перевод и вход в админку: у новых версий меняются шаблоны и строки.
