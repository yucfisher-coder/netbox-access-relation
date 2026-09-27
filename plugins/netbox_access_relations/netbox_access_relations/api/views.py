"""REST API 视图集：为五个模型提供标准的 CRUD REST 端点。

所有视图集继承 NetBoxModelViewSet，自动获得：
- 列表、详情、创建、更新、删除操作
- NetBox 对象级权限（restrict）
- 过滤器集集成
- 分页、排序、搜索
"""

from rest_framework.routers import APIRootView
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets
from ..models import AccessPolicy, ApplicationSystem, PolicyService, SystemAddress, SystemAlias
from . import serializers


class AccessRelationsRootView(APIRootView):
    def get_view_name(self):
        return "Access Relations"


class ApplicationSystemViewSet(NetBoxModelViewSet):
    queryset = ApplicationSystem.objects.all()
    serializer_class = serializers.ApplicationSystemSerializer
    filterset_class = filtersets.ApplicationSystemFilterSet


class SystemAliasViewSet(NetBoxModelViewSet):
    queryset = SystemAlias.objects.select_related("system")
    serializer_class = serializers.SystemAliasSerializer
    filterset_class = filtersets.SystemAliasFilterSet


class SystemAddressViewSet(NetBoxModelViewSet):
    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")
    serializer_class = serializers.SystemAddressSerializer
    filterset_class = filtersets.SystemAddressFilterSet


class AccessPolicyViewSet(NetBoxModelViewSet):
    queryset = AccessPolicy.objects.select_related("source_system", "target_system").prefetch_related("services")
    serializer_class = serializers.AccessPolicySerializer
    filterset_class = filtersets.AccessPolicyFilterSet


class PolicyServiceViewSet(NetBoxModelViewSet):
    queryset = PolicyService.objects.select_related("policy", "policy__source_system", "policy__target_system")
    serializer_class = serializers.PolicyServiceSerializer
    filterset_class = filtersets.PolicyServiceFilterSet
