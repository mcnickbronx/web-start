"""Дерево из плоского списка: рубрики каталога, вложенные страницы, папки.

У узла в базе — ссылка на родителя (`parent_id`), дерево собирается в памяти целиком: рубрик и страниц
сотни или тысячи, не миллионы. Узел — словарь, строка `.values()` Tortoise или Django: в ней `id`, `parent_id`
и поля сортировки.

    rows = await Category.all().values("id", "parent_id", "title", "sort_order")
    tree = build_tree(rows, order=("sort_order", "id"))  # корни, у каждого узла дети — в `child_list`
    id_set = descendant_ids(rows, category_id)  # рубрика со всеми подрубриками — для фильтра товаров
    check_parent(rows, node_id=category_id, parent_id=parent_id)  # перенос без цикла, иначе ValueError
"""
from collections.abc import Iterable
from typing import Any


def build_tree(rows: Iterable[dict], *, order: tuple[str, ...] = ("id",), child_list: str = "child_list") -> list[dict]:
    """Плоский список → корни с вложенными детьми, на каждом уровне — по полям `order`.
    Узел — копия строки с ключом `child_list`, исходные строки не меняются.
    Родителя нет в списке или узел сам себе родитель — узел становится корнем, а не пропадает."""
    node_by_id = {}
    for row in sorted(rows, key=lambda row: tuple(row[name] for name in order)):
        node_by_id[row["id"]] = {**row, child_list: []}
    root_list = []
    for node in node_by_id.values():  # в порядке сортировки — дети встают в свои списки уже по порядку
        parent = node_by_id.get(node["parent_id"])
        if parent is None or parent is node:
            root_list.append(node)
        else:
            parent[child_list].append(node)
    return root_list


def descendant_ids(rows: Iterable[dict], root_id: Any) -> set:
    """`root_id` и id всех его потомков на всю глубину. Обход помнит, где уже был: цикл в данных его не зацикливает."""
    child_id_list_by_parent: dict[Any, list] = {}
    for row in rows:
        child_id_list_by_parent.setdefault(row["parent_id"], []).append(row["id"])
    id_set, stack = {root_id}, [root_id]
    while stack:
        for child_id in child_id_list_by_parent.get(stack.pop(), []):
            if child_id not in id_set:
                id_set.add(child_id)
                stack.append(child_id)
    return id_set


def check_parent(rows: Iterable[dict], *, node_id: Any, parent_id: Any) -> None:
    """Узел `node_id` можно вложить в `parent_id`: родитель — не сам узел и не его потомок, иначе ValueError.
    В корень (`parent_id` — None) можно всегда, новый узел (`node_id` — None) — под любой: потомков у него нет."""
    if node_id is None or parent_id is None:
        return
    if parent_id in descendant_ids(rows, node_id):
        raise ValueError("Нельзя вложить узел в самого себя или в своего потомка")
