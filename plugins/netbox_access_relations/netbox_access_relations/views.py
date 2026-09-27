"""NetBox-native object views for the plugin."""

from functools import partial
import base64
from itertools import chain
import logging

from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.object_actions import AddObject, BulkExport, CloneObject, DeleteObject, EditObject, ObjectAction
from netbox.ui import layout
from netbox.ui import actions as panel_actions
from netbox.ui.panels import CommentsPanel, ObjectsTablePanel
from netbox.views import generic
from utilities.views import register_model_view
from utilities.forms import restrict_form_fields

from . import filtersets, forms, tables
from .models import AccessPolicy, ApplicationSystem, PolicyService, SystemAddress, SystemAlias
from .ui.panels import AccessPolicyPanel, ApplicationSystemPanel, PolicyServicePanel, SystemAddressPanel, SystemAliasPanel
from .services.workbook_import import apply_workbook, build_template, preview_workbook
from .services.zones import policy_zone_pairs


class ExcelCompatibleCsvExportMixin:
    """Prefix table CSV exports with a UTF-8 BOM for spreadsheet applications."""

    def export_table(self, *args, **kwargs):
        response = super().export_table(*args, **kwargs)
        if response.streaming:
            response.streaming_content = chain(("\ufeff",), response.streaming_content)
        else:
            response.content = "\ufeff" + response.content.decode(response.charset or "utf-8")
        return response


class ZoneMatrixView(PermissionRequiredMixin, View):
    permission_required = ("netbox_access_relations.view_accesspolicy",)
    template_name = "netbox_access_relations/zone_matrix.html"

    def get(self, request):
        form = forms.ZoneMatrixFilterForm(request.GET)
        params = request.GET.copy()
        params.pop("export", None)
        queryset = AccessPolicy.objects.restrict(request.user, "view").select_related(
            "source_system", "target_system"
        ).prefetch_related(
            "services", "source_system__addresses__prefix", "source_system__addresses__ip_address",
            "source_system__addresses__ip_range", "target_system__addresses__prefix",
            "target_system__addresses__ip_address", "target_system__addresses__ip_range",
        )
        if form.is_valid():
            queryset = filtersets.AccessPolicyFilterSet(params, queryset=queryset).qs
        policies = list(queryset)
        counts = {}
        buckets = set()
        for policy in policies:
            for source, target in policy_zone_pairs(policy):
                buckets.update((source, target))
                counts[(source.key, target.key)] = counts.get((source.key, target.key), 0) + 1
        ordered = sorted(buckets, key=lambda item: (item.state != "resolved", item.label, item.key))
        rows = []
        for source in ordered:
            cells = []
            for target in ordered:
                count = counts.get((source.key, target.key), 0)
                drilldown = params.copy()
                drilldown["source_zone"] = source.key
                drilldown["target_zone"] = target.key
                cells.append({"count": count, "url": f'{reverse("plugins:netbox_access_relations:accesspolicy_list")}?{drilldown.urlencode()}' if count else ""})
            rows.append({"bucket": source, "cells": cells, "total": sum(cell["count"] for cell in cells)})
        column_totals = [sum(counts.get((source.key, target.key), 0) for source in ordered) for target in ordered]
        context = {
            "title": "区域矩阵", "form": form, "buckets": ordered, "rows": rows,
            "column_totals": column_totals, "cell_total": sum(counts.values()),
            "policy_total": len(policies), "query": params.urlencode(),
        }
        if request.GET.get("export") == "csv":
            return self._export(context)
        return render(request, self.template_name, context)

    def _export(self, context):
        import csv
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="zone-matrix.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["筛选条件", context["query"] or "无"])
        writer.writerow(["源区域", "目标区域", "访问关系数"])
        for row in context["rows"]:
            for target, cell in zip(context["buckets"], row["cells"]):
                writer.writerow([row["bucket"].label, target.label, cell["count"]])
        return response


class WorkbookUploadForm(django_forms.Form):
    workbook = django_forms.FileField(label="XLSX 工作簿")

    def clean_workbook(self):
        upload = self.cleaned_data["workbook"]
        if not upload.name.lower().endswith(".xlsx"):
            raise django_forms.ValidationError("请上传 .xlsx 工作簿。")
        if upload.size > 5 * 1024 * 1024:
            raise django_forms.ValidationError("工作簿大小不得超过 5 MB。")
        return upload


class WorkbookTemplateView(PermissionRequiredMixin, View):
    kind = None
    permission_required = ()

    def get(self, request):
        response = HttpResponse(
            build_template(self.kind),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="access-relations-{self.kind}-v1.0.xlsx"'
        return response


class WorkbookImportView(PermissionRequiredMixin, View):
    """Two-step preview/confirmation without retaining the uploaded file."""

    kind = None
    title = None
    permission_required = ()
    template_name = "netbox_access_relations/workbook_import.html"

    def get(self, request):
        return self._render(request, WorkbookUploadForm())

    def post(self, request):
        if request.POST.get("confirm"):
            return self._confirm(request)
        form = WorkbookUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form)
        content = form.cleaned_data["workbook"].read()
        plan = preview_workbook(content, self.kind, request.user)
        token = signing.dumps({"kind": self.kind, "content": base64.b64encode(content).decode("ascii")}, compress=True)
        return self._render(request, form, plan=plan, token=token)

    def _confirm(self, request):
        try:
            payload = signing.loads(request.POST.get("token", ""), max_age=1800)
            if payload.get("kind") != self.kind:
                raise signing.BadSignature
            content = base64.b64decode(payload["content"], validate=True)
            plan = apply_workbook(content, self.kind, request.user)
        except (signing.BadSignature, KeyError, ValueError):
            form = WorkbookUploadForm()
            form.add_error(None, "预检结果已过期或无效，请重新上传工作簿。")
            return self._render(request, form, status=400)
        except ValidationError as exc:
            form = WorkbookUploadForm()
            form.add_error(None, exc)
            return self._render(request, form, status=409)
        messages.success(request, "工作簿导入成功。")
        return self._render(request, WorkbookUploadForm(), plan=plan, applied=True)

    def _render(self, request, form, *, plan=None, token=None, applied=False, status=200):
        return render(request, self.template_name, {
            "form": form,
            "kind": self.kind,
            "title": self.title,
            "plan": plan,
            "token": token,
            "applied": applied,
            "template_url": reverse(f"plugins:netbox_access_relations:{self.kind}_import_template"),
        }, status=status)


class ApplicationSystemTemplateView(WorkbookTemplateView):
    kind = "systems"
    permission_required = ("netbox_access_relations.view_applicationsystem",)


class ApplicationSystemImportView(WorkbookImportView):
    kind = "systems"
    title = _("Import application systems and addresses")
    permission_required = (
        "netbox_access_relations.add_applicationsystem",
        "netbox_access_relations.add_systemalias",
        "netbox_access_relations.add_systemaddress",
    )


class AccessPolicyTemplateView(WorkbookTemplateView):
    kind = "policies"
    permission_required = ("netbox_access_relations.view_accesspolicy",)


class AccessPolicyImportView(WorkbookImportView):
    kind = "policies"
    title = _("Import access policies and services")
    permission_required = (
        "netbox_access_relations.add_accesspolicy",
        "netbox_access_relations.add_policyservice",
    )


class ApplicationSystemImportAction(ObjectAction):
    label = _("Import systems and addresses")
    permissions_required = {"add"}
    template_name = "buttons/import.html"

    @classmethod
    def get_url(cls, model):
        return reverse("plugins:netbox_access_relations:systems_import")


class AccessPolicyImportAction(ObjectAction):
    label = _("Import policies and services")
    permissions_required = {"add"}
    template_name = "buttons/import.html"

    @classmethod
    def get_url(cls, model):
        return reverse("plugins:netbox_access_relations:policies_import")


class TerminateAccessPolicyAction(ObjectAction):
    name = "terminate"
    label = "提前终止"
    permissions_required = {"change"}
    url_kwargs = ["pk"]
    template_name = "buttons/edit.html"


class AccessPolicyTerminateView(PermissionRequiredMixin, View):
    permission_required = ("netbox_access_relations.change_accesspolicy",)
    template_name = "netbox_access_relations/accesspolicy_terminate.html"

    def _object(self, request, pk):
        return AccessPolicy.objects.restrict(request.user, "view").get(pk=pk)

    def get(self, request, pk):
        policy = self._object(request, pk)
        return render(request, self.template_name, {"object": policy, "title": "提前终止访问关系"})

    def post(self, request, pk):
        policy = self._object(request, pk)
        now = timezone.now()
        if policy.valid_until is not None and policy.valid_until <= now:
            messages.warning(request, "该访问关系已经失效，无需重复终止。")
        elif policy.valid_from is not None and policy.valid_from > now:
            messages.error(request, "尚未生效的访问关系不能提前终止，请改为编辑有效期。")
        else:
            policy.valid_until = now
            policy.save(update_fields=("valid_until", "last_updated"))
            messages.success(request, f"访问关系“{policy.name}”已提前终止。")
        return redirect(policy.get_absolute_url())


class MaintainAddressesAction(panel_actions.PanelAction):
    template_name = "ui/actions/link.html"

    def __init__(self):
        super().__init__(
            label=_("Maintain addresses"),
            permissions=(
                "netbox_access_relations.change_applicationsystem",
                "netbox_access_relations.view_systemaddress",
            ),
            button_icon="pencil",
        )

    def get_context(self, context):
        return {
            **super().get_context(context),
            "url": reverse(
                "plugins:netbox_access_relations:applicationsystem_edit",
                args=[context["object"].pk],
            ) + "#system-addresses",
        }


@register_model_view(ApplicationSystem, "list", path="", detail=False)
class ApplicationSystemListView(ExcelCompatibleCsvExportMixin, generic.ObjectListView):
    queryset = ApplicationSystem.objects.prefetch_related(
        "addresses__prefix", "addresses__ip_address", "addresses__ip_range"
    )
    filterset = filtersets.ApplicationSystemFilterSet
    filterset_form = forms.ApplicationSystemFilterForm
    table = tables.ApplicationSystemTable
    actions = (AddObject, ApplicationSystemImportAction, BulkExport)


@register_model_view(ApplicationSystem)
class ApplicationSystemView(generic.ObjectView):
    queryset = ApplicationSystem.objects.all()
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[ApplicationSystemPanel(), TagsPanel()],
        right_panels=[CustomFieldsPanel(), CommentsPanel()],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_access_relations.systemalias",
                filters={"system_id": lambda context: context["object"].pk},
                exclude_columns=["system"],
                title=_("System aliases"),
                actions=[panel_actions.AddObject(
                    "netbox_access_relations.systemalias",
                    label=_("Add alias"),
                    url_params={"system": lambda context: context["object"].pk},
                )],
            ),
            ObjectsTablePanel(
                "netbox_access_relations.systemaddress",
                filters={"system_id": lambda context: context["object"].pk},
                exclude_columns=["system"],
                title=_("System addresses"),
                actions=[MaintainAddressesAction()],
            ),
            ObjectsTablePanel(
                "netbox_access_relations.accesspolicy",
                filters={"source_system_id": lambda context: context["object"].pk},
                exclude_columns=["source_system"],
                title=_("Outbound access policies"),
            ),
            ObjectsTablePanel(
                "netbox_access_relations.accesspolicy",
                filters={"target_system_id": lambda context: context["object"].pk},
                exclude_columns=["target_system"],
                title=_("Inbound access policies"),
            ),
        ],
    )


@register_model_view(ApplicationSystem, "add", detail=False)
@register_model_view(ApplicationSystem, "edit")
class ApplicationSystemEditView(generic.ObjectEditView):
    queryset = ApplicationSystem.objects.all()
    form = forms.ApplicationSystemWithAddressesForm
    template_name = "netbox_access_relations/applicationsystem_edit.html"

    def dispatch(self, request, *args, **kwargs):
        self.form = partial(forms.ApplicationSystemWithAddressesForm, user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)
        if instance.pk:
            context["affected_policies"] = AccessPolicy.objects.restrict(request.user, "view").filter(
                Q(source_system=instance) | Q(target_system=instance)
            ).distinct()
        return context


@register_model_view(ApplicationSystem, "delete")
class ApplicationSystemDeleteView(generic.ObjectDeleteView):
    queryset = ApplicationSystem.objects.all()


@register_model_view(SystemAlias, "list", path="", detail=False)
class SystemAliasListView(ExcelCompatibleCsvExportMixin, generic.ObjectListView):
    queryset = SystemAlias.objects.select_related("system")
    filterset = filtersets.SystemAliasFilterSet
    filterset_form = forms.SystemAliasFilterForm
    table = tables.SystemAliasTable
    actions = (AddObject, BulkExport)


@register_model_view(SystemAlias)
class SystemAliasView(generic.ObjectView):
    queryset = SystemAlias.objects.select_related("system")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[SystemAliasPanel(), TagsPanel()],
        right_panels=[CustomFieldsPanel()],
    )


@register_model_view(SystemAlias, "add", detail=False)
@register_model_view(SystemAlias, "edit")
class SystemAliasEditView(generic.ObjectEditView):
    queryset = SystemAlias.objects.select_related("system")
    form = forms.SystemAliasForm


@register_model_view(SystemAlias, "delete")
class SystemAliasDeleteView(generic.ObjectDeleteView):
    queryset = SystemAlias.objects.select_related("system")


@register_model_view(SystemAddress, "list", path="", detail=False)
class SystemAddressListView(generic.ObjectListView):
    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")
    filterset = filtersets.SystemAddressFilterSet
    table = tables.SystemAddressTable
    actions = (AddObject,)


@register_model_view(SystemAddress)
class SystemAddressView(generic.ObjectView):
    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(
        left_panels=[SystemAddressPanel(), TagsPanel()],
        right_panels=[CustomFieldsPanel()],
    )


@register_model_view(SystemAddress, "add", detail=False)
@register_model_view(SystemAddress, "edit")
class SystemAddressEditView(generic.ObjectEditView):
    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")
    form = forms.SystemAddressForm

    def dispatch(self, request, *args, **kwargs):
        self.form = partial(forms.SystemAddressForm, user=request.user)
        return super().dispatch(request, *args, **kwargs)


@register_model_view(SystemAddress, "delete")
class SystemAddressDeleteView(generic.ObjectDeleteView):
    """Delete only the association; native IPAM objects remain untouched."""

    queryset = SystemAddress.objects.select_related("system", "prefix", "ip_address", "ip_range")


@register_model_view(AccessPolicy, "list", path="", detail=False)
class AccessPolicyListView(ExcelCompatibleCsvExportMixin, generic.ObjectListView):
    queryset = AccessPolicy.objects.select_related("source_system", "target_system").prefetch_related(
        "services",
        "source_system__addresses__prefix",
        "source_system__addresses__ip_address",
        "source_system__addresses__ip_range",
        "target_system__addresses__prefix",
        "target_system__addresses__ip_address",
        "target_system__addresses__ip_range",
    )
    filterset = filtersets.AccessPolicyFilterSet
    filterset_form = forms.AccessPolicyFilterForm
    table = tables.AccessPolicyTable
    actions = (AddObject, AccessPolicyImportAction, BulkExport)


@register_model_view(AccessPolicy)
class AccessPolicyView(generic.ObjectView):
    queryset = AccessPolicy.objects.select_related("source_system", "target_system")
    template_name = "generic/object.html"
    actions = (CloneObject, EditObject, TerminateAccessPolicyAction, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[AccessPolicyPanel(), TagsPanel()],
        right_panels=[CustomFieldsPanel(), CommentsPanel()],
        bottom_panels=[
            ObjectsTablePanel(
                "netbox_access_relations.systemaddress",
                filters={"system_id": lambda context: context["object"].source_system_id},
                exclude_columns=["system"],
                title=_("Source system IPAM information"),
            ),
            ObjectsTablePanel(
                "netbox_access_relations.systemaddress",
                filters={"system_id": lambda context: context["object"].target_system_id},
                exclude_columns=["system"],
                title=_("Target system IPAM information"),
            ),
            ObjectsTablePanel(
                "netbox_access_relations.policyservice",
                filters={"policy_id": lambda context: context["object"].pk},
                exclude_columns=["policy"],
                title=_("Policy services"),
            ),
        ],
    )


@register_model_view(AccessPolicy, "add", detail=False)
@register_model_view(AccessPolicy, "edit")
class AccessPolicyEditView(generic.ObjectEditView):
    queryset = AccessPolicy.objects.select_related("source_system", "target_system")
    form = forms.AccessPolicyForm
    template_name = "netbox_access_relations/accesspolicy_edit.html"

    def post(self, request, *args, **kwargs):
        """Return save failures to the populated form instead of an unhelpful 500 page."""
        try:
            return super().post(request, *args, **kwargs)
        except Exception:
            logging.getLogger(__name__).exception("Failed to save access policy")
            obj = self.alter_object(self.get_object(**kwargs), request, args, kwargs)
            form = self.form(data=request.POST, files=request.FILES, instance=obj)
            restrict_form_fields(form, request.user)
            form.is_valid()
            form.add_error(None, _("The access policy could not be saved. Please correct any errors and try again."))
            return render(request, self.template_name, {
                "model": self.queryset.model,
                "object": obj,
                "form": form,
                "return_url": self.get_return_url(request, obj),
                **self.get_extra_context(request, obj),
            })


@register_model_view(AccessPolicy, "delete")
class AccessPolicyDeleteView(generic.ObjectDeleteView):
    queryset = AccessPolicy.objects.all()


@register_model_view(PolicyService, "list", path="", detail=False)
class PolicyServiceListView(ExcelCompatibleCsvExportMixin, generic.ObjectListView):
    queryset = PolicyService.objects.select_related("policy", "policy__source_system", "policy__target_system")
    template_name = "netbox_access_relations/service_query.html"
    filterset = filtersets.PolicyServiceFilterSet
    filterset_form = forms.PolicyServiceFilterForm
    table = tables.PolicyServiceTable
    actions = (BulkExport,)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).restrict(request.user, "view")
        visible_policies = AccessPolicy.objects.restrict(request.user, "view").values("pk")
        return queryset.filter(policy_id__in=visible_policies)



@register_model_view(PolicyService)
class PolicyServiceView(generic.ObjectView):
    queryset = PolicyService.objects.select_related("policy")
    template_name = "generic/object.html"
    layout = layout.SimpleLayout(left_panels=[PolicyServicePanel(), TagsPanel()], right_panels=[CustomFieldsPanel()])


@register_model_view(PolicyService, "add", detail=False)
@register_model_view(PolicyService, "edit")
class PolicyServiceEditView(generic.ObjectEditView):
    queryset = PolicyService.objects.select_related("policy")
    form = forms.PolicyServiceForm


@register_model_view(PolicyService, "delete")
class PolicyServiceDeleteView(generic.ObjectDeleteView):
    queryset = PolicyService.objects.select_related("policy")
