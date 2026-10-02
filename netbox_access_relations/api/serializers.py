"""REST and event serializers for access-relations objects."""

from django.db import transaction
from ipam.api.serializers_.ip import IPAddressSerializer, IPRangeSerializer, PrefixSerializer
from rest_framework import serializers
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer

from ..models import AccessPolicy, ActiveStatusChoices, ApplicationSystem, PolicyService, SystemAddress, SystemAlias, TransportProtocolChoices
from ..services.policy_uniqueness import find_duplicate_policies, get_policy_service_keys, service_key


def _require_visible_relation(value, request, field_name):
    """Reject references to objects outside the caller's view permission scope."""
    if value is None or request is None:
        return
    if not value.__class__.objects.restrict(request.user, "view").filter(pk=value.pk).exists():
        # Keep the response intentionally indistinguishable from a missing ID.
        raise serializers.ValidationError({field_name: "Invalid object reference."})


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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _require_visible_relation(attrs.get("system"), self.context.get("request"), "system")
        return attrs


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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        _require_visible_relation(attrs.get("system"), request, "system")
        for field_name in ("prefix", "ip_address", "ip_range"):
            _require_visible_relation(attrs.get(field_name), request, field_name)
        return attrs


class PolicyServiceInputSerializer(serializers.Serializer):
    """Writable service representation used only while creating a policy."""

    protocol = ChoiceField(choices=TransportProtocolChoices.choices, required=False)
    is_any = serializers.BooleanField(default=False)
    port_start = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=65535)
    port_end = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=65535)

    def validate(self, attrs):
        is_any = attrs["is_any"]
        start, end = attrs.get("port_start"), attrs.get("port_end")
        if is_any:
            if start is not None or end is not None:
                raise serializers.ValidationError("ANY services must not specify ports.")
            attrs["protocol"] = TransportProtocolChoices.TCP
        elif not attrs.get("protocol"):
            raise serializers.ValidationError({"protocol": "Protocol is required unless the service is ANY."})
        elif start is None or end is None or start > end:
            raise serializers.ValidationError("A non-ANY service requires a valid port range.")
        return attrs


class AccessPolicySerializer(PrimaryModelSerializer):
    source_system = ApplicationSystemSerializer(nested=True)
    target_system = ApplicationSystemSerializer(nested=True)
    effective_status = serializers.SerializerMethodField()
    services = PolicyServiceInputSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = AccessPolicy
        fields = (
            "id", "url", "display_url", "display", "name", "category", "source_system", "target_system",
            "valid_from", "valid_until", "effective_status", "services", "description", "owner", "comments", "tags",
            "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "name", "source_system", "target_system", "effective_status")

    def get_effective_status(self, obj):
        return obj.effective_status

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        _require_visible_relation(attrs.get("source_system"), request, "source_system")
        _require_visible_relation(attrs.get("target_system"), request, "target_system")
        submitted_services = attrs.get("services")
        if self.instance is None:
            # This serializer is also used as the writable nested reference on
            # PolicyServiceSerializer.  Referencing an existing policy must
            # not be mistaken for creating a new policy.
            if self.parent is not None:
                return attrs
            keys = {
                service_key(service["protocol"], service["is_any"], service.get("port_start"), service.get("port_end"))
                for service in submitted_services or ()
            }
            if not keys:
                raise serializers.ValidationError({"services": "An access policy requires at least one service."})
            if len(keys) != len(submitted_services):
                raise serializers.ValidationError({"services": "Duplicate services are not allowed within an access policy."})
            source, target = attrs.get("source_system"), attrs.get("target_system")
            source_id, target_id = getattr(source, "pk", source), getattr(target, "pk", target)
            if source_id and target_id:
                duplicates = find_duplicate_policies(source_id, target_id, frozenset(keys))
                if duplicates:
                    raise serializers.ValidationError({"services": "An access policy with these endpoints and services already exists."})
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

    def create(self, validated_data):
        services = validated_data.pop("services")
        with transaction.atomic():
            # Serialize competing policy creations for the same endpoints.
            source_id = getattr(validated_data["source_system"], "pk", validated_data["source_system"])
            target_id = getattr(validated_data["target_system"], "pk", validated_data["target_system"])
            list(ApplicationSystem.objects.select_for_update().filter(pk__in=(source_id, target_id)).order_by("pk"))
            keys = frozenset(
                service_key(service["protocol"], service["is_any"], service.get("port_start"), service.get("port_end"))
                for service in services
            )
            if find_duplicate_policies(source_id, target_id, keys):
                raise serializers.ValidationError({"services": "An access policy with these endpoints and services already exists."})
            policy = super().create(validated_data)
            for service_data in services:
                service = PolicyService(policy=policy, **service_data)
                service.full_clean()
                service.save()
        return policy

    def update(self, instance, validated_data):
        # Service edits stay on their dedicated endpoint.  Requiring the full
        # set on PATCH would make ordinary policy metadata edits needlessly
        # destructive.
        validated_data.pop("services", None)
        return super().update(instance, validated_data)


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
        _require_visible_relation(attrs.get("policy"), self.context.get("request"), "policy")
        if policy is None:
            return attrs
        if self.instance is not None and "policy" in attrs and policy.pk != self.instance.policy_id:
            raise serializers.ValidationError({"policy": "Moving a service to another access policy is not supported."})
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
