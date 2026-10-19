"""История изменений заявок: правки статуса в админке и сервис с декоратором @history."""
import asyncio

from django.test import TestCase
from django.urls import reverse
from tortoise.transactions import in_transaction

from core.bridge import with_sync
from core.history import history
from core.tests.api import ApiTestCase
from form import models_async
from form.models import FormRequestHistory
from form.tests.create import create_form_request
from user.tests.create import create_user


class AdminHistoryTest(TestCase):
    def setUp(self):
        self.admin = create_user(email="admin@example.com", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.request = create_form_request()

    def test_change_form(self):
        """Статус сменили в карточке — в истории кто и было → стало, на странице — блок «История»."""
        url = reverse("admin:form_formrequest_change", args=[self.request.id])
        management = {f"{prefix}-{key}": "0" for prefix in ("formfile_set", "history") for key in ("TOTAL_FORMS", "INITIAL_FORMS")}
        self.client.post(url, {"status": "work", "_continue": "1", **management})
        record = FormRequestHistory.objects.get()
        self.assertEqual((record.user, record.changes), (self.admin, {"status": ["new", "work"]}))
        self.assertContains(self.client.get(url), "Статус: Новая → В работе")

    def test_list_editable(self):
        """Статус сменили прямо в списке — тоже в истории."""
        self.client.post(reverse("admin:form_formrequest_changelist"), {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
            "form-0-id": str(self.request.id), "form-0-status": "done", "_save": "1",
        })
        self.assertEqual(FormRequestHistory.objects.get().changes, {"status": ["new", "done"]})

    def test_no_change_no_record(self):
        """Сохранили без правок — строки нет."""
        management = {f"{prefix}-{key}": "0" for prefix in ("formfile_set", "history") for key in ("TOTAL_FORMS", "INITIAL_FORMS")}
        response = self.client.post(reverse("admin:form_formrequest_change", args=[self.request.id]), {"status": "new", **management})
        self.assertEqual(response.status_code, 302)  # сохранилось, а не вернулось с ошибкой формы
        self.assertFalse(FormRequestHistory.objects.exists())

    def test_delete_with_record(self):
        """Заявку удалили в админке — её история уходит с ней."""
        self.request.history.create(changes={"status": ["new", "work"]})
        self.client.post(reverse("admin:form_formrequest_delete", args=[self.request.id]), {"post": "yes"})
        self.assertFalse(FormRequestHistory.objects.exists())


@with_sync
@history(models_async.FormRequestHistory, ["status"])
async def set_status(form_request_id: int, status: str, user=None) -> None:
    """Сервис для проверки декоратора: статус заявок меняет только админка, своего сервиса у form нет."""
    await models_async.FormRequest.filter(id=form_request_id).update(status=status)


class ServiceHistoryTest(ApiTestCase):
    def test_service(self):
        """Сервис поменял статус через filter().update() — декоратор всё равно видит разницу."""
        user = create_user()
        request = create_form_request()
        self.api.portal.call(set_status, request.id, "work", user)
        record = FormRequestHistory.objects.get()
        self.assertEqual((record.user, record.changes), (user, {"status": ["new", "work"]}))

    def test_unchanged(self):
        """Сервис ничего не поменял — строки нет."""
        request = create_form_request()
        self.api.portal.call(set_status, request.id, "new")
        self.assertFalse(FormRequestHistory.objects.exists())

    def test_hidden(self):
        """Скрытое поле (телефон) — только факт изменения, без значений."""
        @history(models_async.FormRequestHistory, ["phone", "status"], hidden=["phone"])
        async def change(form_request_id: int):
            await models_async.FormRequest.filter(id=form_request_id).update(phone="+79990000000", status="work")

        request = create_form_request()
        self.api.portal.call(change, request.id)
        self.assertEqual(FormRequestHistory.objects.get().changes, {"phone": None, "status": ["new", "work"]})

    def test_concurrent(self):
        """Строку «до» сервис читает с блокировкой: ждёт чужую правку, и «было» у него — её результат."""
        request = create_form_request()

        async def race():
            changed = asyncio.Event()

            async def other():  # чужая правка держит строку 0,3 с
                async with in_transaction():
                    await models_async.FormRequest.filter(id=request.id).update(status="work")
                    changed.set()
                    await asyncio.sleep(0.3)

            async def service():
                await changed.wait()
                await set_status(request.id, "done")

            await asyncio.gather(other(), service())

        self.api.portal.call(race)
        self.assertEqual(FormRequestHistory.objects.get().changes, {"status": ["work", "done"]})

    def test_sync_from_admin_code(self):
        """Тот же сервис из админки и команд — .sync(), история та же, кто — None (система)."""
        request = create_form_request()
        set_status.sync(request.id, "spam")
        record = FormRequestHistory.objects.get()
        self.assertEqual((record.user, record.changes), (None, {"status": ["new", "spam"]}))
