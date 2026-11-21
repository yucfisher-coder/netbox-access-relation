"""Object detail panels."""

from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs, panels

from ..models import PolicyService


class ApplicationSystemPanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr("name", label=_("Name"))
    status = attrs.ChoiceAttr("status", label=_("Status"))
    is_co_located = attrs.BooleanAttr("is_co_located", label=_("Co-located"))
    description = attrs.TextAttr("description", label=_("Description"))
    owner = attrs.RelatedObjectAttr("owner", linkify=True, label=_("Owner"))


class SystemAliasPanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr("name", label=_("Alias"))
    system = attrs.RelatedObjectAttr("system", linkify=True, label=_("Application system"))


class SystemAddressPanel(panels.ObjectAttributesPanel):
    system = attrs.RelatedObjectAttr("system", linkify=True, label=_("Application system"))
    address_type = attrs.TextAttr("address_type", label=_("Type"))
    address_object = attrs.RelatedObjectAttr("address_object", linkify=True, label=_("Native address"))


class AccessPolicyPanel(panels.ObjectAttributesPanel):
    name = attrs.TextAttr("name", label=_("Name"))
    category = attrs.TextAttr("category", label=_("Category"))
    source_system = attrs.RelatedObjectAttr("source_system", linkify=True, label=_("Source system"))
    target_system = attrs.RelatedObjectAttr("target_system", linkify=True, label=_("Target system"))
    effective_status_label = attrs.TextAttr("effective_status_label", label=_("Effective status"))
    valid_from = attrs.DateTimeAttr("valid_from", label=_("Valid from"))
    valid_until = attrs.DateTimeAttr("valid_until", label=_("Valid until"))
    description = attrs.TextAttr("description", label=_("Description"))


class AccessPolicyServicesPanel(panels.Panel):
    title = _("Policy services")
    template_name = "netbox_access_relations/inc/policy_services_panel.html"

    def should_render(self, context):
        return context["request"].user.has_perm("netbox_access_relations.view_policyservice")

    def get_context(self, context):
        return {
            **super().get_context(context),
            "services": PolicyService.objects.restrict(context["request"].user, "view").filter(
                policy=context["object"],
            ),
        }


class PolicyServicePanel(panels.ObjectAttributesPanel):
    policy = attrs.RelatedObjectAttr("policy", linkify=True, label=_("Access policy"))
    protocol = attrs.TextAttr("protocol_display", label=_("Protocol"))
    port_display = attrs.TextAttr("port_display", label=_("Destination port"))
