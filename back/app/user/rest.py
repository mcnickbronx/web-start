from uuid import UUID

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from core.schemas import MessageOut
from user import auth, services
from user.auth import CurrentSession, CurrentUser, get_session_by_token
from user.schemas import (
    CodeIn,
    EmailIn,
    PasswordChangeIn,
    PasswordResetConfirmIn,
    RegisterIn,
    SessionOut,
    TokenOut,
    TokenPairIn,
    UserMeOut,
    UserUpdateIn,
)

router = APIRouter()

UNAUTHORIZED = {401: {"model": MessageOut, "description": "Нет токена или он недействителен"}}
BUSINESS = {406: {"model": MessageOut, "description": "Сообщение пользователю"}}


@router.post("/register", response_model=MessageOut, summary="Регистрация",
             description="Создаёт неактивного пользователя и отправляет код подтверждения на почту. "
                         "Дальше — /activate. Код живёт 30 минут.")
async def register(data: RegisterIn):
    await services.register(data.email, data.password, data.first_name, data.last_name)
    return {"message": "Код подтверждения отправлен на почту"}


@router.post("/activate", response_model=TokenOut, summary="Подтверждение регистрации", responses=BUSINESS,
             description="Активирует аккаунт по коду из письма и сразу входит: access — в ответе, "
                         "refresh — в куке.")
async def activate(data: CodeIn, request: Request, response: Response):
    user = await services.activate(data.email, data.code)
    return await auth.login(request, response, user.id)


@router.post("/activate/resend", response_model=MessageOut, summary="Выслать код ещё раз", responses=BUSINESS,
             description="Новый код подтверждения на почту. Не чаще раза в минуту: раньше — 406 с временем ожидания. "
                         "Такого email нет или он уже активирован — ответ как при отправке, письма нет.")
async def activate_resend(data: EmailIn):
    await services.resend_activation_code(data.email)
    return {"message": "Если аккаунт ждёт подтверждения, код отправлен на почту"}


@router.post("/pair", response_model=TokenOut, summary="Вход",
             responses={401: {"model": MessageOut, "description": "Неверный email или пароль"}},
             description="Новая сессия этого устройства: access — в ответе, refresh — в куке httpOnly, её видит "
                         "только браузер. Из браузера — с `credentials: 'include'`, иначе кука не сохранится.")
async def token_pair(data: TokenPairIn, request: Request, response: Response):
    user = await services.authenticate(data.email, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return await auth.login(request, response, user.id)


@router.post("/refresh", response_model=TokenOut, summary="Новый access-токен", responses=UNAUTHORIZED,
             description="По refresh из куки, тело не нужно. Продлевает и саму куку на 30 дней. "
                         "Из браузера — с `credentials: 'include'`.")
async def token_refresh(response: Response, refresh: str | None = Cookie(None, alias=auth.REFRESH_COOKIE, include_in_schema=False)):
    session = await get_session_by_token(refresh, "refresh") if refresh else None
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нужно войти заново")
    return await auth.renew(response, session)


@router.post("/logout", response_model=MessageOut, summary="Выход", responses=UNAUTHORIZED,
             description="Завершает сессию этого устройства: его access и refresh перестают работать сразу.")
async def logout(session: CurrentSession, response: Response):
    await services.end_session(session.user, session.id)
    auth.delete_refresh_cookie(response)
    return {"message": "Вы вышли"}


@router.post("/logout/all", response_model=MessageOut, summary="Выход на всех устройствах", responses=UNAUTHORIZED,
             description="Завершает все сессии пользователя, этого устройства тоже.")
async def logout_all(user: CurrentUser, response: Response):
    await services.end_all_sessions(user)
    auth.delete_refresh_cookie(response)
    return {"message": "Вы вышли на всех устройствах"}


@router.get("/session/list", response_model=list[SessionOut], summary="Где я вошёл", responses=UNAUTHORIZED,
            description="Сессии пользователя, сначала недавние. Это устройство — `is_current`.")
async def session_list(session: CurrentSession):
    return await services.session_list(session)


@router.delete("/session/{session_id}", response_model=MessageOut, summary="Выйти на одном устройстве",
               responses=UNAUTHORIZED | {404: {"model": MessageOut, "description": "Сессии нет или она чужая"}},
               description="Завершает сессию из `/session/list`: токены того устройства перестают работать сразу.")
async def session_end(session_id: UUID, user: CurrentUser):
    await services.end_session(user, session_id)
    return {"message": "Сессия завершена"}


@router.get("/me", response_model=UserMeOut, summary="Текущий пользователь", responses=UNAUTHORIZED)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserMeOut, summary="Изменить профиль", responses=UNAUTHORIZED)
async def me_update(data: UserUpdateIn, user: CurrentUser):
    return await services.update_profile(user, data.model_dump(exclude_unset=True))


@router.post("/password/change", response_model=TokenOut, summary="Смена пароля", responses=UNAUTHORIZED,
             description="Меняет пароль и завершает все сессии, на других устройствах — выход. Это устройство "
                         "входит заново: access — в ответе, refresh — в куке.")
async def password_change(data: PasswordChangeIn, user: CurrentUser, request: Request, response: Response):
    await services.change_password(user, data.password_current, data.password_new)
    return await auth.login(request, response, user.id)


@router.post("/password/reset", response_model=MessageOut, summary="Забыли пароль", responses=BUSINESS,
             description="Отправляет код на почту, дальше — /password/reset/confirm. Не чаще раза в минуту: "
                         "раньше — 406 с временем ожидания. Такого аккаунта нет — ответ как при отправке, письма нет.")
async def password_reset(data: EmailIn):
    await services.request_password_reset(data.email)
    return {"message": "Если аккаунт существует, код отправлен на почту"}


@router.post("/password/reset/confirm", response_model=TokenOut, summary="Новый пароль по коду",
             responses=BUSINESS,
             description="Ставит новый пароль по коду из письма, завершает все сессии и сразу входит: access — "
                         "в ответе, refresh — в куке.")
async def password_reset_confirm(data: PasswordResetConfirmIn, request: Request, response: Response):
    user = await services.confirm_password_reset(data.email, data.code, data.password_new)
    return await auth.login(request, response, user.id)
