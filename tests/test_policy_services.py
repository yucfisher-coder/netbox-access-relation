from django.core.exceptions import ValidationError
from django.test import TestCase

from netbox_access_relations.models import (
    AccessPolicy,
    ApplicationSystem,
    PolicyService,
    TransportProtocolChoices,
)
from netbox_access_relations.services.policy_uniqueness import (
    find_duplicate_policies,
    service_set,
)


class PolicyServiceTests(TestCase):
    """Regression coverage for the protocol-agnostic ANY model introduced in 1.3.0."""

    def setUp(self):
        self.source = ApplicationSystem.objects.create(name="Source")
        self.target = ApplicationSystem.objects.create(name="Target")

    def create_policy(self, name):
        return AccessPolicy.objects.create(
            name=name,
            source_system=self.source,
            target_system=self.target,
        )

    def test_any_is_canonicalized_and_matches_every_protocol_and_port(self):
        policy = self.create_policy("Any policy")
        service = PolicyService(policy=policy, protocol=TransportProtocolChoices.UDP, is_any=True)

        service.full_clean()
        service.save()

        self.assertEqual(service.protocol, TransportProtocolChoices.TCP)
        self.assertEqual(service.protocol_display, "TCP/UDP")
        self.assertEqual(service.port_display, "ANY")
        self.assertTrue(service.overlaps(PolicyService(protocol="tcp", port_start=443, port_end=443)))
        self.assertTrue(service.overlaps(PolicyService(protocol="udp", port_start=53, port_end=53)))

    def test_any_rejects_port_values(self):
        service = PolicyService(
            policy=self.create_policy("Invalid any policy"),
            protocol=TransportProtocolChoices.TCP,
            is_any=True,
            port_start=443,
            port_end=443,
        )

        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_non_any_services_only_overlap_with_same_protocol_and_intersecting_ranges(self):
        tcp_https = PolicyService(protocol="tcp", port_start=443, port_end=443)
        tcp_range = PolicyService(protocol="tcp", port_start=400, port_end=500)
        udp_https = PolicyService(protocol="udp", port_start=443, port_end=443)

        self.assertTrue(tcp_https.overlaps(tcp_range))
        self.assertFalse(tcp_https.overlaps(udp_https))

    def test_any_has_one_protocol_agnostic_identity(self):
        keys = service_set([
            {"protocol": "tcp", "is_any": True, "port_start": None, "port_end": None},
            {"protocol": "udp", "is_any": True, "port_start": None, "port_end": None},
        ])

        self.assertEqual(keys, frozenset({(None, True, None, None)}))

    def test_duplicate_lookup_requires_the_exact_service_set(self):
        existing = self.create_policy("Existing HTTPS")
        PolicyService.objects.create(
            policy=existing,
            protocol=TransportProtocolChoices.TCP,
            port_start=443,
            port_end=443,
        )

        same = frozenset({("tcp", False, 443, 443)})
        additional_service = frozenset({("tcp", False, 443, 443), ("udp", False, 53, 53)})

        self.assertEqual(
            find_duplicate_policies(self.source.pk, self.target.pk, same),
            [existing],
        )
        self.assertEqual(
            find_duplicate_policies(self.source.pk, self.target.pk, additional_service),
            [],
        )
