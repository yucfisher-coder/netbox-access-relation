"""REST API URL registration."""

from netbox.api.routers import NetBoxRouter

from . import views


router = NetBoxRouter()
router.APIRootView = views.AccessRelationsRootView
router.register("application-systems", views.ApplicationSystemViewSet)
router.register("system-aliases", views.SystemAliasViewSet)
router.register("system-addresses", views.SystemAddressViewSet)
router.register("access-policies", views.AccessPolicyViewSet)
router.register("policy-services", views.PolicyServiceViewSet)

app_name = "netbox_access_relations-api"
urlpatterns = router.urls
