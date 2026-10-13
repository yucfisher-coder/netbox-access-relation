"""Plugin navigation menu."""

from django.utils.translation import gettext_lazy as _
from netbox.plugins.navigation import PluginMenuButton, PluginMenuItem


application_systems = PluginMenuItem(
    link="plugins:netbox_access_relations:applicationsystem_list",
    link_text=_("Application systems"),
    permissions=("netbox_access_relations.view_applicationsystem",),
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_access_relations:applicationsystem_add",
            title=_("Add application system"),
            icon_class="mdi mdi-plus-thick",
            permissions=("netbox_access_relations.add_applicationsystem",),
        ),
        PluginMenuButton(
            link="plugins:netbox_access_relations:systems_import",
            title=_("Import application systems and addresses"),
            icon_class="mdi mdi-upload",
            permissions=(
                "netbox_access_relations.add_applicationsystem",
                "netbox_access_relations.add_systemalias",
                "netbox_access_relations.add_systemaddress",
            ),
        ),
    ),
)

access_policies = PluginMenuItem(
    link="plugins:netbox_access_relations:accesspolicy_list",
    link_text=_("Access policies"),
    permissions=("netbox_access_relations.view_accesspolicy",),
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_access_relations:accesspolicy_add", title=_("Add access policy"),
            icon_class="mdi mdi-plus-thick", permissions=("netbox_access_relations.add_accesspolicy",),
        ),
        PluginMenuButton(
            link="plugins:netbox_access_relations:policies_import",
            title=_("Import access policies and services"),
            icon_class="mdi mdi-upload",
            permissions=("netbox_access_relations.add_accesspolicy", "netbox_access_relations.add_policyservice"),
        ),
    ),
)

service_query = PluginMenuItem(
    link="plugins:netbox_access_relations:policyservice_list",
    link_text=_("Service query"),
    permissions=("netbox_access_relations.view_policyservice",),
)

zone_matrix = PluginMenuItem(
    link="plugins:netbox_access_relations:zone_matrix",
    link_text=_("Zone matrix"),
    permissions=("netbox_access_relations.view_accesspolicy",),
)

# Register the links in NetBox's standard Plugins menu.  This is the navigation
# resource rendered by the sidebar in NetBox 4.7.
menu_items = (application_systems, access_policies, service_query, zone_matrix)
