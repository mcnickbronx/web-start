from django.test import SimpleTestCase

from core.tree import build_tree, check_parent, descendant_ids

# Строки — не по порядку: дерево обязано отсортировать их само
ROW_LIST = [
    {"id": 1, "parent_id": None, "title": "Двигатель", "sort_order": 20},
    {"id": 6, "parent_id": 1, "title": "Свечи", "sort_order": 0},
    {"id": 2, "parent_id": None, "title": "Кузов", "sort_order": 10},
    {"id": 3, "parent_id": 1, "title": "Фильтры", "sort_order": 0},
    {"id": 4, "parent_id": 3, "title": "Масляные", "sort_order": 0},
    {"id": 5, "parent_id": 99, "title": "Сирота", "sort_order": 30},
]


def titles(node_list, child_list="child_list"):
    return [(node["title"], titles(node[child_list], child_list)) for node in node_list]


class BuildTreeTest(SimpleTestCase):
    def test_order(self):
        """Дети под родителем, на каждом уровне — по полям `order` (равные — по следующему полю); без `order` — по id."""
        self.assertEqual(titles(build_tree(ROW_LIST, order=("sort_order", "id"))), [
            ("Кузов", []),
            ("Двигатель", [("Фильтры", [("Масляные", [])]), ("Свечи", [])]),
            ("Сирота", []),
        ])
        self.assertEqual(titles(build_tree(ROW_LIST)), [
            ("Двигатель", [("Фильтры", [("Масляные", [])]), ("Свечи", [])]),
            ("Кузов", []),
            ("Сирота", []),
        ])

    def test_orphan(self):
        """Родителя нет в списке (удалён, отфильтрован) — узел корнем, а не пропадает."""
        tree = build_tree(ROW_LIST)
        self.assertEqual(tree[-1]["title"], "Сирота")
        self.assertEqual(tree[-1]["parent_id"], 99)

    def test_rows_untouched(self):
        """Узел — копия строки: исходные строки не меняются, ключ детей — свой, если задан."""
        row_list_before = [dict(row) for row in ROW_LIST]
        tree = build_tree(ROW_LIST, child_list="item_list")
        self.assertEqual(ROW_LIST, row_list_before)
        self.assertEqual(titles(tree, "item_list")[0], ("Двигатель", [("Фильтры", [("Масляные", [])]), ("Свечи", [])]))

    def test_parent_id_required(self):
        """Строка без `parent_id` — ошибка, а не молча плоский список: забыли поле в `.values()`."""
        with self.assertRaises(KeyError):
            build_tree([{"id": 1}])
        with self.assertRaises(KeyError):
            descendant_ids([{"id": 1}], 1)


class DescendantIdsTest(SimpleTestCase):
    def test_depth(self):
        """Сам узел и потомки на всю глубину; лист — только он сам."""
        self.assertEqual(descendant_ids(ROW_LIST, 1), {1, 3, 4, 6})
        self.assertEqual(descendant_ids(ROW_LIST, 4), {4})

    def test_cycle_in_data(self):
        """Цикл, уже попавший в базу, не зацикливает ни обход, ни сборку: узлы цикла в дерево не выходят."""
        row_list = [{"id": 1, "parent_id": 2}, {"id": 2, "parent_id": 1}, {"id": 3, "parent_id": 3}, {"id": 4, "parent_id": 1}]
        self.assertEqual(descendant_ids(row_list, 1), {1, 2, 4})
        self.assertEqual(descendant_ids(row_list, 3), {3})
        self.assertEqual(build_tree(row_list), [{"id": 3, "parent_id": 3, "child_list": []}])  # сам себе родитель — корень


class CheckParentTest(SimpleTestCase):
    def test_cycle_refused(self):
        """Под себя и под своего потомка — ошибка."""
        for parent_id in (1, 3, 4):
            with self.subTest(parent_id=parent_id), self.assertRaises(ValueError):
                check_parent(ROW_LIST, node_id=1, parent_id=parent_id)

    def test_allowed(self):
        """Под соседа, под предка и в корень — можно; новый узел (`node_id` — None) — под любой."""
        check_parent(ROW_LIST, node_id=1, parent_id=2)
        check_parent(ROW_LIST, node_id=4, parent_id=1)
        check_parent(ROW_LIST, node_id=4, parent_id=None)
        check_parent(ROW_LIST, node_id=None, parent_id=1)
