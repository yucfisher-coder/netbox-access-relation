"""Exercise list selection and write results through the actual NetBox views."""
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from ipam.models import Prefix

from netbox_access_relations.models import ApplicationSystem, AccessPolicy, PolicyService, SystemAddress, SystemAlias


class BulkOperationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="bulk-test", password="test")
        self.client.force_login(self.user)
        self.source = ApplicationSystem.objects.create(name="Source")
        self.target = ApplicationSystem.objects.create(name="Target")

    def url(self, model, action, **kwargs):
        return reverse(f"plugins:netbox_access_relations:{model}_{action}", kwargs=kwargs)

    def policy(self, name):
        policy = AccessPolicy.objects.create(name=name, source_system=self.source, target_system=self.target)
        PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        return policy

    def test_list_selection_and_bulk_actions_are_rendered(self):
        self.policy("Selectable")
        for model, obj in (("applicationsystem", self.source), ("accesspolicy", AccessPolicy.objects.first())):
            response = self.client.get(self.url(model, "list"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'name="pk"')
            self.assertContains(response, self.url(model, "bulk_edit"))
            self.assertContains(response, self.url(model, "bulk_delete"))

    def test_single_system_delete_removes_links_and_aliases_but_preserves_ipam(self):
        native = Prefix.objects.create(prefix="198.18.0.0/24")
        for system in (self.source, self.target):
            SystemAddress.objects.create(system=system, prefix=native)
        SystemAlias.objects.create(system=self.source, name="Source alias")
        source_pk = self.source.pk
        response = self.client.post(self.url("applicationsystem", "delete", pk=source_pk), {"confirm": True}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApplicationSystem.objects.filter(pk=source_pk).exists())
        self.assertFalse(SystemAddress.objects.filter(system_id=source_pk).exists())
        self.assertFalse(SystemAlias.objects.filter(system_id=source_pk).exists())
        self.assertTrue(Prefix.objects.filter(pk=native.pk).exists())
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_co_located)

    def test_bulk_system_delete_only_removes_selected_system(self):
        response = self.client.post(self.url("applicationsystem", "bulk_delete"), {
            "pk": [self.source.pk], "_confirm": "1", "confirm": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ApplicationSystem.objects.filter(pk=self.source.pk).exists())
        self.assertTrue(ApplicationSystem.objects.filter(pk=self.target.pk).exists())

    def test_system_referenced_by_policy_cannot_be_deleted_or_report_success(self):
        self.policy("Protected")
        response = self.client.post(self.url("applicationsystem", "delete", pk=self.source.pk), {"confirm": True})
        self.assertTrue(ApplicationSystem.objects.filter(pk=self.source.pk).exists())
        self.assertFalse(any(message.level_tag == "success" for message in get_messages(response.wsgi_request)))

    def test_bulk_edit_only_updates_selected_systems(self):
        response = self.client.post(self.url("applicationsystem", "bulk_edit"), {
            "pk": [self.source.pk], "_apply": "1", "status": "inactive", "description": "Bulk edit",
        })
        self.assertEqual(response.status_code, 302)
        self.source.refresh_from_db()
        self.target.refresh_from_db()
        self.assertEqual(self.source.status, "inactive")
        self.assertEqual(self.source.description, "Bulk edit")
        self.assertEqual(self.target.status, "active")

    def test_bulk_policy_edit_and_delete_preserve_unselected_policy(self):
        selected = self.policy("Selected")
        kept = self.policy("Kept")
        response = self.client.post(self.url("accesspolicy", "bulk_edit"), {
            "pk": [selected.pk], "_apply": "1", "category": "Updated",
        })
        self.assertEqual(response.status_code, 302)
        selected.refresh_from_db()
        self.assertEqual(selected.category, "Updated")
        response = self.client.post(self.url("accesspolicy", "bulk_delete"), {
            "pk": [selected.pk], "_confirm": "1", "confirm": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccessPolicy.objects.filter(pk=selected.pk).exists())
        self.assertFalse(PolicyService.objects.filter(policy_id=selected.pk).exists())
        self.assertTrue(AccessPolicy.objects.filter(pk=kept.pk).exists())

    def test_users_without_write_permissions_cannot_bulk_edit_or_delete(self):
        user = get_user_model().objects.create_user(username="no-write")
        self.client.force_login(user)
        for model in ("applicationsystem", "accesspolicy"):
            for action in ("bulk_edit", "bulk_delete"):
                response = self.client.post(self.url(model, action), {"pk": [self.source.pk], "_apply": "1", "_confirm": "1", "confirm": True})
                self.assertEqual(response.status_code, 403)
        self.assertTrue(ApplicationSystem.objects.filter(pk=self.source.pk).exists())
