"""核心业务模型：定义访问关系插件的五个数据模型。

模型关系概览：
- ApplicationSystem（业务系统）：核心实体，拥有别名、地址和访问关系。
- SystemAlias（系统别名）：业务系统的替代名称，与系统名共用不区分大小写的唯一命名空间。
- SystemAddress（系统地址）：业务系统到原生 NetBox IPAM 对象（Prefix/IPAddress/IPRange）的关联。
- AccessPolicy（访问关系）：两个业务系统之间有方向、有时效的访问策略。
- PolicyService（策略服务项）：访问关系下的 TCP/UDP 端口或端口范围。

派生字段：
- ApplicationSystem.is_co_located：当系统与其他系统共享同一原生 IPAM 对象时自动标记。
- AccessPolicy.effective_status：根据 valid_from / valid_until 动态计算的生效状态。
"""

from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from netbox.models import NetBoxModel, PrimaryModel


class ActiveStatusChoices(models.TextChoices):
    ACTIVE = "active", pgettext_lazy("application system status", "Active")
    INACTIVE = "inactive", pgettext_lazy("application system status", "Inactive")


class AccessPolicyStatusChoices(models.TextChoices):
    UPCOMING = "upcoming", _("Upcoming")
    ACTIVE = "active", pgettext_lazy("access policy status", "Active")
    EXPIRED = "expired", _("Expired")


class TransportProtocolChoices(models.TextChoices):
    TCP = "tcp", "TCP"
    UDP = "udp", "UDP"


class ApplicationSystem(PrimaryModel):
    """A canonical business system shared by access-policy endpoints."""

    name = models.CharField(_("Name"), max_length=200)
    status = models.CharField(
        _("Status"),
        max_length=16,
        choices=ActiveStatusChoices,
        default=ActiveStatusChoices.ACTIVE,
        db_index=True,
    )
    is_co_located = models.BooleanField(
        _("Co-located"),
        default=False,
        editable=False,
        db_index=True,
        help_text=_("Automatically set when a native address object is shared with another system."),
    )

    class Meta:
        verbose_name = _("Application system")
        verbose_name_plural = _("Application systems")
        ordering = ("name", "pk")
        constraints = (
            models.UniqueConstraint(
                Lower("name"),
                name="accessrel_appsystem_name_ci_unique",
                violation_error_message=_("An application system with this name already exists."),
            ),
        )

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": _("Name cannot be blank.")})
        conflict = SystemAlias.objects.filter(name__iexact=self.name)
        if conflict.exists():
            raise ValidationError({"name": _("This name is already used by a system alias.")})

    def __str__(self):
        return self.name

    def get_status_color(self):
        return {
            ActiveStatusChoices.ACTIVE: "green",
            ActiveStatusChoices.INACTIVE: "red",
        }.get(self.status, "gray")


class SystemAlias(NetBoxModel):
    """A manually confirmed alternative name for an application system."""

    system = models.ForeignKey(
        to=ApplicationSystem,
        verbose_name=_("Application system"),
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    name = models.CharField(_("Alias"), max_length=200)

    class Meta:
        verbose_name = _("System alias")
        verbose_name_plural = _("System aliases")
        ordering = ("name", "pk")
        constraints = (
            models.UniqueConstraint(
                Lower("name"),
                name="accessrel_systemalias_name_ci_unique",
                violation_error_message=_("A system alias with this name already exists."),
            ),
        )

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": _("Alias cannot be blank.")})
        if ApplicationSystem.objects.filter(name__iexact=self.name).exists():
            raise ValidationError({"name": _("This alias is already used as an application system name.")})

    def __str__(self):
        return self.name


class SystemAddress(NetBoxModel):
    """A link from one business system to exactly one native NetBox IPAM object."""

    system = models.ForeignKey(
        to=ApplicationSystem,
        verbose_name=_("Application system"),
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    prefix = models.ForeignKey(
        to="ipam.Prefix",
        verbose_name=_("Prefix"),
        on_delete=models.PROTECT,
        related_name="access_relation_system_addresses",
        blank=True,
        null=True,
    )
    ip_address = models.ForeignKey(
        to="ipam.IPAddress",
        verbose_name=_("IP address"),
        on_delete=models.PROTECT,
        related_name="access_relation_system_addresses",
        blank=True,
        null=True,
    )
    ip_range = models.ForeignKey(
        to="ipam.IPRange",
        verbose_name=_("IP range"),
        on_delete=models.PROTECT,
        related_name="access_relation_system_addresses",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("System address")
        verbose_name_plural = _("System addresses")
        ordering = ("system", "pk")
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(prefix__isnull=False, ip_address__isnull=True, ip_range__isnull=True)
                    | models.Q(prefix__isnull=True, ip_address__isnull=False, ip_range__isnull=True)
                    | models.Q(prefix__isnull=True, ip_address__isnull=True, ip_range__isnull=False)
                ),
                name="accessrel_systemaddress_exactly_one_target",
                violation_error_message=_("Select exactly one Prefix, IP address, or IP range."),
            ),
            models.UniqueConstraint(
                fields=("system", "prefix"),
                condition=models.Q(prefix__isnull=False),
                name="accessrel_systemaddress_system_prefix_unique",
            ),
            models.UniqueConstraint(
                fields=("system", "ip_address"),
                condition=models.Q(ip_address__isnull=False),
                name="accessrel_systemaddress_system_ip_unique",
            ),
            models.UniqueConstraint(
                fields=("system", "ip_range"),
                condition=models.Q(ip_range__isnull=False),
                name="accessrel_systemaddress_system_range_unique",
            ),
        )

    @property
    def address_object(self):
        return self.prefix or self.ip_address or self.ip_range

    @property
    def address_type(self):
        if self.prefix_id is not None:
            return _("Prefix")
        if self.ip_address_id is not None:
            return _("IP address")
        if self.ip_range_id is not None:
            return _("IP range")
        return None

    @property
    def address_type_field(self):
        if self.prefix_id is not None:
            return "prefix"
        if self.ip_address_id is not None:
            return "ip_address"
        if self.ip_range_id is not None:
            return "ip_range"
        return None

    @property
    def vrf(self):
        return getattr(self.address_object, "vrf", None)

    @property
    def zone_evidence(self):
        from .services.zones import resolve_address_evidence
        return resolve_address_evidence(self)

    @property
    def matched_prefix(self):
        return self.zone_evidence.matched_prefix

    @property
    def security_zone(self):
        return self.zone_evidence.bucket.label

    @property
    def resolution_status(self):
        evidence = self.zone_evidence
        return f"{evidence.reason}（{evidence.rule_version}）"

    def clean(self):
        super().clean()
        if getattr(self, "_defer_native_target_validation", False):
            return
        if sum(value is not None for value in (self.prefix_id, self.ip_address_id, self.ip_range_id)) != 1:
            raise ValidationError(_("Select exactly one Prefix, IP address, or IP range."))

    def validate_constraints(self, exclude=None):
        if getattr(self, "_defer_native_target_validation", False):
            return
        return super().validate_constraints(exclude=exclude)

    def save(self, *args, **kwargs):
        """保存关联并在同一事务中重新计算所有受影响系统的共置标记。

        延迟导入避免循环依赖：co_location 服务需要引用本模型，而本模型的 save
        需要调用该服务。
        """
        from .services.co_location import prepare_address_change, recalculate_co_location

        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        kwargs["using"] = using

        with transaction.atomic(using=using):
            # 保存前锁定受影响的行，确保并发安全
            change = prepare_address_change(self, using=using)
            result = super().save(*args, **kwargs)
            # 保存后重新计算共置标记（is_co_located 是派生字段）
            recalculate_co_location(change.system_ids, using=using)

        return result

    def __str__(self):
        return f"{self.system}: {self.address_object}"


class AccessPolicy(PrimaryModel):
    """A directed, time-bound relationship between two application systems."""

    name = models.CharField(_("Name"), max_length=200)
    category = models.CharField(_("Category"), max_length=100, blank=True)
    source_system = models.ForeignKey(
        ApplicationSystem,
        verbose_name=_("Source system"),
        on_delete=models.PROTECT,
        related_name="outbound_access_policies",
    )
    target_system = models.ForeignKey(
        ApplicationSystem,
        verbose_name=_("Target system"),
        on_delete=models.PROTECT,
        related_name="inbound_access_policies",
    )
    valid_from = models.DateTimeField(_("Valid from"), blank=True, null=True)
    valid_until = models.DateTimeField(_("Valid until"), blank=True, null=True)

    class Meta:
        verbose_name = _("Access policy")
        verbose_name_plural = _("Access policies")
        ordering = ("name", "pk")
        constraints = (
            models.UniqueConstraint(
                Lower("name"),
                name="accessrel_accesspolicy_name_ci_unique",
                violation_error_message=_("An access policy with this name already exists."),
            ),
            models.CheckConstraint(
                condition=~models.Q(source_system=models.F("target_system")),
                name="accessrel_accesspolicy_distinct_systems",
                violation_error_message=_("Source and target systems must be different."),
            ),
            models.CheckConstraint(
                condition=(models.Q(valid_from__isnull=True) | models.Q(valid_until__isnull=True)
                           | models.Q(valid_until__gt=models.F("valid_from"))),
                name="accessrel_accesspolicy_valid_period",
                violation_error_message=_("Valid until must be later than valid from."),
            ),
        )

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        self.category = (self.category or "").strip()
        if not self.name:
            raise ValidationError({"name": _("Name cannot be blank.")})
        if self.source_system_id and self.source_system_id == self.target_system_id:
            raise ValidationError({"target_system": _("Source and target systems must be different.")})
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": _("Valid until must be later than valid from.")})

    @property
    def effective_status(self):
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return AccessPolicyStatusChoices.UPCOMING
        if self.valid_until and now >= self.valid_until:
            return AccessPolicyStatusChoices.EXPIRED
        return AccessPolicyStatusChoices.ACTIVE

    @property
    def effective_status_label(self):
        return AccessPolicyStatusChoices(self.effective_status).label

    def get_effective_status_color(self):
        return {
            AccessPolicyStatusChoices.UPCOMING: "blue",
            AccessPolicyStatusChoices.ACTIVE: "green",
            AccessPolicyStatusChoices.EXPIRED: "gray",
        }[self.effective_status]

    def __str__(self):
        return self.name


class PolicyService(NetBoxModel):
    """A TCP or UDP destination-port expression owned by one access policy."""

    policy = models.ForeignKey(
        AccessPolicy,
        verbose_name=_("Access policy"),
        on_delete=models.CASCADE,
        related_name="services",
    )
    protocol = models.CharField(_("Protocol"), max_length=3, choices=TransportProtocolChoices)
    is_any = models.BooleanField(_("Any port"), default=False)
    port_start = models.PositiveSmallIntegerField(_("Port start"), blank=True, null=True)
    port_end = models.PositiveSmallIntegerField(_("Port end"), blank=True, null=True)

    class Meta:
        verbose_name = _("Policy service")
        verbose_name_plural = _("Policy services")
        ordering = ("policy", "protocol", "is_any", "port_start", "port_end", "pk")
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(is_any=True, port_start__isnull=True, port_end__isnull=True)
                    | models.Q(
                        is_any=False,
                        port_start__gte=1,
                        port_end__lte=65535,
                        port_start__lte=models.F("port_end"),
                    )
                ),
                name="accessrel_policyservice_valid_ports",
                violation_error_message=_("Use ANY or a port range between 1 and 65535."),
            ),
            models.UniqueConstraint(
                fields=("policy", "protocol"),
                condition=models.Q(is_any=True),
                name="accessrel_policyservice_unique_any",
            ),
            models.UniqueConstraint(
                fields=("policy", "protocol", "port_start", "port_end"),
                condition=models.Q(is_any=False),
                name="accessrel_policyservice_unique_range",
            ),
        )

    def clean(self):
        super().clean()
        if self.is_any:
            if self.port_start is not None or self.port_end is not None:
                raise ValidationError(_("ANY services must not specify ports."))
        elif self.port_start is None or self.port_end is None:
            raise ValidationError(_("A non-ANY service requires both port values."))
        elif not 1 <= self.port_start <= self.port_end <= 65535:
            raise ValidationError(_("Ports must form a closed range between 1 and 65535."))

    @property
    def port_display(self):
        if self.is_any:
            return _("ANY")
        if self.port_start == self.port_end:
            return str(self.port_start)
        return f"{self.port_start}-{self.port_end}"

    def overlaps(self, other):
        if self.protocol != other.protocol:
            return False
        if self.is_any or other.is_any:
            return True
        return self.port_start <= other.port_end and other.port_start <= self.port_end

    @property
    def overlap_count(self):
        return self.overlap_count_in(PolicyService.objects.all())

    def overlap_count_in(self, queryset):
        """Count overlapping policies within an already permission-scoped queryset."""
        query = queryset.exclude(pk=self.pk).filter(protocol=self.protocol)
        if not self.is_any:
            query = query.filter(
                models.Q(is_any=True)
                | models.Q(port_start__lte=self.port_end, port_end__gte=self.port_start)
            )
        return query.exclude(policy_id=self.policy_id).values("policy_id").distinct().count()

    def __str__(self):
        return f"{self.get_protocol_display().upper()}/{self.port_display}"
