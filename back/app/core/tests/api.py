"""Основа тестов API: настоящая база и клиент FastAPI."""
from django.test import TransactionTestCase
from starlette.testclient import TestClient

from core.broker import broker
from project.api import create_app
from user.auth import create_token
from user.models import UserSession


class ApiTestCase(TransactionTestCase):
    """Тест API. TransactionTestCase, а не TestCase: API читает базу через Tortoise по своему
    соединению и не видит незакоммиченного. Данные из хелперов create_* коммитятся сразу,
    после теста все таблицы очищаются.

        response = self.api.get("/api/page/list")
        response = self.api.get("/api/user/me", headers=self.auth(user))
    """

    def setUp(self):
        # https: на сервере кука с refresh — только для HTTPS, клиент по http её бы не вернул
        self.api = self.enterContext(TestClient(create_app(), base_url="https://testserver"))

    @staticmethod
    def auth(user) -> dict[str, str]:
        """Заголовок с access-токеном новой сессии пользователя — как после входа."""
        session = UserSession.objects.create(user=user)
        return {"Authorization": f"Bearer {create_token(user.id, session.id, 'access')}"}

    def wait_tasks(self) -> None:
        """Дождаться фоновых задач: в тестах они выполняются в процессе API, без Redis."""
        self.api.portal.call(broker.wait_all)
