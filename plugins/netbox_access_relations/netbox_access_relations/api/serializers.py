"""REST and event serializers for access-relations objects."""

from ipam.api.serializers_.ip import IPAddressSerializer, IPRangeSerializer, PrefixSerializer
from rest_framework import serializers
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer

from ..models import AccessPolicy, ActiveStatusChoices, ApplicationSystem, PolicyService, SystemAddress, SystemAlias, TransportProtocolChoices
from ..services.policy_uniqueness import find_duplicate_policies, get_policy_service_keys, service_key


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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # On create the service set does not exist yet; services are added via
        # the policy-service endpoint, which performs its own check.
        if self.instance is None:
            return attrs
        source = attrs.get("source_system", self.instance.source_system)
        target = attrs.get("target_system", self.instance.target_system)
        source_id = getattr(source, "pk", source)
        target_id = getattr(target, "pk", target)
        if source_id and target_id and source_id != target_id:
            duplicates = find_duplicate_policies(
                source_id,
                target_id,
                get_policy_service_keys(self.instance),
                exclude_policy_id=self.instance.pk,
            )
            if duplicates:
                names = "、".join(p.name for p in duplicates)
                raise serializers.ValidationError(
                    f"已存在源系统、目标系统与服务项完全相同的访问关系：{names}。"
                )
        return attrs


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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        policy = attrs.get("policy") or (self.instance.policy if self.instance else None)
        if policy is None:
            return attrs
        # Compute the policy's service set as it would look after this write.
        keys = set(get_policy_service_keys(policy))
        if self.instance is not None:
            keys.discard(service_key(
                self.instance.protocol, self.instance.is_any,
                self.instance.port_start, self.instance.port_end,
            ))
        keys.add(service_key(
            attrs.get("protocol", self.instance.protocol if self.instance else None),
            attrs.get("is_any", self.instance.is_any if self.instance else False),
            attrs.get("port_start", self.instance.port_start if self.instance else None),
            attrs.get("port_end", self.instance.port_end if self.instance else None),
        ))
        duplicates = find_duplicate_policies(
            policy.source_system_id,
            policy.target_system_id,
            frozenset(keys),
            exclude_policy_id=policy.pk,
        )
        if duplicates:
            names = "、".join(p.name for p in duplicates)
            raise serializers.ValidationError(
                f"已存在源系统、目标系统与服务项完全相同的访问关系：{names}。"
            )
        return attrs
