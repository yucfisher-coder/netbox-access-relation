"""原子写入服务：在一个数据库事务中同时操作 SystemAddress 和其关联的原生 IPAM 对象。

支持三种操作：
- LINK：关联一个已存在的原生 IPAM 对象。
- CREATE：创建一个新的原生 IPAM 对象并关联。
- UPDATE：更新已关联的原生 IPAM 对象的属性。

所有操作都在同一个事务中完成，并强制执行 NetBox 对象级权限检查。
"""

from django.core.exceptions import ValidationError
from django.db import router, transaction
from ipam.models import IPAddress, IPRange, Prefix
from utilities.exceptions import PermissionsViolation

from ..models import SystemAddress


# 三种原生对象操作类型
OPERATION_LINK = "link"      # 关联已有对象
OPERATION_CREATE = "create"  # 创建新对象
OPERATION_UPDATE = "update"  # 更新已关联对象

# 三种原生 IPAM 对象类型标识
TYPE_PREFIX = "prefix"
TYPE_IP_ADDRESS = "ip_address"
TYPE_IP_RANGE = "ip_range"

# 类型标识 → Django 模型类 的映射
NATIVE_MODELS = {
    TYPE_PREFIX: Prefix,
    TYPE_IP_ADDRESS: IPAddress,
    TYPE_IP_RANGE: IPRange,
}
# 类型标识 → SystemAddress 上对应外键字段名 的映射
NATIVE_FIELDS = {
    TYPE_PREFIX: "prefix",
    TYPE_IP_ADDRESS: "ip_address",
    TYPE_IP_RANGE: "ip_range",
}


def apply_native_values(native, values, native_type):
    """将表单/API 提交的通用值应用到原生 IPAM 模型实例上。

    三种类型的通用字段：vrf、status、description。
    类型特有字段：
    - prefix → prefix（CIDR 字符串）
    - ip_address → address（带掩码的主机地址）
    - ip_range → start_address, end_address
    """
    native.vrf = values.get("native_vrf")
    native.status = values.get("native_status") or native._meta.get_field("status").default
    native.description = values.get("native_description", "")
    if native_type == TYPE_PREFIX:
        native.prefix = values.get("native_prefix")
    elif native_type == TYPE_IP_ADDRESS:
        native.address = values.get("native_ip_address")
    elif native_type == TYPE_IP_RANGE:
        native.start_address = values.get("native_range_start")
        native.end_address = values.get("native_range_end")
    else:
        raise ValueError(f"Unsupported native IPAM object type: {native_type}")


def write_system_address(
    address,
    *,
    operation,
    native_type,
    native_values,
    user,
    save_related=None,
):
    """在一个事务中持久化 SystemAddress 及其（可选的）原生 IPAM 创建/更新。

    参数：
    - address：待保存的 SystemAddress 实例（可能尚未有 pk）。
    - operation：link / create / update。
    - native_type：prefix / ip_address / ip_range。
    - native_values：原生对象的字段值字典。
    - user：执行操作的用户，用于权限检查。
    - save_related：可选回调，用于在同一事务中保存 tags 等关联数据。

    权限检查策略：
    - CREATE：检查 ipam.add_<model> 权限，并在对象创建后再次用 restrict 确认。
    - UPDATE：检查 ipam.change_<model> 权限（通过 restrict）。
    - LINK：不额外检查 IPAM 权限（SystemAddress 的权限由上层处理）。
    """
    if operation not in {OPERATION_LINK, OPERATION_CREATE, OPERATION_UPDATE}:
        raise ValueError(f"Unsupported IPAM operation: {operation}")
    if native_type not in NATIVE_MODELS:
        raise ValueError(f"Unsupported native IPAM object type: {native_type}")

    using = router.db_for_write(SystemAddress, instance=address)
    with transaction.atomic(using=using):
        if operation == OPERATION_CREATE:
            model = NATIVE_MODELS[native_type]
            # 权限检查 1：用户有创建此类对象的模型级权限
            if not user.has_perm(f"ipam.add_{model._meta.model_name}"):
                raise PermissionsViolation()
            native = model()
            apply_native_values(native, native_values, native_type)
            native.full_clean()
            native.save(using=using)
            # 权限检查 2：对象级权限（restrict），在对象有 pk 后再次确认
            if not model.objects.restrict(user, "add").filter(pk=native.pk).exists():
                raise PermissionsViolation()
            _set_native_target(address, native_type, native)
        elif operation == OPERATION_UPDATE:
            if not address.pk:
                raise ValidationError("The linked IPAM object cannot be updated as this type.")
            # 锁定当前 SystemAddress 行，防止并发修改
            current_address = SystemAddress.objects.select_for_update().get(pk=address.pk)
            if current_address.address_type_field != native_type:
                raise ValidationError("The linked IPAM object cannot be updated as this type.")
            model = NATIVE_MODELS[native_type]
            # 锁定原生对象行
            native = model.objects.select_for_update().get(pk=current_address.address_object.pk)
            # 对象级权限检查
            if not model.objects.restrict(user, "change").filter(pk=native.pk).exists():
                raise PermissionsViolation()
            native.snapshot()  # NetBox 变更日志快照
            apply_native_values(native, native_values, native_type)
            native.full_clean()
            native.save(using=using)
            _set_native_target(address, native_type, native)

        # 恢复延迟验证标记，执行完整校验并保存
        address._defer_native_target_validation = False
        address.full_clean()
        address.save(using=using)
        # 保存关联数据（如 tags），在同一事务内
        if save_related is not None:
            save_related()
        return address


def _set_native_target(address, native_type, native):
    """将原生对象设置到 SystemAddress 的对应外键字段，并清空其他两个外键。

    保证"恰好一个目标"的约束在 Python 层面也成立。
    """
    for field_name in NATIVE_FIELDS.values():
        setattr(address, field_name, native if field_name == native_type else None)
