"""На главной админки чужое новое действие не вытесняет своё из личной десятки."""
import re
from datetime import timedelta

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from form.tests.create import create_form_request
from user.tests.create import create_user


class RecentActionsTest(TestCase):
    def test_newest_other_staff_action_does_not_displace_own_action(self):
        owner = create_user(email="owner.staff@example.com", is_staff=True)
        other = create_user(email="other.staff@example.com", is_staff=True)
        permission = Permission.objects.get(content_type__app_label="form", codename="view_formrequest")
        owner.user_permissions.add(permission)
        own_records = [create_form_request(name=f"B{index}") for index in range(11)]
        other_record = create_form_request(name="A")
        started = timezone.now() - timedelta(minutes=1)
        for index, record in enumerate(own_records + [other_record]):
            actor = owner if index < len(own_records) else other
            entry = LogEntry.objects.log_actions(actor.pk, [record], CHANGE, single_object=True)
            # Строго разные времена: чужое действие новее всей своей одиннадцатки.
            LogEntry.objects.filter(pk=entry.pk).update(
                action_time=started + timedelta(seconds=index)
            )

        self.client.force_login(owner)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        module = re.search(
            r'<div\b[^>]*\bid="recent-actions-module"[^>]*>(.*?)</div>', response.content.decode(), re.S
        )
        self.assertIsNotNone(module, "На главной нет блока недавних действий")
        actionlist = re.search(r'<ul class="actionlist">(.*?)</ul>', module.group(1), re.S)
        self.assertIsNotNone(actionlist, "В блоке недавних действий нет actionlist")
        recent = actionlist.group(1)
        links = re.findall(r'<a href="([^"]+)"', recent)
        own_urls = [reverse("admin:form_formrequest_change", args=[record.pk]) for record in own_records]
        other_url = reverse("admin:form_formrequest_change", args=[other_record.pk])
        self.assertNotIn(other_url, links, "В личную десятку попала чужая заявка")
        self.assertNotIn(own_urls[0], links, "Самая старая своя заявка должна выйти из десятки")
        self.assertEqual(len(re.findall(r"<li\b", recent)), 10)
        self.assertEqual(len(links), 10)
        self.assertCountEqual(links, own_urls[1:])
