"""Query filters for access-relations objects."""

import django_filters
import netaddr
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from netbox.filtersets import NetBoxModelFilterSet, PrimaryModelFilterSet
from utilities.filters import MultiValueNumberFilter

from .models import AccessPolicy, ActiveStatusChoices, ApplicationSystem, PolicyService, SystemAddress, SystemAlias, TransportProtocolChoices
from .services.zones import system_zone_buckets


def _address_interval(link):
    if link.prefix_id:
        network = netaddr.IPNetwork(link.prefix.prefix)
        return network.first, network.last, network.version
    if link.ip_address_id:
        address = netaddr.IPNetwork(link.ip_address.address).ip
        return int(address), int(address), address.version
    start = netaddr.IPNetwork(link.ip_range.start_address).ip
    end = netaddr.IPNetwork(link.ip_range.end_address).ip
    return int(start), int(end), start.version


def _system_matches_ip(system, value):
    try:
        query = netaddr.IPNetwork(value)
    except (netaddr.AddrFormatError, ValueError):
        return False
    query_start, query_end = query.first, query.last
    return any(
        version == query.version and start <= query_end and end >= query_start
        for start, end, version in (_address_interval(link) for link in system.addresses.all())
    )


class ApplicationSystemFilterSet(PrimaryModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=ActiveStatusChoices)
    is_co_located = django_filters.BooleanFilter()

    class Meta:
        model = ApplicationSystem
        fields = ("id", "name", "status", "is_co_located", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(aliases__name__icontains=value)
            | Q(description__icontains=value)
            | Q(comments__icontains=value)
        ).distinct()


class SystemAliasFilterSet(NetBoxModelFilterSet):
    system_id = MultiValueNumberFilter(field_name="system_id")

    class Meta:
        model = SystemAlias
        fields = ("id", "name", "system_id")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(system__name__icontains=value))


class SystemAddressFilterSet(NetBoxModelFilterSet):
    system_id = MultiValueNumberFilter(field_name="system_id")

    class Meta:
        model = SystemAddress
        fields = ("id", "system_id", "prefix_id", "ip_address_id", "ip_range_id")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(system__name__icontains=value)


class AccessPolicyFilterSet(PrimaryModelFilterSet):
    source_system_id = MultiValueNumberFilter(field_name="source_system_id")
    target_system_id = MultiValueNumberFilter(field_name="target_system_id")
    system_id = MultiValueNumberFilter(method="filter_system")
    protocol = django_filters.MultipleChoiceFilter(method="filter_protocol", choices=TransportProtocolChoices)
    port = django_filters.NumberFilter(method="filter_port")
    port_start = django_filters.NumberFilter(method="filter_port_start")
    port_end = django_filters.NumberFilter(method="filter_port_end")
    effective_status = django_filters.MultipleChoiceFilter(method="filter_effective_status")
    source_zone = django_filters.CharFilter(method="filter_zone_pair")
    target_zone = django_filters.CharFilter(method="filter_zone_pair")
    zone = django_filters.CharFilter(method="filter_zone_pair")
    ip = django_filters.CharFilter(method="filter_ip")

    class Meta:
        model = AccessPolicy
        fields = ("id", "name", "category", "source_system_id", "target_system_id")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(category__icontains=value)
            | Q(source_system__name__icontains=value) | Q(target_system__name__icontains=value)
            | Q(description__icontains=value) | Q(comments__icontains=value)
        ).distinct()

    def filter_system(self, queryset, name, values):
        return queryset.filter(Q(source_system_id__in=values) | Q(target_system_id__in=values))

    def filter_protocol(self, queryset, name, values):
        query = Q(services__protocol__in=values)
        port = self.form.cleaned_data.get("port")
        if port is not None:
            query &= Q(services__is_any=True) | Q(services__port_start__lte=port, services__port_end__gte=port)
        else:
            start = self.form.cleaned_data.get("port_start")
            end = self.form.cleaned_data.get("port_end")
            if start is not None and end is not None:
                query &= Q(services__is_any=True) | Q(services__port_start__lte=end, services__port_end__gte=start)
        return queryset.filter(query).distinct()

    def filter_port(self, queryset, name, value):
        if self.form.cleaned_data.get("protocol"):
            return queryset
        return queryset.filter(
            Q(services__is_any=True)
            | Q(services__port_start__lte=value, services__port_end__gte=value)
        ).distinct()

    def filter_port_start(self, queryset, name, value):
        return queryset

    def filter_port_end(self, queryset, name, value):
        if self.form.cleaned_data.get("protocol"):
            return queryset
        start = self.form.cleaned_data.get("port_start")
        if start is None:
            return queryset
        return queryset.filter(
            Q(services__is_any=True)
            | Q(services__port_start__lte=value, services__port_end__gte=start)
        ).distinct()

    def filter_effective_status(self, queryset, name, values):
        now = timezone.now()
        query = Q(pk__in=[])
        if "upcoming" in values:
            query |= Q(valid_from__gt=now)
        if "active" in values:
            query |= (Q(valid_from__isnull=True) | Q(valid_from__lte=now)) & (Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        if "expired" in values:
            query |= Q(valid_until__lte=now)
        return queryset.filter(query)

    def filter_zone_pair(self, queryset, name, value):
        source = self.form.cleaned_data.get("source_zone")
        target = self.form.cleaned_data.get("target_zone")
        either = self.form.cleaned_data.get("zone")
        def key(raw):
            if not raw or raw.startswith(("zone:", "state:")):
                return raw
            return f"zone:{raw}"
        source, target, either = key(source), key(target), key(either)
        queryset = queryset.select_related("source_system", "target_system").prefetch_related(
            "source_system__addresses__prefix", "source_system__addresses__ip_address",
            "source_system__addresses__ip_range", "target_system__addresses__prefix",
            "target_system__addresses__ip_address", "target_system__addresses__ip_range",
        )
        matching = []
        for policy in queryset:
            source_keys = {bucket.key for bucket in system_zone_buckets(policy.source_system)}
            target_keys = {bucket.key for bucket in system_zone_buckets(policy.target_system)}
            if source and source not in source_keys:
                continue
            if target and target not in target_keys:
                continue
            if either and either not in source_keys | target_keys:
                continue
            matching.append(policy.pk)
        return queryset.filter(pk__in=matching)

    def filter_ip(self, queryset, name, value):
        queryset = queryset.select_related("source_system", "target_system").prefetch_related(
            "source_system__addresses__prefix", "source_system__addresses__ip_address",
            "source_system__addresses__ip_range", "target_system__addresses__prefix",
            "target_system__addresses__ip_address", "target_system__addresses__ip_range",
        )
        matching = [
            policy.pk for policy in queryset
            if _system_matches_ip(policy.source_system, value) or _system_matches_ip(policy.target_system, value)
        ]
        return queryset.filter(pk__in=matching)


class PolicyServiceFilterSet(NetBoxModelFilterSet):
    policy_id = MultiValueNumberFilter(field_name="policy_id")
    source_system_id = MultiValueNumberFilter(field_name="policy__source_system_id")
    target_system_id = MultiValueNumberFilter(field_name="policy__target_system_id")
    system_id = MultiValueNumberFilter(method="filter_system")
    protocol = django_filters.MultipleChoiceFilter(choices=TransportProtocolChoices)
    port = django_filters.NumberFilter(method="filter_port")
    port_start = django_filters.NumberFilter(method="filter_port_start")
    port_end = django_filters.NumberFilter(method="filter_port_end")
    effective_status = django_filters.MultipleChoiceFilter(method="filter_effective_status")

    class Meta:
        model = PolicyService
        fields = ("id", "policy_id", "protocol", "is_any")

    def filter_port(self, queryset, name, value):
        return queryset.filter(Q(is_any=True) | Q(port_start__lte=value, port_end__gte=value))

    def filter_port_start(self, queryset, name, value):
        return queryset

    def filter_port_end(self, queryset, name, value):
        start = self.form.cleaned_data.get("port_start")
        if start is None:
            return queryset
        return queryset.filter(Q(is_any=True) | Q(port_start__lte=value, port_end__gte=start))

    def filter_system(self, queryset, name, values):
        return queryset.filter(
            Q(policy__source_system_id__in=values) | Q(policy__target_system_id__in=values)
        )

    def filter_effective_status(self, queryset, name, values):
        now = timezone.now()
        query = Q(pk__in=[])
        if "upcoming" in values:
            query |= Q(policy__valid_from__gt=now)
        if "active" in values:
            query |= (
                (Q(policy__valid_from__isnull=True) | Q(policy__valid_from__lte=now))
                & (Q(policy__valid_until__isnull=True) | Q(policy__valid_until__gt=now))
            )
        if "expired" in values:
            query |= Q(policy__valid_until__lte=now)
        return queryset.filter(query)

    def search(self, queryset, name, value):
        return queryset.filter(Q(policy__name__icontains=value) | Q(policy__source_system__name__icontains=value) | Q(policy__target_system__name__icontains=value))
