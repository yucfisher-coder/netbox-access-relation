import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

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

    def test_high_ports_validate_and_persist(self):
        policy = self.create_policy("High ports")
        for protocol, start, end in [("tcp", 32768, 32768), ("udp", 49152, 65535)]:
            with self.subTest(protocol=protocol):
                service = PolicyService(policy=policy, protocol=protocol, port_start=start, port_end=end)
                service.full_clean()
                service.save()
                service.refresh_from_db()
                self.assertEqual((service.port_start, service.port_end), (start, end))

    def test_ports_outside_network_range_are_rejected(self):
        policy = self.create_policy("Invalid ports")
        for start, end in [(0, 1), (65535, 65536), (50000, 40000)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                PolicyService(policy=policy, protocol="tcp", port_start=start, port_end=end).full_clean()

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

    def test_deleting_the_last_service_is_rejected(self):
        policy = self.create_policy("Protected service")
        service = PolicyService.objects.create(
            policy=policy,
            protocol=TransportProtocolChoices.TCP,
            port_start=443,
            port_end=443,
        )

        with self.assertRaises(ValidationError):
            service.delete()

        self.assertTrue(PolicyService.objects.filter(pk=service.pk).exists())


class ServiceQueryOrderingTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(username="service-sort-test"))
        self.url = reverse("plugins:netbox_access_relations:policyservice_list")
        source = ApplicationSystem.objects.create(name="Sort source")
        target = ApplicationSystem.objects.create(name="Sort target")
        self.policy = AccessPolicy.objects.create(name="Sort policy", source_system=source, target_system=target)
        for protocol, start, end in [("tcp", 100, 100), ("tcp", 20, 30), ("udp", 20, 20), ("tcp", 20, 20)]:
            PolicyService.objects.create(policy=self.policy, protocol=protocol, port_start=start, port_end=end)
        PolicyService.objects.create(policy=self.policy, protocol="tcp", is_any=True)

    def expressions(self, response):
        return [(group["protocol"], group["port"]) for group in response.context["groups"]]

    def test_numeric_port_order_and_deterministic_ties_in_both_directions(self):
        expected = [("TCP", "20"), ("UDP", "20"), ("TCP", "20-30"), ("TCP", "100"), ("TCP/UDP", "ANY")]
        for ordering, expressions in [("port", expected), ("-port", expected[::-1])]:
            with self.subTest(ordering=ordering):
                response = self.client.get(self.url, {"sort": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.expressions(response), expressions)
                self.assertEqual(response.context["ordering_form"]["sort"].value(), ordering)

    def test_protocol_order_and_invalid_sort_fallback(self):
        expected = [("TCP", "20"), ("TCP", "20-30"), ("TCP", "100"), ("TCP/UDP", "ANY"), ("UDP", "20")]
        for ordering, expressions in [("protocol", expected), ("-protocol", expected[::-1]), ("invalid", expected)]:
            with self.subTest(ordering=ordering):
                response = self.client.get(self.url, {"sort": ordering})
                self.assertEqual(self.expressions(response), expressions)
                if ordering == "invalid":
                    self.assertEqual(response.context["ordering"], "protocol")
                    self.assertEqual(response.context["query"], "sort=protocol")

    def test_filtered_csv_uses_same_numeric_order_as_page(self):
        params = {"protocol": "tcp", "sort": "-port"}
        response = self.client.get(self.url, params)
        exported = self.client.get(self.url, {**params, "export": "csv"})
        self.assertEqual(exported.status_code, 200)
        rows = list(csv.reader(StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual([tuple(row[:2]) for row in rows[1:]], self.expressions(response))
        self.assertNotIn(("UDP", "20"), self.expressions(response))

    def test_pagination_and_export_links_preserve_filter_and_sort(self):
        for port in range(1000, 1050):
            PolicyService.objects.create(policy=self.policy, protocol="tcp", port_start=port, port_end=port)
        params = {"protocol": "tcp", "sort": "port"}
        first = self.client.get(self.url, params)
        second = self.client.get(self.url, {**params, "page": 2})
        self.assertEqual(first.context["page_obj"].paginator.count, 54)
        self.assertEqual(len(first.context["groups"]), 50)
        self.assertEqual(self.expressions(second), [("TCP", "1047"), ("TCP", "1048"), ("TCP", "1049"), ("TCP/UDP", "ANY")])
        exported = self.client.get(self.url, {**params, "page": 2, "export": "csv"})
        rows = list(csv.reader(StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows) - 1, 54)
        self.assertEqual([tuple(row[:2]) for row in rows[1:]], self.expressions(first) + self.expressions(second))
        self.assertContains(first, 'protocol=tcp&amp;sort=port&amp;page=2')
        self.assertContains(second, 'protocol=tcp&amp;sort=port&amp;export=csv')
        self.assertEqual(self.expressions(second), self.expressions(self.client.get(self.url, {**params, "page": 2})))

    def test_query_pages_follow_active_language_including_exports(self):
        from django.utils.translation import override
        matrix_url = reverse("plugins:netbox_access_relations:zone_matrix")
        for language, service_title, matrix_title, sort_label, state in [
            ("en", "Service query", "Zone matrix", "Port ascending", "Unmatched"),
            ("zh-hans", "服务查询", "区域矩阵", "端口升序", "未匹配"),
        ]:
            with self.subTest(language=language), override(language):
                # Bypass locale middleware so the active language is explicit.
                from django.test import RequestFactory
                from netbox_access_relations.views import PolicyServiceListView, ZoneMatrixView
                from django.contrib.auth import get_user_model
                user = get_user_model().objects.get(username="service-sort-test")
                for view, url, title in [(PolicyServiceListView, self.url, service_title), (ZoneMatrixView, matrix_url, matrix_title)]:
                    request = RequestFactory().get(url)
                    request.user = user
                    response = view.as_view()(request)
                    self.assertContains(response, title)
                    if view is PolicyServiceListView:
                        self.assertContains(response, sort_label)
                    else:
                        self.assertContains(response, state)
                    exported = RequestFactory().get(url, {"export": "csv"})
                    exported.user = user
                    content = view.as_view()(exported).content.decode("utf-8-sig")
                    self.assertIn("Protocol" if language == "en" and view is PolicyServiceListView else
                                  "Source zone" if language == "en" else
                                  "协议" if view is PolicyServiceListView else "源区域", content)
                    if language == "en":
                        import re
                        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", content))
                        self.assertIsNone(re.search(r"[\u4e00-\u9fff]", response.content.decode()))
