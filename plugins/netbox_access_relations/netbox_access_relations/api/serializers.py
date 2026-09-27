"""REST and event serializers for access-relations objects."""

from ipam.api.serializers_.ip import IPAddressSerializer, IPRangeSerializer, PrefixSerializer
from rest_framework import serializers
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer

from ..models import AccessPolicy, ActiveStatusChoices, ApplicationSystem, PolicyService, SystemAddress, SystemAlias, TransportProtocolChoices


class ApplicationSystemSerializer(PrimaryModelSerializer):
    status = ChoiceField(choices=ActiveStatusChoices.choices)

    class Meta:
        model = ApplicationSystem
        fields = (
            "id",
            "url",
            "display_url",
            "display",
            "name",
            "status",
            "is_co_located",
            "description",
            "owner",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "status", "is_co_located")
        read_only_fields = ("is_co_located",)


class SystemAliasSerializer(NetBoxModelSerializer):
    system = ApplicationSystemSerializer(nested=True)

    class Meta:
        model = SystemAlias
        fields = (
            "id", "url", "display_url", "display", "system", "name", "tags",
            "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "system")


class SystemAddressSerializer(NetBoxModelSerializer):
    system = ApplicationSystemSerializer(nested=True)
    prefix = PrefixSerializer(nested=True, required=False, allow_null=True)
    ip_address = IPAddressSerializer(nested=True, required=False, allow_null=True)
    ip_range = IPRangeSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = SystemAddress
        fields = (
            "id",
            "url",
            "display_url",
            "display",
            "system",
            "prefix",
            "ip_address",
            "ip_range",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
        brief_fields = ("id", "url", "display")


class AccessPolicySerializer(PrimaryModelSerializer):
    source_system = ApplicationSystemSerializer(nested=True)
    target_system = ApplicationSystemSerializer(nested=True)
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = AccessPolicy
        fields = (
            "id", "url", "display_url", "display", "name", "category", "source_system", "target_system",
            "valid_from", "valid_until", "effective_status", "description", "owner", "comments", "tags",
            "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "source_system", "target_system", "effective_status")

    def get_effective_status(self, obj):
        return obj.effective_status


class PolicyServiceSerializer(NetBoxModelSerializer):
    policy = AccessPolicySerializer(nested=True)
    protocol = ChoiceField(choices=TransportProtocolChoices.choices)
    port_display = serializers.CharField(read_only=True)

    class Meta:
        model = PolicyService
        fields = (
            "id", "url", "display_url", "display", "policy", "protocol", "is_any", "port_start", "port_end",
            "port_display", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "protocol", "port_display")
