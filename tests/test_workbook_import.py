from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.core import signing
from django.core.cache import cache
from ipam.models import IPAddress, IPRange
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

    def test_confirmation_displays_native_field_errors_without_server_error(self):
        from netbox_access_relations.views import ApplicationSystemImportView

        view = ApplicationSystemImportView()
        upload_id = "native-field-error-test"
        cache_key = view._cache_key(upload_id)
        cache.set(cache_key, {"user_id": self.user.pk, "kind": view.kind, "content": b"workbook"})
        token = signing.dumps({"kind": view.kind, "upload_id": upload_id})
        request = RequestFactory().post("/", {"confirm": "1", "token": token})
        request.user = self.user
        error = ValidationError({"address": ["Address conflicts with an existing object."]})
        with patch("netbox_access_relations.views.apply_workbook", side_effect=error), patch.object(view, "_render") as render:
            view._confirm(request)

        self.assertEqual(render.call_args.kwargs["status"], 409)
        form = render.call_args.args[1]
        self.assertEqual(list(form.non_field_errors()), error.messages)
        self.assertIsNone(cache.get(cache_key))

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

    def test_preflight_rejects_a_workbook_with_excessive_uncompressed_content(self):
        content = BytesIO()
        with ZipFile(content, "w", ZIP_DEFLATED) as archive:
            archive.writestr("xl/sharedStrings.xml", b"x" * (51 * 1024 * 1024))

        plan = preview_workbook(content.getvalue(), "systems", self.user)

        self.assertFalse(plan.valid)
        self.assertEqual(plan.errors[0].field, "file")
        self.assertIn("50 MB", plan.errors[0].reason)

    def test_missing_or_inconsistent_masks_are_preflight_errors(self):
        for native_type, start, end in (
            ("ip_address", "198.51.100.10", ""),
            ("ip_address", "198.51.100.10/0", ""),
            ("ip_range", "198.51.100.10", "198.51.100.20/24"),
            ("ip_range", "198.51.100.10/24", "198.51.100.20"),
            ("ip_range", "198.51.100.10/24", "198.51.100.20/25"),
            ("ip_range", "198.51.100.10/24", "2001:db8::20/24"),
        ):
            with self.subTest(native_type=native_type, start=start, end=end):
                content = self.system_workbook(systems=[("Masked", "active", "", "")], addresses=[
                    ("Masked", native_type, start, end, "", "active", ""),
                ])
                plan = preview_workbook(content, "systems", self.user)
                self.assertFalse(plan.valid)
                self.assertEqual(plan.errors[0].sheet, "系统地址")
                self.assertEqual(plan.errors[0].row, 2)

    def test_range_import_preserves_masks_and_matches_existing_range(self):
        for start, end in (("198.51.100.10/24", "198.51.100.20/24"), ("2001:db8::10/64", "2001:db8::20/64")):
            with self.subTest(start=start):
                name = f"Masked {start}"
                content = self.system_workbook(systems=[(name, "active", "", "")], addresses=[
                    (name, "ip_range", start, end, "", "active", ""),
                ])
                self.assertTrue(preview_workbook(content, "systems", self.user).valid)
                apply_workbook(content, "systems", self.user)
                native = SystemAddress.objects.get(system__name=name).ip_range
                self.assertEqual(str(native.start_address), start)
                self.assertEqual(str(native.end_address), end)
                plan = preview_workbook(content, "systems", self.user)
                self.assertTrue(plan.valid)
                self.assertTrue(all(row.action == "skip" for row in plan.rows))

    def test_native_populated_range_error_is_reported_during_preflight(self):
        native = IPRange(start_address="198.51.100.10/24", end_address="198.51.100.20/24", mark_populated=True)
        native.full_clean(exclude=["size"])
        native.save()
        content = self.system_workbook(systems=[("Populated", "active", "", "")], addresses=[
            ("Populated", "ip_address", "198.51.100.15/24", "", "", "active", ""),
        ])
        self.assertFalse(preview_workbook(content, "systems", self.user).valid)
