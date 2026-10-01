"""Web forms for access-relations objects."""

from django import forms
import netaddr
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from ipam.choices import PrefixStatusChoices
from ipam.models import IPAddress, IPRange, Prefix, VRF
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm, PrimaryModelFilterSetForm, PrimaryModelForm
from utilities.exceptions import PermissionsViolation
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from utilities.forms.rendering import FieldSet

from .models import (
    AccessPolicy, AccessPolicyStatusChoices, ActiveStatusChoices, ApplicationSystem,
    PolicyService, SystemAddress, SystemAlias, TransportProtocolChoices,
)
from .services.ipam_writes import (
    NATIVE_FIELDS,
    NATIVE_MODELS,
    OPERATION_CREATE,
    OPERATION_LINK,
    OPERATION_UPDATE,
    TYPE_IP_ADDRESS,
    TYPE_IP_RANGE,
    TYPE_PREFIX,
    apply_native_values,
    write_system_address,
)
from .services.policy_uniqueness import find_duplicate_policies, service_key


class LocalizedStandardFieldsMixin:
    """Give inherited NetBox fields reliable labels in NetBox's Chinese locale."""

    standard_field_labels = {
        "tags": pgettext_lazy("access relations standard field", "Tags"),
        "owner_group": pgettext_lazy("access relations standard field", "Owner group"),
        "owner": pgettext_lazy("access relations standard field", "Owner"),
        "comments": pgettext_lazy("access relations standard field", "Comments"),
        "changelog_message": pgettext_lazy("access relations standard field", "Changelog message"),
        "filter_id": pgettext_lazy("access relations standard field", "Saved Filter"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in self.standard_field_labels.items():
            if name in self.fields:
                self.fields[name].label = label


class ApplicationSystemForm(LocalizedStandardFieldsMixin, PrimaryModelForm):
    fieldsets = (
        FieldSet("name", "status", "description", "tags", name=_("Application system")),
    )

    class Meta:
        model = ApplicationSystem
        fields = ("name", "status", "description", "owner", "comments", "tags")


class ApplicationSystemFilterForm(LocalizedStandardFieldsMixin, PrimaryModelFilterSetForm):
    model = ApplicationSystem
    fieldsets = (
        FieldSet("q", "filter_id", "status", "is_co_located", name=_("Application system")),
        FieldSet("owner_group_id", "owner_id", name=_("Ownership")),
    )
    status = forms.MultipleChoiceField(
        choices=ActiveStatusChoices,
        required=False,
        label=_("Status"),
    )
    is_co_located = forms.NullBooleanField(
        required=False,
        label=_("Co-located"),
    )


class PolicyServiceInlineForm(LocalizedStandardFieldsMixin, NetBoxModelForm):
    protocol = forms.ChoiceField(choices=TransportProtocolChoices, required=False, label=_('Protocol'))
    is_any = forms.BooleanField(
        required=False,
        label="全协议 ANY",
        help_text="覆盖所有 TCP 和 UDP 端口。",
    )

    class Meta:
        model = PolicyService
        fields = ("is_any", "protocol", "port_start", "port_end")

    def clean(self):
        cleaned = super().clean() or self.cleaned_data
        if cleaned.get("is_any"):
            cleaned["protocol"] = TransportProtocolChoices.TCP
        elif not cleaned.get("protocol"):
            self.add_error("protocol", _("Protocol is required unless the service is ANY."))
        return cleaned


class BasePolicyServiceInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        if not active_forms:
            raise ValidationError(_("An access policy requires at least one service."))

        seen = set()
        for form in active_forms:
            protocol = form.cleaned_data.get("protocol")
            is_any = form.cleaned_data.get("is_any", False)
            key = (
                None if is_any else protocol,
                is_any,
                None if is_any else form.cleaned_data.get("port_start"),
                None if is_any else form.cleaned_data.get("port_end"),
            )
            if key in seen:
                raise ValidationError(_("Duplicate services are not allowed within an access policy."))
            seen.add(key)


PolicyServiceInlineFormSet = inlineformset_factory(
    AccessPolicy,
    PolicyService,
    form=PolicyServiceInlineForm,
    formset=BasePolicyServiceInlineFormSet,
    extra=1,
    can_delete=True,
)


class AccessPolicyForm(LocalizedStandardFieldsMixin, PrimaryModelForm):
    source_system = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), label=_("Source system"))
    target_system = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), label=_("Target system"))
    fieldsets = (
        FieldSet("name", "category", name=_("Access policy")),
        FieldSet("source_system", "target_system", name=_("Endpoints")),
        FieldSet("valid_from", "valid_until", name=_("Validity")),
        FieldSet("description", "tags", name=_("Details")),
    )

    class Meta:
        model = AccessPolicy
        fields = (
            "name", "category", "source_system", "target_system", "valid_from", "valid_until",
            "description", "owner", "comments", "tags",
        )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.service_formset = PolicyServiceInlineFormSet(
            data=self.data if self.is_bound else None,
            files=self.files if self.is_bound else None,
            instance=self.instance,
            prefix="services",
        )

    def clean(self):
        # NetBox's PrimaryModelForm.clean() validates in place and may return
        # None. Django still exposes the populated values on cleaned_data.
        cleaned = super().clean() or self.cleaned_data
        source = cleaned.get("source_system")
        target = cleaned.get("target_system")
        # Only check once endpoints are resolved and the service formset is valid.
        if source and target and source != target and self.service_formset.is_valid():
            service_keys = self._collect_service_keys()
            if service_keys:
                duplicates = find_duplicate_policies(
                    source.pk,
                    target.pk,
                    service_keys,
                    exclude_policy_id=self.instance.pk,
                    user=self.user,
                )
                if duplicates:
                    names = "、".join(policy.name for policy in duplicates)
                    self.add_error(
                        None,
                        _(f"已存在源系统、目标系统与服务项完全相同的访问关系：{names}。"),
                    )
        return cleaned

    def _collect_service_keys(self):
        keys = set()
        for form in self.service_formset.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            data = form.cleaned_data
            keys.add(service_key(
                data.get("protocol"),
                data.get("is_any", False),
                data.get("port_start"),
                data.get("port_end"),
            ))
        return frozenset(keys)

    def is_valid(self):
        # Evaluate both sides so users see all parent and service errors in one response.
        return super().is_valid() & self.service_formset.is_valid()

    def save(self, commit=True):
        if not commit:
            raise ValueError("AccessPolicyForm requires commit=True")
        policy = super().save(commit=True)
        self.service_formset.instance = policy
        self.service_formset.save()
        return policy


class AccessPolicyFilterForm(LocalizedStandardFieldsMixin, PrimaryModelFilterSetForm):
    model = AccessPolicy
    fieldsets = (
        FieldSet("q", "filter_id", "category", "source_system_id", "target_system_id", "system_id", "ip", name=_("Access policy")),
        FieldSet("source_zone", "target_zone", "zone", name=_("Security zones")),
        FieldSet("protocol", "port", "port_start", "port_end", "effective_status", name=_("Service and status")),
    )
    category = forms.CharField(required=False, label=_("Category"))
    source_system_id = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), required=False, label=_("Source system"))
    target_system_id = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), required=False, label=_("Target system"))
    system_id = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), required=False, label=_("Either system"))
    protocol = forms.MultipleChoiceField(choices=TransportProtocolChoices, required=False, label=_("Protocol"))
    port = forms.IntegerField(min_value=1, max_value=65535, required=False, label=_("Port"))
    port_start = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围起点")
    port_end = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围终点")
    effective_status = forms.MultipleChoiceField(choices=AccessPolicyStatusChoices, required=False, label=_("Effective status"))
    ip = forms.CharField(required=False, label="IP 或网段")
    source_zone = forms.CharField(required=False, label="源区域")
    target_zone = forms.CharField(required=False, label="目标区域")
    zone = forms.CharField(required=False, label="任一区域")

    def clean_ip(self):
        value = self.cleaned_data.get("ip", "").strip()
        if value:
            try:
                netaddr.IPNetwork(value)
            except (netaddr.AddrFormatError, ValueError) as exc:
                raise ValidationError("请输入有效的单个 IP 或 CIDR 网段。") from exc
        return value

    def clean(self):
        cleaned = super().clean()
        start, end, port = cleaned.get("port_start"), cleaned.get("port_end"), cleaned.get("port")
        if (start is None) != (end is None):
            raise ValidationError("端口范围必须同时填写起点和终点。")
        if start is not None and start > end:
            raise ValidationError("端口范围起点不得大于终点。")
        if port is not None and start is not None:
            raise ValidationError("单端口和端口范围只能选择一种。")
        return cleaned


class ZoneMatrixFilterForm(forms.Form):
    system_id = DynamicModelChoiceField(queryset=ApplicationSystem.objects.all(), required=False, label=_("Either system"))
    protocol = forms.MultipleChoiceField(choices=TransportProtocolChoices, required=False, label=_("Protocol"))
    port = forms.IntegerField(min_value=1, max_value=65535, required=False, label=_("Port"))
    port_start = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围起点")
    port_end = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围终点")
    effective_status = forms.MultipleChoiceField(choices=AccessPolicyStatusChoices, required=False, label=_("Effective status"))

    def clean(self):
        cleaned = super().clean()
        start, end, port = cleaned.get("port_start"), cleaned.get("port_end"), cleaned.get("port")
        if (start is None) != (end is None):
            raise ValidationError("端口范围必须同时填写起点和终点。")
        if start is not None and start > end:
            raise ValidationError("端口范围起点不得大于终点。")
        if port is not None and start is not None:
            raise ValidationError("单端口和端口范围只能选择一种。")
        return cleaned


class PolicyServiceForm(LocalizedStandardFieldsMixin, NetBoxModelForm):
    policy = DynamicModelChoiceField(queryset=AccessPolicy.objects.all(), label=_("Access policy"))
    fieldsets = (FieldSet("policy", "protocol", "is_any", "port_start", "port_end", "tags", name=_("Policy service")),)

    class Meta:
        model = PolicyService
        fields = ("policy", "protocol", "is_any", "port_start", "port_end", "tags")


class PolicyServiceFilterForm(LocalizedStandardFieldsMixin, NetBoxModelFilterSetForm):
    model = PolicyService
    fieldsets = (
        FieldSet("q", "filter_id", name=_("Policy service")),
        FieldSet("policy_id", "source_system_id", "target_system_id", "system_id", name=_("Access policy")),
        FieldSet("protocol", "is_any", "port", "port_start", "port_end", "effective_status", name=_("Service and status")),
    )
    policy_id = DynamicModelMultipleChoiceField(
        queryset=AccessPolicy.objects.all(),
        required=False,
        label=_("Access policy"),
    )
    protocol = forms.MultipleChoiceField(
        choices=TransportProtocolChoices,
        required=False,
        label=_("Protocol"),
    )
    is_any = forms.NullBooleanField(required=False, label=_("Any port"))
    port = forms.IntegerField(min_value=1, max_value=65535, required=False, label=_("Port"))
    port_start = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围起点")
    port_end = forms.IntegerField(min_value=1, max_value=65535, required=False, label="端口范围终点")
    source_system_id = DynamicModelMultipleChoiceField(
        queryset=ApplicationSystem.objects.all(), required=False, label=_("Source system")
    )
    target_system_id = DynamicModelMultipleChoiceField(
        queryset=ApplicationSystem.objects.all(), required=False, label=_("Target system")
    )
    system_id = DynamicModelMultipleChoiceField(
        queryset=ApplicationSystem.objects.all(), required=False, label=_("Either system")
    )
    effective_status = forms.MultipleChoiceField(
        choices=AccessPolicyStatusChoices, required=False, label=_("Effective status")
    )

    def clean(self):
        cleaned = super().clean()
        start, end, port = cleaned.get("port_start"), cleaned.get("port_end"), cleaned.get("port")
        if (start is None) != (end is None):
            raise ValidationError("端口范围必须同时填写起点和终点。")
        if start is not None and start > end:
            raise ValidationError("端口范围起点不得大于终点。")
        if port is not None and start is not None:
            raise ValidationError("单端口和端口范围只能选择一种。")
        return cleaned


class SystemAliasForm(LocalizedStandardFieldsMixin, NetBoxModelForm):
    system = DynamicModelChoiceField(
        queryset=ApplicationSystem.objects.all(),
        label=_("Application system"),
    )
    fieldsets = (FieldSet("system", "name", "tags", name=_("System alias")),)

    class Meta:
        model = SystemAlias
        fields = ("system", "name", "tags")


class SystemAliasFilterForm(LocalizedStandardFieldsMixin, NetBoxModelFilterSetForm):
    model = SystemAlias
    fieldsets = (
        FieldSet("q", "filter_id", "system_id", "name", name=_("System alias")),
    )
    system_id = DynamicModelMultipleChoiceField(
        queryset=ApplicationSystem.objects.all(),
        required=False,
        label=_("Application system"),
    )
    name = forms.CharField(required=False, label=_("Alias"))


class SystemAddressForm(LocalizedStandardFieldsMixin, NetBoxModelForm):
    """Link an existing IPAM object, or create/update one atomically."""

    OPERATION_LINK = OPERATION_LINK
    OPERATION_CREATE = OPERATION_CREATE
    OPERATION_UPDATE = OPERATION_UPDATE
    TYPE_PREFIX = TYPE_PREFIX
    TYPE_IP_ADDRESS = TYPE_IP_ADDRESS
    TYPE_IP_RANGE = TYPE_IP_RANGE

    native_operation = forms.ChoiceField(
        choices=(
            (OPERATION_LINK, _("Link an existing IPAM object")),
            (OPERATION_CREATE, _("Create a new IPAM object")),
            (OPERATION_UPDATE, _("Update the currently linked IPAM object")),
        ),
        label=_("Operation"),
    )
    native_type = forms.ChoiceField(
        choices=(
            (TYPE_PREFIX, _("Prefix")),
            (TYPE_IP_ADDRESS, _("IP address")),
            (TYPE_IP_RANGE, _("IP range")),
        ),
        label=_("IPAM object type"),
    )

    system = DynamicModelChoiceField(
        queryset=ApplicationSystem.objects.all(),
        label=_("Application system"),
    )
    prefix = DynamicModelChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        label=_("Prefix"),
    )
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        required=False,
        label=_("IP address"),
    )
    ip_range = DynamicModelChoiceField(
        queryset=IPRange.objects.all(),
        required=False,
        label=_("IP range"),
    )
    native_prefix = forms.CharField(required=False, label=_("Prefix value"))
    native_ip_address = forms.CharField(required=False, label=_("IP address value"))
    native_range_start = forms.CharField(required=False, label=_("Range start"))
    native_range_end = forms.CharField(required=False, label=_("Range end"))
    native_vrf = DynamicModelChoiceField(queryset=VRF.objects.all(), required=False, label=_("VRF"))
    native_status = forms.ChoiceField(
        choices=PrefixStatusChoices,
        initial=PrefixStatusChoices.STATUS_ACTIVE,
        required=False,
        label=_("Status"),
    )
    native_description = forms.CharField(required=False, label=_("Description"))

    fieldsets = (
        FieldSet("system", name=_("Application system")),
        FieldSet("native_operation", "native_type", name=_("IPAM operation")),
        FieldSet("prefix", "ip_address", "ip_range", name=_("Existing IPAM object")),
        FieldSet(
            "native_prefix",
            "native_ip_address",
            "native_range_start",
            "native_range_end",
            "native_vrf",
            "native_status",
            "native_description",
            name=_("Create or update IPAM object"),
        ),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SystemAddress
        fields = ("system", "prefix", "ip_address", "ip_range", "tags")

    native_models = NATIVE_MODELS
    native_fields = NATIVE_FIELDS

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            for native_type, field_name in self.native_fields.items():
                self.fields[field_name].queryset = self.native_models[native_type].objects.restrict(user, "view")
        native = self.instance.address_object if self.instance.pk else None
        native_type = self.instance.address_type_field if native else self.TYPE_PREFIX
        if native:
            self.fields["native_operation"].choices = (
                (OPERATION_UPDATE, _("Update the currently linked IPAM object")),
                (OPERATION_LINK, _("Replace with an existing IPAM object")),
            )
            self.fields["native_operation"].initial = self.OPERATION_UPDATE
        else:
            self.fields["native_operation"].choices = (
                (OPERATION_LINK, _("Link an existing IPAM object")),
                (OPERATION_CREATE, _("Create a new IPAM object")),
            )
            self.fields["native_operation"].initial = self.OPERATION_LINK
        self.fields["native_type"].initial = native_type
        if native:
            self.initial.update(self._native_initial(native_type, native))

    @staticmethod
    def _native_initial(native_type, native):
        initial = {
            "native_vrf": native.vrf_id,
            "native_status": native.status,
            "native_description": native.description,
        }
        if native_type == SystemAddressForm.TYPE_PREFIX:
            initial["native_prefix"] = native.prefix
        elif native_type == SystemAddressForm.TYPE_IP_ADDRESS:
            initial["native_ip_address"] = native.address
        else:
            initial["native_range_start"] = native.start_address
            initial["native_range_end"] = native.end_address
        return initial

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        operation = cleaned.get("native_operation")
        native_type = cleaned.get("native_type")
        if operation == self.OPERATION_LINK:
            selected = {name: cleaned.get(name) for name in self.native_fields.values()}
            if sum(value is not None for value in selected.values()) != 1:
                raise ValidationError(_("Select exactly one existing Prefix, IP address, or IP range."))
            selected_type = next(name for name, value in selected.items() if value is not None)
            if native_type != selected_type:
                self.add_error("native_type", _("Object type does not match the selected IPAM object."))
            return cleaned

        if operation == self.OPERATION_UPDATE:
            if not self.instance.pk:
                self.add_error("native_operation", _("There is no linked IPAM object to update."))
                return cleaned
            if native_type != self.instance.address_type_field:
                self.add_error("native_type", _("Change the association instead of changing an object's type."))
                return cleaned
            native = self.instance.address_object
            self._native_object = native
            if not native.__class__.objects.restrict(self.user, "change").filter(pk=native.pk).exists():
                self.add_error("native_operation", _("You do not have permission to modify this IPAM object."))

        if operation == self.OPERATION_CREATE:
            model = self.native_models.get(native_type)
            if model is not None and not self.user.has_perm(f"ipam.add_{model._meta.model_name}"):
                self.add_error("native_operation", _("You do not have permission to create this IPAM object type."))

        self._validate_native_values(cleaned, native_type)
        self.instance._defer_native_target_validation = True
        return cleaned

    def _validate_native_values(self, cleaned, native_type):
        required = {
            self.TYPE_PREFIX: ("native_prefix",),
            self.TYPE_IP_ADDRESS: ("native_ip_address",),
            self.TYPE_IP_RANGE: ("native_range_start", "native_range_end"),
        }.get(native_type, ())
        for field_name in required:
            if not cleaned.get(field_name):
                self.add_error(field_name, _("This field is required."))
        if any(field_name not in cleaned for field_name in required):
            return

        native = (
            self.native_models[native_type].objects.get(pk=self._native_object.pk)
            if getattr(self, "_native_object", None) is not None
            else self.native_models[native_type]()
        )
        self._apply_native_values(native, cleaned, native_type)
        try:
            native.full_clean()
        except ValidationError as exc:
            self.add_error(None, ValidationError(exc.messages))

    @staticmethod
    def _apply_native_values(native, cleaned, native_type):
        apply_native_values(native, cleaned, native_type)

    def save(self, commit=True):
        if not commit:
            raise ValueError("SystemAddressForm requires commit=True")
        operation = self.cleaned_data["native_operation"]
        native_type = self.cleaned_data["native_type"]
        try:
            address = super().save(commit=False)
            return write_system_address(
                address,
                operation=operation,
                native_type=native_type,
                native_values=self.cleaned_data,
                user=self.user,
                save_related=self._save_m2m,
            )
        finally:
            self.instance._defer_native_target_validation = False


class BaseSystemAddressInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        kwargs["form_kwargs"] = {**kwargs.get("form_kwargs", {}), "user": user}
        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].label = _("Unlink this address")

    def clean(self):
        super().clean()
        if any(self.errors) or self.user is None:
            return
        for form in self.forms:
            if not form.cleaned_data or not form.has_changed():
                continue
            address = form.instance
            if form.cleaned_data.get("DELETE"):
                can_delete = (
                    address.pk
                    and SystemAddress.objects.restrict(self.user, "delete").filter(pk=address.pk).exists()
                )
                if not can_delete:
                    raise ValidationError(_("You do not have permission to unlink one or more addresses."))
            elif address.pk:
                if not SystemAddress.objects.restrict(self.user, "change").filter(pk=address.pk).exists():
                    raise ValidationError(_("You do not have permission to modify one or more address links."))
            elif not self.user.has_perm("netbox_access_relations.add_systemaddress"):
                raise ValidationError(_("You do not have permission to add address links."))

    def save(self, commit=True):
        addresses = super().save(commit=commit)
        if commit:
            for address in self.new_objects:
                if not SystemAddress.objects.restrict(self.user, "add").filter(pk=address.pk).exists():
                    raise PermissionsViolation(_("You do not have permission to add this address link."))
        return addresses


SystemAddressInlineFormSet = inlineformset_factory(
    ApplicationSystem,
    SystemAddress,
    form=SystemAddressForm,
    formset=BaseSystemAddressInlineFormSet,
    extra=1,
    can_delete=True,
)


class ApplicationSystemWithAddressesForm(ApplicationSystemForm):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.can_manage_addresses = bool(
            user and user.has_perm("netbox_access_relations.view_systemaddress")
        )
        self.address_formset = None
        if self.can_manage_addresses:
            self.address_formset = SystemAddressInlineFormSet(
                data=self.data if self.is_bound else None,
                files=self.files if self.is_bound else None,
                instance=self.instance,
                prefix="addresses",
                user=user,
            )

    def is_valid(self):
        parent_valid = super().is_valid()
        if self.address_formset is None:
            return parent_valid
        return parent_valid & self.address_formset.is_valid()

    def save(self, commit=True):
        if not commit:
            raise ValueError("ApplicationSystemWithAddressesForm requires commit=True")
        system = super().save(commit=True)
        if self.address_formset is not None:
            self.address_formset.instance = system
            self.address_formset.save()
        return system
