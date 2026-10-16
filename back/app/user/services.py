"""Логика модуля «Пользователи» для API."""
import asyncio
import secrets
from datetime import datetime, timezone

from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from fastapi import HTTPException
from tortoise.exceptions import IntegrityError
from tortoise.expressions import F
from tortoise.transactions import in_transaction

from core.errors import field_error
from core.user_agent import describe_user_agent
from user import conf
from user.models_async import CustomUser, UserSession
from user.tasks import send_code


def _check_password(password: str, encoded: str) -> tuple[bool, str | None]:
    """(совпал ли пароль, новый хеш — если Django сменил алгоритм или число итераций)."""
    if not check_password(password, encoded):
        return False, None
    if identify_hasher(encoded).must_update(encoded):
        return True, make_password(password)
    return True, None


async def authenticate(email: str, password: str) -> CustomUser | None:
    """Пользователь по email и паролю. Хеши — хешерами Django: пароль из админки работает в API."""
    user = await CustomUser.get_or_none(email=email, is_active=True)
    if user is None:
        # Хешируем впустую, чтобы по времени ответа нельзя было понять, есть ли такой email
        await asyncio.to_thread(make_password, password)
        return None

    # Хеширование — сотни миллисекунд CPU, в потоке, чтобы не блокировать event loop
    is_valid, new_hash = await asyncio.to_thread(_check_password, password, user.password)
    if not is_valid:
        return None

    user.last_login = datetime.now(timezone.utc)
    update_fields = ["last_login"]
    if new_hash:
        # Не смена пароля, а обновление хеша — токены остаются в силе
        user.password = new_hash
        update_fields.append("password")
    await user.save(update_fields=update_fields)
    return user


async def _validate_password(password: str, field: str) -> None:
    """Пароль проходит проверки Django на сложность, иначе 422 у поля field."""
    try:
        await asyncio.to_thread(validate_password, password)
    except ValidationError as exc:
        raise field_error({field: " ".join(exc.messages)}) from exc


def _wrong_code() -> HTTPException:
    """Неверный код — и когда такого email нет: проверить надо и адрес, и код."""
    return field_error({"code": "Неверный код"})


async def update_profile(user: CustomUser, data: dict) -> CustomUser:
    if data:
        user.update_from_dict(data)
        await user.save(update_fields=list(data))
    return user


async def set_password(user: CustomUser, password: str) -> None:
    """Новый пароль. Все выданные токены после этого недействительны."""
    await _validate_password(password, "password_new")
    user.password = await asyncio.to_thread(make_password, password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.confirmation_code = None
    user.confirmation_code_created_at = None
    await user.save(update_fields=["password", "password_changed_at", "confirmation_code", "confirmation_code_created_at"])
    # Выход на всех устройствах: новую сессию этому устройству выдаст вход сразу после смены
    await UserSession.filter(user_id=user.id).delete()


async def issue_code(user: CustomUser, kind: str) -> None:
    """Выдать код подтверждения и отправить письмо фоновой задачей. Чаще раза в минуту — 406.

    Строка пользователя — под замком до конца транзакции: из одновременных запросов второй дождётся
    первого и получит 406. Письмо не встало в очередь — откатится и код: повтор пришлёт новый.
    """
    async with in_transaction():
        user = await CustomUser.select_for_update().get(id=user.id)
        sent_at = user.confirmation_code_created_at
        if sent_at and datetime.now(timezone.utc) - sent_at < conf.CONFIRMATION_CODE_RESEND_INTERVAL:
            wait = conf.CONFIRMATION_CODE_RESEND_INTERVAL - (datetime.now(timezone.utc) - sent_at)
            raise HTTPException(406, f"Код уже отправлен, повторите через {int(wait.total_seconds()) + 1} сек")

        user.confirmation_code = f"{secrets.randbelow(900_000) + 100_000}"
        user.confirmation_code_created_at = datetime.now(timezone.utc)
        user.confirmation_code_attempts = 0
        await user.save(update_fields=["confirmation_code", "confirmation_code_created_at", "confirmation_code_attempts"])
        await send_code.kiq(user.email, user.confirmation_code, kind)


async def check_code(user: CustomUser, code: str) -> None:
    """Код верный и не просрочен. Неверный — 422 у поля code, кончились попытки или срок — 406.
    Попытки ограничены — защита от перебора."""
    if not user.confirmation_code:
        raise _wrong_code()
    # Счётчик увеличивает сама база: параллельные запросы не проскочат лимит
    is_counted = await CustomUser.filter(
        id=user.id, confirmation_code_attempts__lt=conf.CONFIRMATION_CODE_ATTEMPTS,
    ).update(confirmation_code_attempts=F("confirmation_code_attempts") + 1)
    if not is_counted:
        raise HTTPException(406, "Превышено число попыток, запросите новый код")
    if not secrets.compare_digest(user.confirmation_code, code):
        raise _wrong_code()
    if datetime.now(timezone.utc) - user.confirmation_code_created_at > conf.CONFIRMATION_CODE_LIFETIME:
        raise HTTPException(406, "Срок действия кода истёк, запросите новый")


async def register(email: str, password: str, first_name: str, last_name: str) -> CustomUser:
    """Неактивный пользователь и код подтверждения на почту."""
    try:
        validate_email(email)
    except ValidationError as exc:
        raise field_error({"email": "Некорректный email"}) from exc
    email_taken = field_error({"email": "Пользователь с таким email уже зарегистрирован"})
    if await CustomUser.filter(email=email).exists():
        raise email_taken
    await _validate_password(password, "password")

    try:
        user = await CustomUser.create(
            email=email,
            password=await asyncio.to_thread(make_password, password),
            first_name=first_name,
            last_name=last_name,
            is_active=False,
            password_changed_at=datetime.now(timezone.utc),
        )
    except IntegrityError as exc:
        # Два одновременных запроса с одним email: проверку выше прошли оба
        raise email_taken from exc
    await issue_code(user, "activation")
    return user


async def activate(email: str, code: str) -> CustomUser:
    user = await CustomUser.get_or_none(email=email)
    if user is None:
        raise _wrong_code()
    if user.is_active:
        raise HTTPException(406, "Аккаунт уже активирован")

    await check_code(user, code)
    user.is_active = True
    user.confirmation_code = None
    user.confirmation_code_created_at = None
    await user.save(update_fields=["is_active", "confirmation_code", "confirmation_code_created_at"])
    return user


async def resend_activation_code(email: str) -> None:
    user = await CustomUser.get_or_none(email=email, is_active=False)
    if user is None:
        # Не сообщаем, есть ли такой email и активирован ли он
        return
    await issue_code(user, "activation")


async def request_password_reset(email: str) -> None:
    user = await CustomUser.get_or_none(email=email, is_active=True)
    if user is None:
        return
    await issue_code(user, "reset")


async def confirm_password_reset(email: str, code: str, password: str) -> CustomUser:
    user = await CustomUser.get_or_none(email=email, is_active=True)
    if user is None:
        raise _wrong_code()
    await check_code(user, code)
    await set_password(user, password)
    return user


async def change_password(user: CustomUser, current: str, new: str) -> CustomUser:
    is_valid, _ = await asyncio.to_thread(_check_password, current, user.password)
    if not is_valid:
        raise field_error({"password_current": "Текущий пароль неверен"})
    await set_password(user, new)
    return user


# --- Сессии: где пользователь вошёл ---------------------------------------------------------

async def session_list(current: UserSession) -> list[dict]:
    """Входы пользователя, сначала недавние. Текущее устройство — is_current."""
    return [
        {
            "id": session.id, "device": describe_user_agent(session.user_agent), "ip": session.ip,
            "date_add": session.date_add, "date_used": session.date_used, "is_current": session.id == current.id,
        }
        for session in await UserSession.filter(user_id=current.user_id)
    ]


async def end_session(user: CustomUser, session_id) -> None:
    """Выйти на одном устройстве: его токены перестают работать сразу. Чужую сессию не найти — 404."""
    if not await UserSession.filter(id=session_id, user_id=user.id).delete():
        raise HTTPException(404, "Сессия не найдена")


async def end_all_sessions(user: CustomUser) -> None:
    """Выйти на всех устройствах, этом тоже."""
    await UserSession.filter(user_id=user.id).delete()
