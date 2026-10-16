"""JWT-авторизация API: access — в заголовке Authorization, refresh — в куке httpOnly.

Каждый вход — сессия в базе (UserSession), её номер зашит в оба токена. Токен действует,
пока жива его сессия: выход удаляет сессию, и токены этого устройства перестают работать
сразу, а не когда истекут.

В эндпоинтах:
    async def endpoint(user: CurrentUser): ...         # 401 без валидного access-токена
    async def endpoint(user: OptionalUser): ...        # None для гостя
    async def endpoint(session: CurrentSession): ...   # сессия этого устройства, user — session.user
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

import jwt
from django.conf import settings
from fastapi import Depends, HTTPException, Request, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from user import conf
from user.models_async import CustomUser, UserSession

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

# auto_error=False: без токена отвечаем своим 401 на русском, а не 403 FastAPI
bearer = HTTPBearer(auto_error=False, description="Access-токен из /api/user/pair")


def create_token(user_id: int, session_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(timezone.utc)
    lifetime = conf.JWT_ACCESS_LIFETIME if token_type == "access" else conf.JWT_REFRESH_LIFETIME
    payload = {"user_id": user_id, "sid": str(session_id), "token_type": token_type, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


#: Refresh — в куке httpOnly, её ставит сам бэкенд: скрипты страницы её не видят, украсть через внедрённый
#: скрипт нельзя, а браузер шлёт её только на /refresh. Вход идёт из браузера прямо сюда, а не через сервер
#: сайта: лимит Traefik на вход считается по адресу посетителя. Сайт и бэкенд — на одном домене
#: (бэкенд — поддомен сайта), иначе браузер куку не пришлёт
REFRESH_COOKIE = "refresh"
REFRESH_COOKIE_PATH = "/api/user/refresh"
REFRESH_COOKIE_OPTIONS = {"path": REFRESH_COOKIE_PATH, "httponly": True, "samesite": "lax", "secure": settings.SESSION_COOKIE_SECURE}


def set_refresh_cookie(response: Response, session: UserSession) -> None:
    lifetime = int(conf.JWT_REFRESH_LIFETIME.total_seconds())
    token = create_token(session.user_id, session.id, "refresh")
    response.set_cookie(REFRESH_COOKIE, token, max_age=lifetime, **REFRESH_COOKIE_OPTIONS)


async def login(request: Request, response: Response, user_id: int) -> dict[str, str]:
    """Вход состоялся: новая сессия этого устройства, refresh — в куку ответа, access — в тело."""
    # Сессии, которые не продлевали дольше срока refresh, мертвы — убираем заодно, без отдельной уборки
    border = datetime.now(timezone.utc) - conf.JWT_REFRESH_LIFETIME
    await UserSession.filter(user_id=user_id, date_used__lt=border).delete()
    session = await UserSession.create(
        user_id=user_id, ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:500],
    )
    set_refresh_cookie(response, session)
    return {"access": create_token(user_id, session.id, "access")}


async def renew(response: Response, session: UserSession) -> dict[str, str]:
    """Продлить вход по refresh: новый access и новая кука на 30 дней — кто заходит, не вылетит через месяц."""
    await session.save(update_fields=["date_used"])  # auto_now: время последней активности
    set_refresh_cookie(response, session)
    return {"access": create_token(session.user_id, session.id, "access")}


def delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, **REFRESH_COOKIE_OPTIONS)


async def get_session_by_token(token: str, token_type: TokenType) -> UserSession | None:
    """Живая сессия активного пользователя по токену нужного типа (user уже загружен), иначе None.

    None, если токен подделан или истёк, другого типа (refresh живёт 30 дней и не должен
    работать как access), сессию удалили (выход), пользователь удалён или неактивен, либо
    токен выпущен до смены пароля. Запрос к базе один — как раньше за одним пользователем.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "user_id", "sid", "token_type"]},
        )
    except jwt.PyJWTError:
        return None
    if payload["token_type"] != token_type:
        return None

    session = await UserSession.get_or_none(
        id=payload["sid"], user_id=payload["user_id"], user__is_active=True,
    ).select_related("user")
    if session is None:
        return None
    # Пароль сменили в админке — сессии там не удаляются, поэтому сверяем ещё и время.
    # iat — целые секунды: токен, выпущенный в ту же секунду до смены пароля, ещё пройдёт
    changed_at = session.user.password_changed_at
    if changed_at and payload["iat"] < int(changed_at.timestamp()):
        return None
    return session


async def get_current_session(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> UserSession:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован", headers={"WWW-Authenticate": "Bearer"})
    session = await get_session_by_token(credentials.credentials, "access")
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Токен недействителен", headers={"WWW-Authenticate": "Bearer"})
    return session


async def get_current_user(session: UserSession = Depends(get_current_session)) -> CustomUser:
    return session.user


async def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> CustomUser | None:
    if credentials is None:
        return None
    session = await get_session_by_token(credentials.credentials, "access")
    return session.user if session else None


CurrentSession = Annotated[UserSession, Depends(get_current_session)]
CurrentUser = Annotated[CustomUser, Depends(get_current_user)]
OptionalUser = Annotated[CustomUser | None, Depends(get_optional_user)]
