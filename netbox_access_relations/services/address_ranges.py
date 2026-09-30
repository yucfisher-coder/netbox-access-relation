"""Safe coalescing rules for business addresses."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Literal


IPAddressValue = IPv4Address | IPv6Address
ZoneState = Literal["resolved", "unset", "unmatched", "ambiguous"]
OutputKind = Literal["ipaddress", "iprange"]


@dataclass(frozen=True, slots=True)
class ResolvedAddressInterval:
    """An address interval after NetBox VRF and security-zone resolution."""

    system_key: str
    start: IPAddressValue
    end: IPAddressValue
    vrf_resolved: bool
    vrf_id: int | None
    zone_state: ZoneState
    zone_value: str = ""

    def __post_init__(self) -> None:
        if not self.system_key.strip():
            raise ValueError("system_key must not be blank")
        if self.start.version != self.end.version:
            raise ValueError("address interval cannot mix IPv4 and IPv6")
        if int(self.start) > int(self.end):
            raise ValueError("address interval start must not exceed end")
        if self.zone_state == "resolved" and not self.zone_value.strip():
            raise ValueError("resolved security zone requires a value")
        if self.zone_state != "resolved" and self.zone_value:
            raise ValueError("unresolved security zone must not carry a value")

    @classmethod
    def from_strings(
        cls,
        *,
        system_key: str,
        start: str,
        end: str | None = None,
        vrf_resolved: bool,
        vrf_id: int | None,
        zone_state: ZoneState,
        zone_value: str = "",
    ) -> ResolvedAddressInterval:
        return cls(
            system_key=system_key,
            start=ip_address(start),
            end=ip_address(end or start),
            vrf_resolved=vrf_resolved,
            vrf_id=vrf_id,
            zone_state=zone_state,
            zone_value=zone_value,
        )


@dataclass(frozen=True, slots=True)
class CoalescedBusinessAddress:
    """A normalized native-object target for one business system."""

    system_key: str
    start: IPAddressValue
    end: IPAddressValue
    vrf_resolved: bool
    vrf_id: int | None
    zone_state: ZoneState
    zone_value: str

    @property
    def kind(self) -> OutputKind:
        return "ipaddress" if self.start == self.end else "iprange"


def coalesce_business_addresses(
    intervals: list[ResolvedAddressInterval] | tuple[ResolvedAddressInterval, ...],
) -> tuple[CoalescedBusinessAddress, ...]:
    """Coalesce exact adjacent coverage without guessing VRF or security zone.

    Intervals merge only for the same system, IP family, resolved VRF, and
    effective security-zone result. Ambiguous VRFs or zones remain separate.
    A one-address result targets ``IPAddress``; a longer result targets
    ``IPRange``. Existing-object overlap validation remains the persistence
    service's responsibility.
    """

    ordered = sorted(
        intervals,
        key=lambda item: (
            item.system_key,
            item.start.version,
            not item.vrf_resolved,
            item.vrf_id is not None,
            item.vrf_id or 0,
            item.zone_state,
            item.zone_value,
            int(item.start),
            int(item.end),
        ),
    )
    results: list[CoalescedBusinessAddress] = []

    for item in ordered:
        current = CoalescedBusinessAddress(
            system_key=item.system_key,
            start=item.start,
            end=item.end,
            vrf_resolved=item.vrf_resolved,
            vrf_id=item.vrf_id,
            zone_state=item.zone_state,
            zone_value=item.zone_value,
        )
        if not results:
            results.append(current)
            continue

        previous = results[-1]
        merge_allowed = (
            item.vrf_resolved
            and item.zone_state != "ambiguous"
            and previous.system_key == current.system_key
            and previous.start.version == current.start.version
            and previous.vrf_resolved
            and previous.vrf_id == current.vrf_id
            and previous.zone_state == current.zone_state
            and previous.zone_value == current.zone_value
            and int(current.start) <= int(previous.end) + 1
        )
        if merge_allowed:
            results[-1] = CoalescedBusinessAddress(
                system_key=previous.system_key,
                start=previous.start,
                end=max(previous.end, current.end),
                vrf_resolved=True,
                vrf_id=previous.vrf_id,
                zone_state=previous.zone_state,
                zone_value=previous.zone_value,
            )
        else:
            results.append(current)

    return tuple(results)
