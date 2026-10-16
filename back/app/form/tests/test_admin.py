"""Список заявок в админке: фильтр «Форма» (пакет django-admin-filter-kit) и его подсказки."""
from django.test import TestCase
from django.urls import reverse

from form.tests.create import create_form_request, create_form_type
from user.tests.create import create_user


class FormRequestAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(create_user(email="admin@example.com", is_staff=True, is_superuser=True))

    def test_form_filter(self):
        callback = create_form_type()
        feedback = create_form_type("Обратная связь", code="feedback")
        create_form_request(form_type=callback, phone="+79990000001")
        create_form_request(form_type=feedback, phone="+79990000002")
        url = reverse("admin:form_formrequest_changelist")
        response = self.client.get(url)
        self.assertContains(response, 'data-lookup="form_type__id__exact"')
        self.assertContains(response, "admin_filter_kit/collapse.js")  # сворачиваемая панель фильтров
        response = self.client.get(url, {"form_type__id__exact": feedback.pk})
        self.assertContains(response, "+79990000002")
        self.assertNotContains(response, "+79990000001")

    def test_form_suggestions(self):
        create_form_type()
        create_form_type("Обратная связь", code="feedback")
        response = self.client.get(reverse("admin:autocomplete"), {
            "term": "связ", "app_label": "form", "model_name": "formrequest", "field_name": "form_type",
        })
        self.assertEqual([item["text"] for item in response.json()["results"]], ["Обратная связь"])
