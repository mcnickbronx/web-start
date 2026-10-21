import asyncio
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.utils import timezone

from core.tests.api import ApiTestCase
from user import conf, models, models_async
from user.services import issue_code
from user.tests.create import PASSWORD, auth_header, create_user


class AuthTest(ApiTestCase):
    def login(self, email="user@example.com", password=PASSWORD):
        return self.api.post("/api/user/pair", json={"email": email, "password": password})

    def error_field_list(self, path: str, body: dict) -> list[str]:
        response = self.api.post(path, json=body)
        self.assertEqual(response.status_code, 422)
        return [error["loc"] for error in response.json()["full_error"]]

    def test_login_and_me(self):
        create_user()
        access = self.login(email="User@Example.com").json()["access"]  # email — без учёта регистра
        response = self.api.get("/api/user/me", headers={"Authorization": f"Bearer {access}"})
        self.assertEqual(response.json()["email"], "user@example.com")

    def test_wrong_password(self):
        create_user()
        response = self.login(password="не-тот-пароль")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"message": "Неверный email или пароль"})

    def test_refresh_in_cookie(self):
        create_user()
        response = self.login()
        self.assertEqual(set(response.json()), {"access"})  # refresh скриптам страницы не отдаётся
        cookie = response.headers["set-cookie"]
        # Secure — как у куки сессии админки: на сервере есть, локально по HTTP (DEBUG) — нет
        for part in ("refresh=", "HttpOnly", "Path=/api/user/refresh", "SameSite=lax"):
            self.assertIn(part, cookie)
        response = self.api.post("/api/user/refresh")  # по куке, без тела
        self.assertIn("access", response.json())
        self.assertIn("refresh=", response.headers["set-cookie"])  # кука продлена на полный срок refresh

        # access вместо refresh не годится: он живёт сутки, refresh — месяц
        self.api.cookies.set("refresh", response.json()["access"])
        self.assertEqual(self.api.post("/api/user/refresh").status_code, 401)

    def test_refresh_lifetime(self):
        # Срок refresh задаёт и куку, и уборку: сессию, где не заходили дольше срока, удаляет следующий вход
        create_user()
        self.login()
        models.UserSession.objects.update(date_used=timezone.now() - timedelta(days=8))
        with mock.patch.object(conf, "JWT_REFRESH_LIFETIME", timedelta(days=7)):
            response = self.login()
        self.assertIn("Max-Age=604800", response.headers["set-cookie"])
        self.assertEqual(models.UserSession.objects.count(), 1)

    def test_logout_revokes_tokens_at_once(self):
        create_user()
        access = {"Authorization": f"Bearer {self.login().json()['access']}"}
        self.assertEqual(self.api.post("/api/user/logout", headers=access).status_code, 200)
        self.assertEqual(self.api.get("/api/user/me", headers=access).status_code, 401)  # сразу, не через сутки
        self.assertEqual(self.api.post("/api/user/refresh").status_code, 401)

    def test_sessions(self):
        create_user()
        phone = {"Authorization": f"Bearer {self.login().json()['access']}"}
        laptop = {"Authorization": f"Bearer {self.login().json()['access']}"}
        session_list = self.api.get("/api/user/session/list", headers=laptop).json()
        self.assertEqual([session["is_current"] for session in session_list], [True, False])

        # Выйти на телефоне с ноутбука: телефон — сразу на вход, ноутбук работает
        response = self.api.delete(f"/api/user/session/{session_list[1]['id']}", headers=laptop)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api.get("/api/user/me", headers=phone).status_code, 401)
        self.assertEqual(self.api.get("/api/user/me", headers=laptop).status_code, 200)

        self.assertEqual(self.api.post("/api/user/logout/all", headers=laptop).status_code, 200)
        self.assertEqual(self.api.get("/api/user/me", headers=laptop).status_code, 401)

    def test_register_and_activate(self):
        body = {"email": "new@example.com", "password": PASSWORD, "password_confirm": PASSWORD}
        self.assertEqual(self.api.post("/api/user/register", json=body).status_code, 200)
        self.wait_tasks()
        code = models.CustomUser.objects.get(email="new@example.com").confirmation_code
        self.assertIn(code, mail.outbox[0].body)
        self.assertEqual(self.login("new@example.com").status_code, 401)  # до подтверждения не войти

        response = self.api.post("/api/user/activate", json={"email": "new@example.com", "code": code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.login("new@example.com").status_code, 200)

    def test_password_change_revokes_tokens(self):
        user = create_user()
        old = auth_header(user)
        body = {"password_current": PASSWORD, "password_new": "Nov-parol-2026", "password_new_confirm": "Nov-parol-2026"}
        new_access = self.api.post("/api/user/password/change", headers=old, json=body).json()["access"]
        self.assertEqual(self.api.get("/api/user/me", headers=old).status_code, 401)
        self.assertEqual(self.api.get("/api/user/me", headers={"Authorization": f"Bearer {new_access}"}).status_code, 200)

    def test_field_errors(self):
        """Ошибка про поле — 422 у этого поля: сайт покажет её под ним, а не общим сообщением."""
        create_user()
        taken = {"email": "user@example.com", "password": PASSWORD, "password_confirm": PASSWORD}
        self.assertEqual(self.error_field_list("/api/user/register", taken), ["email"])
        mismatch = {"email": "new@example.com", "password": PASSWORD, "password_confirm": "Drugoy-parol-2026"}
        self.assertEqual(self.error_field_list("/api/user/register", mismatch), ["password_confirm"])
        # Нет такого email — ответ как на неверный код
        self.assertEqual(self.error_field_list("/api/user/activate", {"email": "nobody@example.com", "code": "123456"}), ["code"])

    def test_code_only_digits(self):
        """Код из цифр другого алфавита — 422 у поля, а не 500: сравнение кодов на таких символах падает."""
        self.api.post("/api/user/register", json={"email": "new@example.com", "password": PASSWORD, "password_confirm": PASSWORD})
        self.wait_tasks()
        self.assertEqual(self.error_field_list("/api/user/activate", {"email": "new@example.com", "code": "１２３４５６"}), ["code"])

    def test_code_resend_once_a_minute(self):
        """Повтор кода в ту же минуту — 406 с временем ожидания, а не «код отправлен» без письма:
        у кого кончились попытки, тот ждал бы письмо, которое не придёт."""
        create_user()
        reset = lambda email: self.api.post("/api/user/password/reset", json={"email": email})  # noqa: E731
        self.assertEqual(reset("user@example.com").status_code, 200)
        response = reset("user@example.com")
        self.assertEqual(response.status_code, 406)
        self.assertIn("повторите через", response.json()["message"])
        self.assertEqual(reset("nobody@example.com").status_code, 200)  # такого email нет — ответ как при отправке
        self.wait_tasks()
        self.assertEqual(len(mail.outbox), 1)

    def test_simultaneous_code_requests(self):
        """Два одновременных запроса кода — одно письмо, второй получает 406: иначе код из первого
        письма уже не подошёл бы."""
        create_user()

        async def request_twice():
            # У каждого запроса свой объект пользователя, как в API
            user_list = [await models_async.CustomUser.get(email="user@example.com") for _ in range(2)]
            return await asyncio.gather(*(issue_code(user, "reset") for user in user_list), return_exceptions=True)

        error_list = [result for result in self.api.portal.call(request_twice) if result is not None]
        self.assertEqual([error.status_code for error in error_list], [406])
        self.wait_tasks()
        self.assertEqual(len(mail.outbox), 1)

    def test_code_not_kept_when_mail_not_queued(self):
        """Письмо не встало в очередь (Redis недоступен) — код не сохраняется: повтор сразу пришлёт
        новый, а не ответит «уже отправлен», хотя письма не было."""
        create_user()
        with (
            self.assertLogs("core.errors", "ERROR"),  # сбой — в журнал, а не трейсбеком в вывод тестов
            mock.patch("user.services.send_code.kiq", side_effect=ConnectionError),
            self.assertRaises(ConnectionError),
        ):
            self.api.post("/api/user/password/reset", json={"email": "user@example.com"})
        self.assertEqual(self.api.post("/api/user/password/reset", json={"email": "user@example.com"}).status_code, 200)
