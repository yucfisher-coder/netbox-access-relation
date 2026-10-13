"""Regressions for metadata-only edits with untouched inline rows."""
import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from ipam.choices import IPAddressStatusChoices, IPRangeStatusChoices, PrefixStatusChoices
from ipam.models import Prefix

from netbox_access_relations.forms import AccessPolicyForm, ApplicationSystemWithAddressesForm, SystemAddressForm
from netbox_access_relations.models import AccessPolicy, ApplicationSystem, PolicyService, SystemAddress


def rendered_data(form):
    """Submit initial values as a browser does, including NetBox's render time."""
    data = {}
    for field in form:
        value = field.value()
        if value is not None:
            data[field.html_name] = field.field.prepare_value(value)
    return data


def formset_data(formset):
    data = rendered_data(formset.management_form)
    for form in formset:
        data.update(rendered_data(form))
    return data


class EditFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="edit-tester", password="test")
        self.source = ApplicationSystem.objects.create(name="Source")
        self.target = ApplicationSystem.objects.create(name="Target")

    def test_category_only_edit_ignores_untouched_extra_service(self):
        policy = AccessPolicy.objects.create(name="Policy", source_system=self.source, target_system=self.target)
        service = PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset), "category": "New category"}
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertTrue(bound.is_valid(), (bound.errors, bound.service_formset.errors))
        bound.save()
        policy.refresh_from_db()
        self.assertEqual(policy.category, "New category")
        self.assertEqual(list(policy.services.values_list("pk", flat=True)), [service.pk])

    def test_name_only_edit_preserves_address_and_ignores_extra_row(self):
        prefix = Prefix.objects.create(prefix="10.90.0.0/24", status="active")
        address = SystemAddress.objects.create(system=self.source, prefix=prefix)
        native_updated = prefix.last_updated
        initial = ApplicationSystemWithAddressesForm(instance=self.source, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.address_formset), "name": "Renamed"}
        bound = ApplicationSystemWithAddressesForm(data=data, instance=self.source, user=self.user)
        self.assertTrue(bound.is_valid(), (bound.errors, bound.address_formset.errors))
        self.assertEqual(bound.address_formset.forms[0].changed_data, [])
        bound.save()
        self.source.refresh_from_db()
        prefix.refresh_from_db()
        self.assertEqual(self.source.name, "Renamed")
        self.assertEqual(list(self.source.addresses.values_list("pk", flat=True)), [address.pk])
        self.assertEqual(str(prefix.prefix), "10.90.0.0/24")
        self.assertEqual(prefix.last_updated, native_updated)

    def test_native_status_choices_match_each_native_type(self):
        for native_type, choices in (("prefix", PrefixStatusChoices), ("ip_address", IPAddressStatusChoices), ("ip_range", IPRangeStatusChoices)):
            with self.subTest(native_type=native_type):
                form = SystemAddressForm(data={"native_type": native_type}, user=self.user)
                self.assertEqual(list(form.fields["native_status"].choices), list(choices))

    def test_range_rejects_container_status(self):
        form = SystemAddressForm(data={
            "system": self.source.pk, "native_operation": "create", "native_type": "ip_range",
            "native_range_start": "10.91.0.1/24", "native_range_end": "10.91.0.10/24",
            "native_status": "container",
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("native_status", form.errors)

    def test_stale_inline_timestamp_is_still_validated(self):
        policy = AccessPolicy.objects.create(name="Policy", source_system=self.source, target_system=self.target)
        PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset)}
        data["services-0-_init_time"] = str(time.time() - 3600)
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertFalse(bound.is_valid())
        self.assertTrue(bound.service_formset.forms[0].non_field_errors())

    def test_remove_existing_service_preserves_other_service(self):
        policy = AccessPolicy.objects.create(name="Remove", source_system=self.source, target_system=self.target)
        removed = PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        kept = PolicyService.objects.create(policy=policy, protocol="udp", port_start=53, port_end=53)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset), "services-0-DELETE": "on"}
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertTrue(bound.is_valid(), (bound.errors, bound.service_formset.errors))
        bound.save()
        self.assertFalse(PolicyService.objects.filter(pk=removed.pk).exists())
        self.assertEqual(list(policy.services.values_list("pk", flat=True)), [kept.pk])

    def test_replace_last_service_in_one_save(self):
        policy = AccessPolicy.objects.create(name="Replace", source_system=self.source, target_system=self.target)
        removed = PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset),
                "services-0-DELETE": "on", "services-1-protocol": "udp",
                "services-1-port_start": "53", "services-1-port_end": "53"}
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertTrue(bound.is_valid(), (bound.errors, bound.service_formset.errors))
        bound.save()
        self.assertFalse(PolicyService.objects.filter(pk=removed.pk).exists())
        self.assertEqual(list(policy.services.values_list("protocol", "port_start", "port_end")), [("udp", 53, 53)])

    def test_remove_all_services_is_rejected(self):
        policy = AccessPolicy.objects.create(name="Keep one", source_system=self.source, target_system=self.target)
        service = PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset), "services-0-DELETE": "on"}
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertFalse(bound.is_valid())
        self.assertTrue(bound.service_formset.non_form_errors())
        self.assertTrue(PolicyService.objects.filter(pk=service.pk).exists())

    def test_edit_pages_follow_selected_language(self):
        from django.urls import reverse
        from django.utils.translation import override
        policy = AccessPolicy.objects.create(name="Language", source_system=self.source, target_system=self.target)
        PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        self.client.force_login(self.user)
        for language, expected, absent in (("en", "Remove service", "移除服务项"), ("zh-hans", "移除服务项", "Remove service")):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("plugins:netbox_access_relations:accesspolicy_edit", args=[policy.pk]), HTTP_ACCEPT_LANGUAGE=language)
                self.assertContains(response, expected)
                self.assertNotContains(response, absent)
                self.assertContains(response, "全协议 ANY" if language == "zh-hans" else "All protocols ANY")
                response = self.client.get(reverse("plugins:netbox_access_relations:applicationsystem_edit", args=[self.source.pk]), HTTP_ACCEPT_LANGUAGE=language)
                self.assertContains(response, "影响提示：" if language == "zh-hans" else "Impact:")
                self.assertNotContains(response, "Impact:" if language == "zh-hans" else "影响提示：")

    def test_any_cannot_be_added_beside_an_existing_port(self):
        policy = AccessPolicy.objects.create(name="Exclusive", source_system=self.source, target_system=self.target)
        PolicyService.objects.create(policy=policy, protocol="tcp", port_start=443, port_end=443)
        initial = AccessPolicyForm(instance=policy, user=self.user)
        data = {**rendered_data(initial), **formset_data(initial.service_formset), "services-1-is_any": "on"}
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertFalse(bound.is_valid())
        self.assertIn("ANY cannot coexist", str(bound.service_formset.non_form_errors()))
        # Deleting the old port makes the final set valid, despite its presence in the DB.
        data["services-0-DELETE"] = "on"
        bound = AccessPolicyForm(data=data, instance=policy, user=self.user)
        self.assertTrue(bound.is_valid(), (bound.errors, bound.service_formset.errors))
        bound.save()
        self.assertEqual(list(policy.services.values_list("is_any", flat=True)), [True])

    def test_native_service_validation_rejects_both_mixed_directions(self):
        for existing_any in (False, True):
            policy = AccessPolicy.objects.create(name=f"Exclusive {existing_any}", source_system=self.source, target_system=self.target)
            PolicyService.objects.create(policy=policy, protocol="tcp", is_any=existing_any,
                                         port_start=None if existing_any else 443, port_end=None if existing_any else 443)
            new = PolicyService(policy=policy, protocol="udp", is_any=not existing_any,
                                port_start=53 if existing_any else None, port_end=53 if existing_any else None)
            from django.core.exceptions import ValidationError
            with self.assertRaisesMessage(ValidationError, "ANY cannot coexist"):
                new.full_clean()

    def test_api_creation_rejects_mixed_any_services(self):
        from netbox_access_relations.api.serializers import AccessPolicySerializer
        serializer = AccessPolicySerializer(data={
            "name": "API mixed", "source_system": self.source.pk, "target_system": self.target.pk,
            "services": [{"is_any": True}, {"protocol": "tcp", "port_start": 443, "port_end": 443}],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("ANY cannot coexist", str(serializer.errors))

    def test_workbook_preview_rejects_mixed_any_services(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from netbox_access_relations.services.workbook_import import build_template, preview_workbook
        workbook = load_workbook(BytesIO(build_template("policies")))
        workbook["访问关系"].append(("Mixed import", "", self.source.name, self.target.name, "", "", "", ""))
        workbook["服务项"].append(("Mixed import", "", "ANY"))
        workbook["服务项"].append(("Mixed import", "tcp", "443"))
        content = BytesIO()
        workbook.save(content)
        plan = preview_workbook(content.getvalue(), "policies", self.user)
        self.assertFalse(plan.valid)
        self.assertTrue(any("ANY cannot coexist" in str(error) for error in plan.errors), plan.errors)
