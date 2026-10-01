from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from ipam.models import IPAddress
from openpyxl import load_workbook

from netbox_access_relations.models import ApplicationSystem, SystemAddress, SystemAlias
from netbox_access_relations.services.workbook_import import (
    apply_workbook,
    build_template,
    preview_workbook,
)


class WorkbookImportTests(TestCase):
    """Acceptance-level checks for preflight blocking and all-or-nothing writes."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="workbook-import-test",
            password="not-used-by-tests",
        )

    def system_workbook(self, systems=(), aliases=(), addresses=()):
        workbook = load_workbook(BytesIO(build_template("systems")))
        for values in systems:
            workbook["业务系统"].append(values)
        for values in aliases:
            workbook["系统别名"].append(values)
        for values in addresses:
            workbook["系统地址"].append(values)
        content = BytesIO()
        workbook.save(content)
        return content.getvalue()

    def test_preflight_reports_all_duplicate_system_rows_without_writing(self):
        content = self.system_workbook(systems=[
            ("Billing", "active", "", ""),
            ("billing", "active", "", ""),
        ])

        plan = preview_workbook(content, "systems", self.user)

        self.assertFalse(plan.valid)
        self.assertEqual(len(plan.errors), 1)
        self.assertEqual(plan.errors[0].sheet, "业务系统")
        self.assertEqual(plan.errors[0].row, 3)
        self.assertEqual(plan.errors[0].field, "system_name")
        self.assertEqual(ApplicationSystem.objects.count(), 0)

        with self.assertRaises(ValidationError):
            apply_workbook(content, "systems", self.user)
        self.assertEqual(ApplicationSystem.objects.count(), 0)

    def test_late_address_write_failure_rolls_back_system_alias_and_native_address(self):
        content = self.system_workbook(
            systems=[("Atomic Billing", "active", "", "")],
            aliases=[("Atomic Billing", "ATOMIC-BILLING")],
            addresses=[(
                "Atomic Billing", "ip_address", "198.51.100.10/32", "", "",
                "active", "transaction rollback test",
            )],
        )
        self.assertTrue(preview_workbook(content, "systems", self.user).valid)

        with patch.object(SystemAddress, "save", side_effect=ValidationError("simulated address failure")):
            with self.assertRaises(ValidationError):
                apply_workbook(content, "systems", self.user)

        self.assertEqual(ApplicationSystem.objects.filter(name="Atomic Billing").count(), 0)
        self.assertEqual(SystemAlias.objects.filter(name="ATOMIC-BILLING").count(), 0)
        self.assertEqual(SystemAddress.objects.count(), 0)
        self.assertEqual(IPAddress.objects.filter(address="198.51.100.10/32").count(), 0)
