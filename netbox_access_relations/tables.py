"""NetBox-native tables for access-relations objects."""

import django_tables2 as tables
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, PrimaryModelTable, columns

from .models import AccessPolicy, ApplicationSystem, PolicyService, SystemAddress, SystemAlias


class ApplicationSystemTable(PrimaryModelTable):
    name = tables.Column(
        linkify=True,
        verbose_name=_("Name"),
        attrs={"th": {"style": "width: 15rem"}},
    )
    status = columns.ChoiceFieldColumn(verbose_name=_("Status"))
    is_co_located = columns.BooleanColumn(verbose_name=_("Co-located"))
    ip_information = tables.TemplateColumn(
        template_name="netbox_access_relations/inc/application_system_ip_addresses.html",
        orderable=False,
        verbose_name=_("IP information"),
    )
    description = tables.Column(attrs={"th": {"style": "min-width: 15rem"}})
    tags = columns.TagColumn(url_name="plugins:netbox_access_relations:applicationsystem_list")

    class Meta(PrimaryModelTable.Meta):
        model = ApplicationSystem
        fields = (
            "pk",
            "id",
            "name",
            "status",
            "ip_information",
            "is_co_located",
            "description",
            "owner_group",
            "owner",
            "comments",
            "tags",
            "created",
            "last_updated",
            "actions",
        )
        default_columns = ("pk", "name", "status", "ip_information", "is_co_located", "description")

    def value_ip_information(self, record):
        return "\n".join(
            f"{address.address_object}（VRF：{address.vrf}）" if address.vrf else str(address.address_object)
            for address in record.addresses.all()
        ) or "—"


class SystemAliasTable(NetBoxTable):
    name = tables.Column(linkify=True, verbose_name=_("Alias"))
    system = tables.Column(linkify=True, verbose_name=_("Application system"))
    tags = columns.TagColumn(url_name="plugins:netbox_access_relations:systemalias_list")

    class Meta(NetBoxTable.Meta):
        model = SystemAlias
        fields = ("pk", "id", "name", "system", "tags", "created", "last_updated", "actions")
        default_columns = ("pk", "name", "system", "actions")


class SystemAddressTable(NetBoxTable):
    system = tables.Column(linkify=True, verbose_name=_("Application system"))
    address_type = tables.Column(orderable=False, verbose_name=_("Type"))
    address_object = tables.Column(linkify=True, orderable=False, verbose_name=_("Native address"))
    vrf = tables.Column(linkify=True, orderable=False, verbose_name="VRF")
    matched_prefix = tables.Column(empty_values=(), linkify=True, orderable=False, verbose_name="匹配 Prefix")
    security_zone = tables.Column(empty_values=(), orderable=False, verbose_name="安全区域")
    resolution_status = tables.Column(empty_values=(), orderable=False, verbose_name="解析状态")

    class Meta(NetBoxTable.Meta):
        model = SystemAddress
        fields = (
            "pk",
            "id",
            "system",
            "address_type",
            "address_object",
            "created",
            "last_updated",
        )
        default_columns = ("pk", "address_type", "address_object", "vrf", "matched_prefix", "security_zone", "resolution_status", "actions")

    def render_vrf(self, value):
        return value or "全局"

    def render_matched_prefix(self, record):
        return record.zone_evidence.matched_prefix or "—"

    def render_security_zone(self, record):
        return record.zone_evidence.bucket.label

    def render_resolution_status(self, record):
        evidence = record.zone_evidence
        return f"{evidence.reason}（{evidence.rule_version}）"


class AccessPolicyTable(PrimaryModelTable):
    name = tables.Column(
        linkify=True,
        verbose_name=_("Name"),
        attrs={"th": {"style": "width: 14rem"}},
    )
    category = tables.Column(
        verbose_name=_("Category"),
        attrs={"th": {"style": "width: 12rem"}},
    )
    source_system = tables.Column(
        linkify=True,
        verbose_name=_("Source system"),
        attrs={"th": {"style": "width: 10rem"}},
    )
    target_system = tables.Column(
        linkify=True,
        verbose_name=_("Target system"),
        attrs={"th": {"style": "width: 10rem"}},
    )
    source_ipam = tables.TemplateColumn(
        template_name="netbox_access_relations/inc/policy_ipam_addresses.html",
        extra_context={"endpoint": "source"},
        orderable=False,
        verbose_name=_("Source IPAM information"),
        attrs={"th": {"style": "width: 15rem"}},
    )
    target_ipam = tables.TemplateColumn(
        template_name="netbox_access_relations/inc/policy_ipam_addresses.html",
        extra_context={"endpoint": "target"},
        orderable=False,
        verbose_name=_("Target IPAM information"),
        attrs={"th": {"style": "width: 15rem"}},
    )
    effective_status_label = tables.Column(
        orderable=False,
        verbose_name=_("Effective status"),
        attrs={"th": {"style": "width: 7rem"}},
    )
    services = tables.Column(
        empty_values=(),
        orderable=False,
        verbose_name=_("Services"),
        attrs={"th": {"style": "width: 12rem"}},
    )
    tags = columns.TagColumn(url_name="plugins:netbox_access_relations:accesspolicy_list")

    class Meta(PrimaryModelTable.Meta):
        model = AccessPolicy
        fields = (
            "pk", "id", "name", "category", "source_system", "source_ipam", "target_system", "target_ipam", "effective_status_label",
            "valid_from", "valid_until", "services", "description", "comments", "tags", "actions",
        )
        default_columns = (
            "pk", "name", "category", "source_system", "source_ipam", "target_system", "target_ipam",
            "effective_status_label", "services",
        )

    def render_services(self, record):
        services = record.services.all()
        if not services:
            return "—"
        return format_html_join(
            mark_safe("<br>"),
            "{}",
            ((self._service_label(service),) for service in services),
        )

    @staticmethod
    def _service_label(service):
        return str(service.port_display) if service.is_any else f"{service.get_protocol_display()}_{service.port_display}"

    @staticmethod
    def _export_endpoint_ipam(addresses):
        return "\n".join(
            f"{address.address_object}（VRF：{address.vrf}）" if address.vrf else str(address.address_object)
            for address in addresses
        ) or "—"

    def value_source_ipam(self, record):
        return self._export_endpoint_ipam(record.source_system.addresses.all())

    def value_target_ipam(self, record):
        return self._export_endpoint_ipam(record.target_system.addresses.all())

    def value_services(self, record):
        return "\n".join(self._service_label(service) for service in record.services.all()) or "—"


class PolicyServiceTable(NetBoxTable):
    policy = tables.Column(linkify=True, verbose_name=_("Access policy"))
    source_system = tables.Column(accessor="policy.source_system", linkify=True, verbose_name=_("Source system"))
    target_system = tables.Column(accessor="policy.target_system", linkify=True, verbose_name=_("Target system"))
    protocol = columns.ChoiceFieldColumn(verbose_name=_("Protocol"))
    port_type = tables.Column(empty_values=(), orderable=False, verbose_name="端口类型")
    port_display = tables.Column(orderable=False, verbose_name=_("Destination port"))
    effective_status = tables.Column(accessor="policy.effective_status_label", orderable=False, verbose_name=_("Effective status"))
    overlap_count = tables.Column(empty_values=(), orderable=False, verbose_name="服务交集提示")

    class Meta(NetBoxTable.Meta):
        model = PolicyService
        exclude = ("actions",)
        fields = (
            "pk", "id", "protocol", "port_type", "port_display", "policy", "source_system",
            "target_system", "effective_status", "overlap_count", "created", "last_updated",
        )
        default_columns = (
            "pk", "protocol", "port_type", "port_display", "policy", "source_system",
            "target_system", "effective_status", "overlap_count",
        )

    def render_port_type(self, record):
        if record.is_any:
            return "ANY"
        return "单端口" if record.port_start == record.port_end else "端口范围"

    def render_overlap_count(self, record):
        queryset = PolicyService.objects.all()
        request = getattr(self, "request", None)
        if request is not None:
            queryset = queryset.restrict(request.user, "view").filter(
                policy_id__in=AccessPolicy.objects.restrict(request.user, "view").values("pk")
            )
        value = record.overlap_count_in(queryset)
        return f"与 {value} 条其他访问关系相交" if value else "无交集"
