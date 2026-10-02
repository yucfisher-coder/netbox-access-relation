"""REST API 视图集：为五个模型提供标准的 CRUD REST 端点。

所有视图集继承 NetBoxModelViewSet，自动获得：
- 列表、详情、创建、更新、删除操作
- NetBox 对象级权限（restrict）
- 过滤器集集成
- 分页、排序、搜索
"""

from rest_framework.routers import APIRootView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets
from ..models import AccessPolicy, ApplicationSystem, PolicyService, SystemAddress, SystemAlias
from . import serializers


class AccessRelationsRootView(APIRootView):
    def get_view_name(self):
        return "Access Relations"


class ObjectPermissionCreateMixin:
    """Apply NetBox object-level add constraints after a serializer writes."""

    permission_model = None

    def perform_create(self, serializer):
        with transaction.atomic():
            super().perform_create(serializer)
            instance = serializer.instance
            if not self.permission_model.objects.restrict(self.request.user, "add").filter(pk=instance.pk).exists():
                raise PermissionDenied("You do not have permission to create this object.")


class ApplicationSystemViewSet(ObjectPermissionCreateMixin, NetBoxModelViewSet):
    permission_model = ApplicationSystem
    queryset = ApplicationSystem.objects.all()
    serializer_class = serializers.ApplicationSystemSerializer
    filterset_class = filtersets.ApplicationSystemFilterSet


class SystemAliasViewSet(ObjectPermissionCreateMixin, NetBoxModelViewSet):
    permission_model = SystemAlias
    queryset = SystemAlias.objects.select_related("system")
    serializer_class = serializers.SystemAliasSerializer
    filterset_class = filtersets.SystemAliasFilterSet


class SystemAddressViewSet(ObjectPermissionCreateMixin, NetBoxModelViewSet):
    permission_model = SystemAddress
    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")
    serializer_class = serializers.SystemAddressSerializer
    filterset_class = filtersets.SystemAddressFilterSet


class AccessPolicyViewSet(ObjectPermissionCreateMixin, NetBoxModelViewSet):
    permission_model = AccessPolicy
    queryset = AccessPolicy.objects.select_related("source_system", "target_system").prefetch_related("services")
    serializer_class = serializers.AccessPolicySerializer
    filterset_class = filtersets.AccessPolicyFilterSet


class PolicyServiceViewSet(ObjectPermissionCreateMixin, NetBoxModelViewSet):
    permission_model = PolicyService
    queryset = PolicyService.objects.select_related("policy", "policy__source_system", "policy__target_system")
    serializer_class = serializers.PolicyServiceSerializer
    filterset_class = filtersets.PolicyServiceFilterSet

    def perform_destroy(self, instance):
        """Keep the model invariant intact even for direct REST deletions."""
        with transaction.atomic():
            policy = AccessPolicy.objects.select_for_update().get(pk=instance.policy_id)
            remaining = PolicyService.objects.select_for_update().filter(policy=policy).count()
            if remaining <= 1:
                raise ValidationError({"detail": "An access policy requires at least one service."})
            instance.delete()
