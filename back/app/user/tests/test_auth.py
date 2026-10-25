import asyncio
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.urls import reverse
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

    def register(self, email="new@example.com", **name):
        response = self.api.post("/api/user/register", json={"email": email, **name})
        self.wait_tasks()
        return response

    def activate(self, code, email="new@example.com", password=PASSWORD):
        return self.api.post("/api/user/activate", json={"email": email, "code": code, "password": password, "password_confirm": password})

    def test_register_and_activate(self):
        """Регистрация — без пароля, пароль задаёт активация: код из письма и пароль — и сразу вход."""
        self.assertEqual(self.register().status_code, 200)
        code = models.CustomUser.objects.get(email="new@example.com").confirmation_code
        self.assertIn(code, mail.outbox[0].body)
        self.assertEqual(self.login("new@example.com").status_code, 401)  # до подтверждения не войти

        response = self.activate(code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api.get("/api/user/me", headers={"Authorization": f"Bearer {response.json()['access']}"}).status_code, 200)
        self.assertEqual(self.login("new@example.com").status_code, 200)
        self.assertEqual(self.activate(code).status_code, 406)  # «уже активирован»

    def test_squatter_cannot_sign_in(self):
        """Кто первым зарегистрировал чужой адрес, своим паролем в аккаунт владельца не войдёт:
        пароль задаёт тот, кто ввёл код из письма."""
        self.api.post("/api/user/register", json={"email": "new@example.com", "password": "Chuzhoy-parol-2026", "password_confirm": "Chuzhoy-parol-2026"})
        self.wait_tasks()
        code = models.CustomUser.objects.get(email="new@example.com").confirmation_code  # пришёл владельцу почты
        self.assertEqual(self.activate(code).status_code, 200)
        self.assertEqual(self.login("new@example.com", "Chuzhoy-parol-2026").status_code, 401)
        self.assertEqual(self.login("new@example.com").status_code, 200)

    def test_register_again_while_waiting(self):
        """Адрес ждёт кода — повторная регистрация шлёт новый код, а не 422, и имя не меняет: чужой, повторив
        регистрацию с адресом владельца, своё имя в его аккаунт не впишет. Обратный случай — кто первым
        зарегистрировал чужой адрес, его имя и останется, пока владелец не поправит в профиле
        (test_squatter_name_fixed_in_profile)."""
        self.assertEqual(self.register(first_name="Анна", last_name="Смирнова").status_code, 200)
        self.assertEqual(self.register(first_name="Хакер").status_code, 406)  # в ту же минуту
        models.CustomUser.objects.update(confirmation_code_created_at=timezone.now() - conf.CONFIRMATION_CODE_RESEND_INTERVAL)
        self.assertEqual(self.register(first_name="Хакер", last_name="Хакеров").status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        user = models.CustomUser.objects.get(email="new@example.com")
        self.assertEqual((user.first_name, user.last_name), ("Анна", "Смирнова"))
        self.assertEqual(self.activate(user.confirmation_code).status_code, 200)
        user = models.CustomUser.objects.get(email="new@example.com")
        self.assertEqual((user.first_name, user.last_name), ("Анна", "Смирнова"))

    def test_squatter_name_fixed_in_profile(self):
        """Чужой зарегистрировал адрес первым — после активации у владельца его имя; владелец правит его в профиле."""
        self.register(first_name="Хакер")
        response = self.activate(models.CustomUser.objects.get(email="new@example.com").confirmation_code)
        access = {"Authorization": f"Bearer {response.json()['access']}"}
        response = self.api.patch("/api/user/me", json={"first_name": "Анна", "last_name": "Смирнова"}, headers=access)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["first_name"], response.json()["last_name"]), ("Анна", "Смирнова"))
        user = models.CustomUser.objects.get(email="new@example.com")
        self.assertEqual((user.first_name, user.last_name), ("Анна", "Смирнова"))

    def test_disabled_account_untouched(self):
        """Выключенный в админке аккаунт регистрация, повтор кода и активация не трогают — даже с верным кодом:
        у него, как у ждущего кода, снят is_active, а отличает их признак «Подтверждён»."""
        # Код остался от сброса пароля до выключения, повтор кода уже можно
        sent_at = timezone.now() - conf.CONFIRMATION_CODE_RESEND_INTERVAL
        user = create_user(is_active=False, confirmation_code="123456", confirmation_code_created_at=sent_at)
        self.assertEqual(self.error_field_list("/api/user/register", {"email": "user@example.com", "first_name": "Чужой"}), ["email"])
        response = self.activate("123456", email="user@example.com", password="Chuzhoy-parol-2026")
        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.json()["message"], "Аккаунт уже активирован")
        self.assertEqual(self.api.post("/api/user/activate/resend", json={"email": "user@example.com"}).status_code, 200)
        self.wait_tasks()
        self.assertEqual(len(mail.outbox), 0)

        saved = models.CustomUser.objects.get(id=user.id)
        self.assertEqual((saved.is_active, saved.first_name, saved.password), (False, "Анна", user.password))
        self.assertEqual(self.login().status_code, 401)

    def admin_save(self, email: str, is_active: bool, **changes) -> None:
        """Сохранить пользователя в админке: форма изменения, как её отправит админ."""
        user = models.CustomUser.objects.get(email=email)
        data = {
            "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
            "confirmation_code": user.confirmation_code or "", "confirmation_code_attempts": user.confirmation_code_attempts,
            "usersession_set-TOTAL_FORMS": 0, "usersession_set-INITIAL_FORMS": 0, **({"is_active": "on"} if is_active else {}), **changes,
        }
        response = self.client.post(reverse("admin:user_customuser_change", args=[user.id]), data)
        self.assertEqual(response.status_code, 302)  # сохранилось, а не вернулось с ошибками формы

    def test_enabled_by_admin_is_confirmed(self):
        """Админ включил ждущего кода — ручается за адрес: «Подтверждён» ставится сама. Выключил потом — аккаунт
        выключенный, а не ждущий кода: регистрация, повтор кода и активация его не включают."""
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        self.register(first_name="Анна")
        models.CustomUser.objects.update(confirmation_code_created_at=timezone.now() - conf.CONFIRMATION_CODE_RESEND_INTERVAL)
        code = models.CustomUser.objects.get(email="new@example.com").confirmation_code
        self.admin_save("new@example.com", is_active=True)
        self.assertTrue(models.CustomUser.objects.get(email="new@example.com").is_confirmed)
        # Пароля у него нет — входит через «Забыли пароль»
        self.assertEqual(self.api.post("/api/user/password/reset", json={"email": "new@example.com"}).status_code, 200)
        self.wait_tasks()
        reset = {"email": "new@example.com", "code": models.CustomUser.objects.get(email="new@example.com").confirmation_code,
                 "password_new": PASSWORD, "password_new_confirm": PASSWORD}
        self.assertEqual(self.api.post("/api/user/password/reset/confirm", json=reset).status_code, 200)
        self.assertEqual(self.login("new@example.com").status_code, 200)
        self.admin_save("new@example.com", is_active=False)

        self.assertEqual(self.error_field_list("/api/user/register", {"email": "new@example.com", "first_name": "Чужой"}), ["email"])
        self.assertEqual(self.api.post("/api/user/activate/resend", json={"email": "new@example.com"}).status_code, 200)
        self.wait_tasks()
        self.assertEqual(len(mail.outbox), 2)  # письма регистрации и сброса пароля, нового кода нет
        response = self.activate(code)
        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.json()["message"], "Аккаунт уже активирован")
        user = models.CustomUser.objects.get(email="new@example.com")
        self.assertEqual((user.is_active, user.first_name), (False, "Анна"))
        self.assertEqual(self.login("new@example.com").status_code, 401)

    def test_admin_edit_keeps_waiting(self):
        """Админ поправил ждущему кода имя, «Активен» не трогал — тот по-прежнему ждёт кода и активируется сам."""
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))
        self.register(first_name="Анна")
        self.admin_save("new@example.com", is_active=False, first_name="Мария")
        user = models.CustomUser.objects.get(email="new@example.com")
        self.assertEqual((user.first_name, user.is_confirmed), ("Мария", False))
        self.assertEqual(self.activate(user.confirmation_code).status_code, 200)

    def test_weak_password_keeps_code_attempt(self):
        """Пароль проверяется до кода: слабый пароль — 422 у поля, попытка кода не тратится."""
        self.register()
        code = models.CustomUser.objects.get(email="new@example.com").confirmation_code
        weak = {"email": "new@example.com", "code": code, "password": "12345678", "password_confirm": "12345678"}
        self.assertEqual(self.error_field_list("/api/user/activate", weak), ["password"])
        self.assertEqual(models.CustomUser.objects.get(email="new@example.com").confirmation_code_attempts, 0)
        # Без пароля активации нет
        self.assertEqual(self.error_field_list("/api/user/activate", {"email": "new@example.com", "code": code}), ["password", "password_confirm"])
        self.assertEqual(self.activate(code).status_code, 200)

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
        self.assertEqual(self.error_field_list("/api/user/register", {"email": "user@example.com"}), ["email"])
        mismatch = {"email": "new@example.com", "code": "123456", "password": PASSWORD, "password_confirm": "Drugoy-parol-2026"}
        self.assertEqual(self.error_field_list("/api/user/activate", mismatch), ["password_confirm"])
        # Нет такого email — ответ как на неверный код
        nobody = {"email": "nobody@example.com", "code": "123456", "password": PASSWORD, "password_confirm": PASSWORD}
        self.assertEqual(self.error_field_list("/api/user/activate", nobody), ["code"])

    def test_code_only_digits(self):
        """Код из цифр другого алфавита — 422 у поля, а не 500: сравнение кодов на таких символах падает."""
        self.register()
        digits = {"email": "new@example.com", "code": "１２３４５６", "password": PASSWORD, "password_confirm": PASSWORD}
        self.assertEqual(self.error_field_list("/api/user/activate", digits), ["code"])

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
