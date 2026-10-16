from user.models import CustomUser

#: Пароль пользователей из хелперов — проходит проверки Django на сложность
PASSWORD = "Kp7-vesna-2026"


def create_user(email="user@example.com", password=PASSWORD, first_name="Анна", last_name="Смирнова", **kwargs) -> CustomUser:
    """Активный пользователь: входит по email и PASSWORD."""
    return CustomUser.objects.create_user(email, password, first_name=first_name, last_name=last_name, **kwargs)
