"""安全区域解析服务：将 NetBox IPAM 对象映射到区域矩阵的存储桶（bucket）。

核心概念：
- 安全区域通过 Prefix 对象的自定义字段 ``security_zone`` 标记。
- 一个 IP 地址或网段的安全区域由"覆盖它的、最具体的、设置了安全区域的 Prefix"决定。
- 解析结果分为四种状态：resolved（已解析）、unset（覆盖 Prefix 未设置区域）、
  unmatched（无覆盖 Prefix）、ambiguous（存在歧义）。
"""

from dataclasses import dataclass
from itertools import product

import netaddr
from django.utils import timezone
from ipam.models import Prefix


# Prefix 自定义字段中用于标记安全区域的字段名
ZONE_FIELD = "security_zone"
# 区域解析规则的版本号，用于在证据中标识使用的规则版本
RULE_VERSION = "zone-prefix-v1"
# 非 resolved 状态的中文标签
STATE_LABELS = {
    "unset": "未设置",
    "unmatched": "未匹配",
    "ambiguous": "歧义",
}


@dataclass(frozen=True, order=True)
class ZoneBucket:
    """区域矩阵中的一个存储桶。

    key 的格式：
    - 已解析：``zone:<区域名>``
    - 未解析：``state:<状态>``
    """

    key: str       # 唯一标识，用于矩阵行列匹配
    label: str     # 人类可读的标签
    state: str     # 状态：resolved / unset / unmatched / ambiguous


@dataclass(frozen=True)
class ZoneEvidence:
    """一次区域解析的完整证据，用于向用户展示解析依据。"""

    bucket: ZoneBucket              # 解析结果所属的存储桶
    matched_prefix: object | None   # 实际匹配到的 Prefix 对象（如有）
    reason: str                     # 解析原因的中文说明
    matched_at: object              # 解析时间（timezone.now()）
    rule_version: str = RULE_VERSION  # 使用的规则版本


def _bucket(state, value=""):
    """根据状态和可选区域值构造 ZoneBucket。

    resolved 状态需要提供区域值；其他状态使用预定义的中文标签。
    """
    if state == "resolved":
        value = str(value).strip()
        return ZoneBucket(f"zone:{value}", value, state)
    return ZoneBucket(f"state:{state}", STATE_LABELS[state], state)


def _prefixes_for_point(address, vrf_id):
    """查询指定 VRF 中包含给定 IP 地址的所有 Prefix。

    使用 ``net_contains_or_equals`` 确保精确匹配（包括地址本身就是 Prefix 的情况）。
    只取需要的字段以减少数据库开销。
    """
    return list(
        Prefix.objects.filter(vrf_id=vrf_id, prefix__net_contains_or_equals=str(address))
        .only("id", "prefix", "custom_field_data")
    )


def _resolve_point(address, vrf_id):
    """解析单个 IP 地址点的区域（只返回 bucket，不含证据）。"""
    return _resolve_point_evidence(address, vrf_id).bucket


def _from_candidates(candidates, *, no_zone_state="unset"):
    """从候选 Prefix 列表中选出最具体的、设置了安全区域的 Prefix。

    选择规则：
    1. 过滤出设置了 ``security_zone`` 自定义字段的候选。
    2. 在这些候选中取前缀长度最大（最具体）的。
    3. 如果最具体的候选有多个且区域值不一致 → 歧义。
    4. 如果没有候选 → unmatched；如果有候选但都没设置区域 → no_zone_state（默认 unset）。

    返回 (ZoneBucket, matched_prefix)。
    """
    if not candidates:
        return _bucket("unmatched"), None
    # 过滤出设置了安全区域自定义字段的 Prefix
    zoned = [p for p in candidates if str(p.custom_field_data.get(ZONE_FIELD, "")).strip()]
    if not zoned:
        return _bucket(no_zone_state), None
    # 取最具体的（前缀长度最大的）
    most_specific = max(p.prefix.prefixlen for p in zoned)
    winners = [p for p in zoned if p.prefix.prefixlen == most_specific]
    # 检查最具体的候选是否有一致的区域值
    values = {str(p.custom_field_data[ZONE_FIELD]).strip() for p in winners}
    if len(values) != 1:
        return _bucket("ambiguous"), None
    # pk 最小的作为"代表" Prefix（用于展示和跳转）
    return _bucket("resolved", values.pop()), min(winners, key=lambda item: item.pk)


def _resolve_point_evidence(address, vrf_id):
    """解析单个 IP 地址点的区域并返回完整证据。"""
    bucket, prefix = _from_candidates(_prefixes_for_point(address, vrf_id))
    return _evidence(bucket, prefix)


def _resolve_prefix(obj):
    """解析 Prefix 类型地址对象的区域（只返回 bucket）。"""
    return _resolve_prefix_evidence(obj).bucket


def _resolve_prefix_evidence(obj):
    """解析 Prefix 类型地址对象的区域并返回完整证据。

    与单点地址不同，Prefix 对象自身可能直接设置了安全区域字段。
    解析顺序：
    1. Prefix 自身直接设置了区域 → 直接使用。
    2. 否则查找覆盖该 Prefix 的祖先 Prefix，取最近的、设置了区域的。
    3. 没有祖先 → unset。
    """
    # 优先使用 Prefix 自身的安全区域设置
    direct = str(obj.custom_field_data.get(ZONE_FIELD, "")).strip()
    if direct:
        return _evidence(_bucket("resolved", direct), obj)
    # 否则查找覆盖当前 Prefix 的所有候选 Prefix
    network = netaddr.IPNetwork(obj.prefix)
    candidates = list(
        Prefix.objects.filter(
            vrf_id=obj.vrf_id,
            prefix__net_contains_or_equals=str(obj.prefix),
        ).only("id", "prefix", "custom_field_data")
    )
    # 过滤出真正的"祖先"（排除自身，且前缀更短/更大）并设置了区域的
    ancestors = [
        prefix for prefix in candidates
        if prefix.pk != obj.pk and prefix.prefix.prefixlen < network.prefixlen
        and str(prefix.custom_field_data.get(ZONE_FIELD, "")).strip()
    ]
    if not ancestors:
        return _evidence(_bucket("unset"), None)
    # 取最近的祖先（前缀长度最大的）
    nearest = max(prefix.prefix.prefixlen for prefix in ancestors)
    values = {
        str(prefix.custom_field_data[ZONE_FIELD]).strip()
        for prefix in ancestors if prefix.prefix.prefixlen == nearest
    }
    if len(values) != 1:
        return _evidence(_bucket("ambiguous"), None)
    winners = [prefix for prefix in ancestors if prefix.prefix.prefixlen == nearest]
    return _evidence(_bucket("resolved", values.pop()), min(winners, key=lambda item: item.pk))


def _evidence(bucket, prefix=None):
    """根据 bucket 状态构造 ZoneEvidence，附带中文原因说明。"""
    reasons = {
        "resolved": "已从最具体且完整覆盖的 Prefix 解析",
        "unset": "覆盖 Prefix 未设置安全区域",
        "unmatched": "未找到同 VRF 的覆盖 Prefix",
        "ambiguous": "存在跨区域或同等候选歧义",
    }
    return ZoneEvidence(bucket, prefix, reasons[bucket.state], timezone.now())


def resolve_address_evidence(address):
    """返回 SystemAddress 关联的原生 IPAM 对象的完整区域解析证据。

    支持三种原生对象类型：Prefix、IPAddress、IPRange。
    - Prefix：可能自身设置区域，或从祖先 Prefix 继承。
    - IPAddress：从覆盖它的 Prefix 解析。
    - IPRange：从完整覆盖该范围的 Prefix 解析。
    """
    if address.prefix_id:
        return _resolve_prefix_evidence(address.prefix)
    if address.ip_address_id:
        obj = address.ip_address
        return _resolve_point_evidence(netaddr.IPNetwork(obj.address).ip, obj.vrf_id)

    # IPRange：需要找到完整覆盖 [start, end] 区间的 Prefix
    obj = address.ip_range
    start = netaddr.IPNetwork(obj.start_address).ip
    end = netaddr.IPNetwork(obj.end_address).ip
    candidates = [
        prefix for prefix in Prefix.objects.filter(vrf_id=obj.vrf_id).only("id", "prefix", "custom_field_data")
        if netaddr.IPNetwork(prefix.prefix).first <= int(start)
        and netaddr.IPNetwork(prefix.prefix).last >= int(end)
    ]
    bucket, prefix = _from_candidates(candidates)
    return _evidence(bucket, prefix)


def resolve_address(address):
    """返回 SystemAddress 原生对象对应的单一区域 bucket（不含证据）。"""
    return resolve_address_evidence(address).bucket


def system_zone_buckets(system):
    """返回一个业务系统所有地址关联的区域 bucket 集合。

    如果系统没有任何地址，返回一个 "unmatched" bucket 以保证矩阵有行/列。
    """
    buckets = {resolve_address(address) for address in system.addresses.all()}
    return buckets or {_bucket("unmatched")}


def system_zone_evidence(system):
    """返回业务系统每个地址的解析证据列表，用于详情页展示。"""
    if not system.addresses.all():
        return [(None, _bucket("unmatched"), "业务系统没有关联 IPAM 地址")]
    return [
        (address, evidence.bucket, evidence.reason)
        for address in system.addresses.all()
        for evidence in (resolve_address_evidence(address),)
    ]


def policy_zone_pairs(policy):
    """返回访问关系的所有 (源区域, 目标区域) 组合。

    使用笛卡尔积：源系统的每个区域 × 目标系统的每个区域。
    """
    return set(product(system_zone_buckets(policy.source_system), system_zone_buckets(policy.target_system)))


def policies_matching_zone_pair(queryset, source_key, target_key):
    """从查询集中筛选出匹配指定 (源区域, 目标区域) 对的访问关系。"""
    bucket_cache = {}
    def buckets(system):
        if system.pk not in bucket_cache:
            bucket_cache[system.pk] = system_zone_buckets(system)
        return bucket_cache[system.pk]
    matching = []
    for policy in queryset.iterator(chunk_size=200):
        pairs = product(buckets(policy.source_system), buckets(policy.target_system))
        if any(source.key == source_key and target.key == target_key for source, target in pairs):
            matching.append(policy.pk)
    return queryset.filter(pk__in=matching)
