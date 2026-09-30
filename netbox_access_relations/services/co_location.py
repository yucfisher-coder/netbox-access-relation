"""共置标记维护服务：事务性地维护 ``ApplicationSystem.is_co_located`` 派生字段。

当两个或更多业务系统共享同一个原生 IPAM 对象（Prefix / IPAddress / IPRange）时，
这些系统被标记为"共置"（co-located）。该标记是派生数据，由本服务在地址变更时
自动计算，不允许用户手动编辑。
"""

from dataclasses import dataclass

from django.db.models import Count, Q, Subquery


# SystemAddress 模型中关联原生 IPAM 对象的三个外键字段名
TARGET_FIELDS = ("ip_address", "ip_range", "prefix")


@dataclass(frozen=True, order=True)
class AddressTarget:
    """表示一个 SystemAddress 所引用的具体原生 IPAM 行。

    field_name 是外键字段名（如 "prefix"），object_id 是被引用对象的主键。
    """

    field_name: str
    object_id: int


@dataclass(frozen=True)
class AddressChange:
    """记录一次地址变更可能影响的系统和原生目标。

    system_ids：可能需要重新计算共置标记的业务系统 ID 集合。
    targets：本次变更涉及的原生 IPAM 目标集合（用于加锁和查找关联系统）。
    """

    system_ids: frozenset[int]
    targets: frozenset[AddressTarget]


def _target_for(address):
    """从 SystemAddress 实例中提取其引用的原生 IPAM 目标。

    由于模型约束保证恰好一个目标非空，返回第一个（也是唯一一个）非空目标。
    """
    targets = [
        AddressTarget(field_name, getattr(address, f"{field_name}_id"))
        for field_name in TARGET_FIELDS
        if getattr(address, f"{field_name}_id") is not None
    ]
    return targets[0] if len(targets) == 1 else None


def _target_filter(targets):
    """构造一个 Q 对象，匹配引用了给定 targets 中任一原生目标的 SystemAddress。"""
    condition = Q(pk__in=[])
    for target in targets:
        condition |= Q(**{f"{target.field_name}_id": target.object_id})
    return condition


def _lock_targets(targets, *, using, system_address_model):
    """对涉及的原生 IPAM 行加行锁（SELECT FOR UPDATE），序列化并发变更。

    这防止两个并发事务同时修改共享同一原生对象的地址时产生竞态。
    按 field_name + object_id 排序确保加锁顺序一致，避免死锁。
    """
    for target in sorted(targets):
        field = system_address_model._meta.get_field(target.field_name)
        native_model = field.remote_field.model
        tuple(
            native_model.objects.using(using)
            .select_for_update()
            .filter(pk=target.object_id)
            .values_list("pk", flat=True)
        )


def prepare_address_change(address, *, using):
    """在保存 SystemAddress 之前，锁定并收集所有可能受影响的业务系统。

    执行步骤：
    1. 读取变更前的旧记录（如有）。
    2. 收集旧值和新值涉及的所有原生 IPAM 目标。
    3. 对这些原生目标加行锁。
    4. 收集所有引用了这些目标的系统 ID（加上当前系统本身）。
    5. 对所有受影响的系统行加锁（按 pk 排序避免死锁）。
    6. 返回 AddressChange 供后续 recalculate_co_location 使用。
    """
    from ..models import ApplicationSystem, SystemAddress

    previous = None
    if address.pk is not None:
        previous = (
            SystemAddress.objects.using(using)
            .select_for_update()
            .filter(pk=address.pk)
            .only("system_id", *(f"{field_name}_id" for field_name in TARGET_FIELDS))
            .first()
        )

    # 收集旧值和新值涉及的所有原生目标
    targets = {target for item in (previous, address) if item for target in [_target_for(item)] if target}
    _lock_targets(targets, using=using, system_address_model=SystemAddress)

    # 收集所有可能受影响的系统：旧系统、新系统、以及引用了相同原生目标的其他系统
    system_ids = {item.system_id for item in (previous, address) if item and item.system_id is not None}
    if targets:
        system_ids.update(
            SystemAddress.objects.using(using)
            .filter(_target_filter(targets))
            .values_list("system_id", flat=True)
        )

    # 对所有受影响的系统行加锁，按 pk 排序确保一致的加锁顺序
    tuple(
        ApplicationSystem.objects.using(using)
        .select_for_update()
        .filter(pk__in=system_ids)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    return AddressChange(frozenset(system_ids), frozenset(targets))


def prepare_address_deletion(address, *, using):
    """在删除 SystemAddress 之前，锁定并收集所有可能受影响的业务系统。

    与 prepare_address_change 类似，但只处理删除场景：旧值存在，新值不存在。
    """
    from ..models import ApplicationSystem, SystemAddress

    # 锁定即将被删除的 SystemAddress 行
    tuple(
        SystemAddress.objects.using(using)
        .select_for_update()
        .filter(pk=address.pk)
        .values_list("pk", flat=True)
    )

    target = _target_for(address)
    targets = {target} if target else set()
    _lock_targets(targets, using=using, system_address_model=SystemAddress)

    system_ids = {address.system_id} if address.system_id is not None else set()
    if targets:
        system_ids.update(
            SystemAddress.objects.using(using)
            .filter(_target_filter(targets))
            .values_list("system_id", flat=True)
        )

    tuple(
        ApplicationSystem.objects.using(using)
        .select_for_update()
        .filter(pk__in=system_ids)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    return AddressChange(frozenset(system_ids), frozenset(targets))


def recalculate_co_location(system_ids, *, using):
    """重新计算指定系统集合的 ``is_co_located`` 标记。

    判定规则：如果同一个原生 IPAM 对象（Prefix/IPAddress/IPRange）被两个或更多
    不同的业务系统引用，则所有这些系统都被标记为共置。

    实现方式：
    1. 先将所有目标系统的标记重置为 False。
    2. 对每种原生对象类型，找出被多个系统共享的对象 ID。
    3. 将引用了这些共享对象的系统标记为 True。
    """
    from ..models import ApplicationSystem, SystemAddress

    system_ids = frozenset(system_ids)
    if not system_ids:
        return

    co_located_system_ids = set()
    for field_name in TARGET_FIELDS:
        field_id = f"{field_name}_id"
        # 子查询：找出被 2 个以上不同系统引用的原生对象 ID
        shared_targets = (
            SystemAddress.objects.using(using)
            .filter(**{f"{field_id}__isnull": False})
            .values(field_id)
            .annotate(system_count=Count("system_id", distinct=True))
            .filter(system_count__gt=1)
            .values(field_id)
        )
        # 在目标系统中，找出引用了上述共享对象的系统
        co_located_system_ids.update(
            SystemAddress.objects.using(using)
            .filter(system_id__in=system_ids, **{f"{field_id}__in": Subquery(shared_targets)})
            .values_list("system_id", flat=True)
        )

    # 先全部重置为 False，再标记共置的为 True（两步原子操作）
    systems = ApplicationSystem.objects.using(using).filter(pk__in=system_ids)
    systems.update(is_co_located=False)
    if co_located_system_ids:
        systems.filter(pk__in=co_located_system_ids).update(is_co_located=True)
