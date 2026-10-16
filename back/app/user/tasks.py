from core.broker import broker
from core.mailer import send_mail
from user import conf

TITLES = {
    "activation": "Код для подтверждения регистрации:",
    "reset": "Код для восстановления пароля:",
}


@broker.task
async def send_code(email: str, code: str, kind: str) -> None:
    await send_mail(
        email,
        "Код подтверждения",
        "confirmation_code",
        {
            "title": TITLES[kind],
            "code": code,
            "lifetime_minutes": int(conf.CONFIRMATION_CODE_LIFETIME.total_seconds() // 60),
        },
    )
