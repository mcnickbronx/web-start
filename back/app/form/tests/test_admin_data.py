"""Поиск и следы ручной работы с данными в штатной админке Django."""
import re

from django.contrib import admin
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from form.models import FormRequest
from form.tests.create import create_form_request
from user.models import CustomUser, UserSession
from user.tests.create import create_user


class AdminDataTest(TestCase):
    def test_email_search_finds_mixed_ascii_case_in_requests_and_users(self):
        record = create_form_request(email="MiXeD.Reader@example.com")
        user = create_user(email="MiXeD.Reader@example.com")
        create_form_request(email="unrelated@example.com")
        create_user(email="unrelated@example.com")
        request = RequestFactory().get("/admin/")
        for model, expected in [(FormRequest, record), (CustomUser, user)]:
            model_admin = admin.site._registry[model]
            for query in ["mixed.reader@EXAMPLE.COM", "MIXED.READER", "reader@example"]:
                with self.subTest(model=model.__name__, query=query):
                    found, _ = model_admin.get_search_results(request, model.objects.all(), query)
                    self.assertEqual(list(found), [expected])

    def test_recent_actions_are_own_but_record_history_includes_other_staff(self):
        first = create_user(email="first.staff@example.com", is_staff=True)
        second = create_user(email="second.staff@example.com", is_staff=True)
        record = create_form_request()
        permission = Permission.objects.get(content_type__app_label="form", codename="view_formrequest")
        second.user_permissions.add(permission)
        for actor, marker in [(first, "other-staff-change"), (second, "own-staff-change")]:
            LogEntry.objects.log_actions(actor.pk, [record], CHANGE, marker)
        other_record = create_form_request()
        LogEntry.objects.log_actions(first.pk, [other_record], CHANGE, "other-record")
        # Больше десяти своих действий: главная ограничивает ленту, история объекта — нет.
        own_records = [create_form_request() for _ in range(11)]
        for index, own_record in enumerate(own_records):
            LogEntry.objects.log_actions(second.pk, [own_record], CHANGE, f"own-{index}")
        self.client.force_login(second)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        recent = re.search(r'<ul class="actionlist">(.*?)</ul>', response.content.decode(), re.S).group(1)
        self.assertEqual(recent.count("<li "), 10)
        self.assertNotIn(reverse("admin:form_formrequest_change", args=[other_record.pk]), recent)
        self.assertNotIn(reverse("admin:form_formrequest_change", args=[own_records[0].pk]), recent)
        for own_record in own_records[1:]:
            self.assertIn(reverse("admin:form_formrequest_change", args=[own_record.pk]), recent)
        history_url = reverse("admin:form_formrequest_history", args=[record.pk])
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "other-staff-change")
        self.assertContains(response, "own-staff-change")
        second.user_permissions.clear()
        self.assertEqual(self.client.get(history_url).status_code, 403)

    def test_admin_deletion_keeps_user_email_in_log_and_unlinks_request(self):
        staff = create_user(email="staff@example.com", is_staff=True, is_superuser=True)
        target = create_user(email="delete.me@example.com")
        target_id = target.pk
        session = UserSession.objects.create(user=target)
        record = create_form_request(user=target, email=target.email)
        self.client.force_login(staff)
        response = self.client.post(reverse("admin:user_customuser_delete", args=[target.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(pk=target_id).exists())
        self.assertFalse(UserSession.objects.filter(pk=session.pk).exists())
        record.refresh_from_db()
        self.assertIsNone(record.user_id)
        self.assertEqual(record.email, "delete.me@example.com")
        entry = LogEntry.objects.get(action_flag=DELETION, object_id=str(target_id))
        self.assertEqual(entry.object_repr, "delete.me@example.com")
        self.assertEqual(entry.user_id, staff.pk)
