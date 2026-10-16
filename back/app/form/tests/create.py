from form.models import FormRequest, FormType


def create_form_type(name="Обратный звонок", code="callback", email_to="manager@example.com", is_trap=False, **kwargs) -> FormType:
    """Форма сайта. Ловушка по умолчанию выключена: с ней тест ждал бы 3 секунды до отправки,
    её проверяет отдельный тест."""
    return FormType.objects.create(name=name, code=code, email_to=email_to, is_trap=is_trap, **kwargs)


def create_form_request(form_type=None, name="Анна", phone="+79990001122", **kwargs) -> FormRequest:
    """Заявка с сайта. Форма — первая из уже созданных, нет ни одной — новая."""
    form_type = form_type or FormType.objects.first() or create_form_type()
    return FormRequest.objects.create(form_type=form_type, name=name, phone=phone, **kwargs)
