"""Основа тестов API: настоящая база и клиент FastAPI."""
from django.test import TransactionTestCase
from starlette.testclient import TestClient

from core.broker import broker
from project.api import create_app


class ApiTestCase(TransactionTestCase):
    """Тест API. TransactionTestCase, а не TestCase: API читает базу через Tortoise по своему
    соединению и не видит незакоммиченного. Данные из хелперов create_* коммитятся сразу,
    после теста все таблицы очищаются.

        response = self.api.get("/api/page/list")
        response = self.api.get("/api/user/me", headers=auth_header(user))  # из user/tests/create.py
    """

    def setUp(self):
        # https: на сервере кука с refresh — только для HTTPS, клиент по http её бы не вернул
        self.api = self.enterContext(TestClient(create_app(), base_url="https://testserver"))

    def wait_tasks(self) -> None:
        """Дождаться фоновых задач: в тестах они выполняются в процессе API, без Redis."""
        self.api.portal.call(broker.wait_all)
