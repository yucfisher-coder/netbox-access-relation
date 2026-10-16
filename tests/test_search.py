from django.test import TestCase
from ipam.models import IPAddress
from netbox.search import get_indexer
from netbox_access_relations.filtersets import ApplicationSystemFilterSet, AccessPolicyFilterSet
from netbox_access_relations.models import ApplicationSystem, AccessPolicy, SystemAlias, SystemAddress, PolicyService


class QuickSearchTests(TestCase):
    def setUp(self):
        self.source = ApplicationSystem.objects.create(name="Payments", custom_field_data={"owner": "Finance"})
        self.target = ApplicationSystem.objects.create(name="Database")
        SystemAlias.objects.create(system=self.source, name="billing-alias")
        address = IPAddress.objects.create(address="192.0.2.19/24", dns_name="billing.example.test")
        SystemAddress.objects.create(system=self.source, ip_address=address)
        self.policy = AccessPolicy.objects.create(name="Payment connection", category="Database access", description="excluded-description", source_system=self.source, target_system=self.target)
        PolicyService.objects.create(policy=self.policy, protocol="tcp", port_start=8000, port_end=8100)

    def test_related_fields_and_whitespace(self):
        for term in (" billing-alias ", "192.0.2.19"):
            with self.subTest(term=term):
                self.assertIn(self.source, ApplicationSystemFilterSet({"q": term}).qs)
                self.assertIn(self.policy, AccessPolicyFilterSet({"q": term}).qs)
        for term in ("8020", "TCP", "Finance", "billing.example"):
            self.assertFalse(AccessPolicyFilterSet({"q": term}).qs.exists())
            self.assertFalse(ApplicationSystemFilterSet({"q": term}).qs.exists())
        self.assertEqual(AccessPolicyFilterSet({"q": "Database access"}).qs.get(), self.policy)
        self.assertEqual(AccessPolicyFilterSet({"q": "Payment connection"}).qs.get(), self.policy)
        self.assertFalse(AccessPolicyFilterSet({"q": "excluded-description"}).qs.exists())
        self.assertFalse(AccessPolicyFilterSet({"q": "no-such-value"}).qs.exists())

    def test_global_indexes_include_related_fields(self):
        for obj in (self.source, self.policy):
            values = " ".join(str(v.value) for v in get_indexer(type(obj)).to_cache(obj))
            for term in ("billing-alias", "192.0.2.19"):
                self.assertIn(term, values)
            for term in ("Finance", "billing.example", "8000", "8100"):
                self.assertNotIn(term, values)

    def test_requested_scale(self):
        """Exercise search at 3000 systems / 2000 policies with linked data."""
        from time import perf_counter
        from netbox.search.backends import search_backend
        systems = ApplicationSystem.objects.bulk_create([
            ApplicationSystem(name=f"Scale system {i:04d}") for i in range(3000)
        ])
        SystemAlias.objects.bulk_create([
            SystemAlias(system=system, name=f"Scale alias {i:04d}") for i, system in enumerate(systems)
        ])
        addresses = IPAddress.objects.bulk_create([
            IPAddress(address=f"10.20.{i // 256}.{i % 256}/32") for i in range(3000)
        ])
        SystemAddress.objects.bulk_create([
            SystemAddress(system=system, ip_address=address) for system, address in zip(systems, addresses)
        ])
        policies = AccessPolicy.objects.bulk_create([
            AccessPolicy(name=f"Scale policy {i:04d}", source_system=systems[i], target_system=systems[i + 1])
            for i in range(2000)
        ])
        PolicyService.objects.bulk_create([
            PolicyService(policy=policy, protocol="tcp", port_start=443, port_end=443) for policy in policies
        ])
        started = perf_counter()
        entries = search_backend.cache(systems, remove_existing=False)
        entries += search_backend.cache(policies, remove_existing=False)
        print(f"\nSCALE index: {entries} entries, {perf_counter() - started:.3f}s", flush=True)
        for label, operation in (
            ("systems alias", lambda: ApplicationSystemFilterSet({"q": "Scale alias 1500"}).qs.count()),
            ("policies alias", lambda: AccessPolicyFilterSet({"q": "Scale alias 1500"}).qs.count()),
            ("policies IP", lambda: AccessPolicyFilterSet({"q": "10.20.5.220"}).qs.count()),
            ("global alias", lambda: len(search_backend.search("Scale alias 1500"))),
        ):
            started = perf_counter()
            count = operation()
            print(f"SCALE {label}: {count} results, {(perf_counter() - started) * 1000:.2f}ms", flush=True)
            self.assertGreater(count, 0)
