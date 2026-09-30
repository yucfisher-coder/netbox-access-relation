"""Uniqueness guard for access policies.

Two access policies are considered duplicates when they share the same
source system, target system, and an *exactly equal* set of policy services
(protocol + is_any + port range).  Validity period and category are
intentionally excluded from the comparison, per business rules.

This module is deliberately framework-agnostic so it can be called from every
write entry point: the web form, the workbook importer, and the REST API.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Prefetch

from ..models import AccessPolicy, PolicyService


def service_key(protocol, is_any, port_start, port_end) -> tuple:
    """Normalize a single service into a hashable identity tuple.

    The shape mirrors ``BasePolicyServiceInlineFormSet.clean`` so that the
    form, the importer, and this module all agree on what "the same service"
    means.
    """
    if is_any:
        return (protocol, True, None, None)
    return (protocol, False, port_start, port_end)


def service_set(services: Iterable) -> frozenset:
    """Build a comparable service-set identity from heterogeneous inputs.

    Accepts ``PolicyService`` instances, plain dicts (as produced by the
    importer), or pre-normalized 4-tuples.
    """
    keys = set()
    for svc in services:
        if isinstance(svc, PolicyService):
            keys.add(service_key(svc.protocol, svc.is_any, svc.port_start, svc.port_end))
        elif isinstance(svc, dict):
            keys.add(service_key(
                svc.get("protocol"),
                svc.get("is_any", False),
                svc.get("port_start"),
                svc.get("port_end"),
            ))
        elif isinstance(svc, tuple) and len(svc) == 4:
            keys.add(svc)
        else:
            raise TypeError(f"Unsupported service representation: {type(svc)!r}")
    return frozenset(keys)


def get_policy_service_keys(policy: AccessPolicy) -> frozenset:
    """Read the service identity set directly from an existing policy."""
    return service_set(policy.services.all())


def find_duplicate_policies(
    source_system_id,
    target_system_id,
    service_keys: frozenset,
    *,
    exclude_policy_id=None,
    user=None,
) -> list:
    """Return existing policies duplicating the given endpoint + service set.

    A policy counts as a duplicate only when its full service set is *exactly
    equal* to ``service_keys`` (not merely overlapping).
    """
    if not service_keys:
        return []
    queryset = AccessPolicy.objects.filter(
        source_system_id=source_system_id,
        target_system_id=target_system_id,
    ).exclude(pk=exclude_policy_id).prefetch_related(
        Prefetch(
            "services",
            queryset=PolicyService.objects.only(
                "policy_id", "protocol", "is_any", "port_start", "port_end",
            ),
        ),
    )
    if user is not None:
        queryset = queryset.restrict(user, "view")
    return [
        policy for policy in queryset
        if get_policy_service_keys(policy) == service_keys
    ]
