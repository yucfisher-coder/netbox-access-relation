"""Web URL registration for the plugin."""

from django.urls import include, path
from utilities.urls import get_model_urls

from . import views  # noqa: F401


app_name = "netbox_access_relations"
urlpatterns = [
    path("zone-matrix/", views.ZoneMatrixView.as_view(), name="zone_matrix"),
    path("systems/import/", views.ApplicationSystemImportView.as_view(), name="systems_import"),
    path("systems/import/template/", views.ApplicationSystemTemplateView.as_view(), name="systems_import_template"),
    path("policies/import/", views.AccessPolicyImportView.as_view(), name="policies_import"),
    path("policies/import/template/", views.AccessPolicyTemplateView.as_view(), name="policies_import_template"),
    path("policies/<int:pk>/terminate/", views.AccessPolicyTerminateView.as_view(), name="accesspolicy_terminate"),
    path("policies/", include(get_model_urls("netbox_access_relations", "accesspolicy", detail=False))),
    path("policies/<int:pk>/", include(get_model_urls("netbox_access_relations", "accesspolicy"))),
    path("services/", include(get_model_urls("netbox_access_relations", "policyservice", detail=False))),
    path("services/<int:pk>/", include(get_model_urls("netbox_access_relations", "policyservice"))),
    path("systems/", include(get_model_urls("netbox_access_relations", "applicationsystem", detail=False))),
    path("systems/<int:pk>/", include(get_model_urls("netbox_access_relations", "applicationsystem"))),
    path("system-aliases/", include(get_model_urls("netbox_access_relations", "systemalias", detail=False))),
    path("system-aliases/<int:pk>/", include(get_model_urls("netbox_access_relations", "systemalias"))),
    path("system-addresses/", include(get_model_urls("netbox_access_relations", "systemaddress", detail=False))),
    path("system-addresses/<int:pk>/", include(get_model_urls("netbox_access_relations", "systemaddress"))),
]
