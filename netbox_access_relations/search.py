"""Native NetBox search indexes, including related business data."""

from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from ipam.models import Prefix, IPAddress, IPRange
from django.dispatch import receiver
from netbox.search import FieldTypes, ObjectFieldValue, SearchIndex
from netbox.search.backends import search_backend

from .filtersets import POLICY_SEARCH_FIELDS, SYSTEM_SEARCH_FIELDS
from .models import AccessPolicy, ApplicationSystem, SystemAddress, SystemAlias


class RelatedSearchIndex(SearchIndex):
    related_fields = ()

    @classmethod
    def to_cache(cls, instance, custom_fields=None):
        values = super().to_cache(instance, custom_fields=())
        # Read aliases and addresses separately to avoid multiplying rows.
        groups = {}
        for field in cls.related_fields:
            if "__" not in field:
                value = getattr(instance, field)
                if value is not None and str(value):
                    values.append(ObjectFieldValue(field, FieldTypes.STRING, 300, str(value)))
                continue
            parts = field.split("__")
            depth = 2 if parts[0] in ("source_system", "target_system") and len(parts) > 2 else 1
            groups.setdefault("__".join(parts[:depth]), []).append(field)
        for fields in groups.values():
            seen = set()
            for row in cls.model.objects.filter(pk=instance.pk).values_list(*fields).distinct():
                for field, value in zip(fields, row):
                    if value is not None and str(value) and (field, str(value)) not in seen:
                        seen.add((field, str(value)))
                        values.append(ObjectFieldValue(field, FieldTypes.STRING, 300, str(value)))
        return values


class ApplicationSystemIndex(RelatedSearchIndex):
    model = ApplicationSystem
    fields = (("name", 100),)
    related_fields = tuple(field for field in SYSTEM_SEARCH_FIELDS if "__" in field)
    display_attrs = ()


class AccessPolicyIndex(RelatedSearchIndex):
    model = AccessPolicy
    fields = (("name", 100), ("category", 200))
    related_fields = tuple(field for field in POLICY_SEARCH_FIELDS if "__" in field)
    display_attrs = ("source_system", "target_system", "category")


indexes = (ApplicationSystemIndex, AccessPolicyIndex)


@receiver((post_save, post_delete), sender=SystemAlias)
@receiver((post_save, post_delete), sender=SystemAddress)
@receiver(post_save, sender=ApplicationSystem)
def refresh_related_search(sender, instance, using, **kwargs):
    """Use NetBox's transaction-aware indexing for changes to search dependencies."""
    system_id = instance.pk if sender is ApplicationSystem else instance.system_id
    for system in ApplicationSystem.objects.using(using).filter(pk=system_id):
        if sender is not ApplicationSystem:
            search_backend.caching_handler(ApplicationSystem, system, created=False, using=using)
    policies = AccessPolicy.objects.using(using).filter(
        Q(source_system_id=system_id) | Q(target_system_id=system_id)
    )
    for policy in policies:
        search_backend.caching_handler(AccessPolicy, policy, created=False, using=using)


@receiver(post_save, sender=Prefix)
@receiver(post_save, sender=IPAddress)
@receiver(post_save, sender=IPRange)
def refresh_address_search(sender, instance, using, **kwargs):
    field = {Prefix: "prefix", IPAddress: "ip_address", IPRange: "ip_range"}[sender]
    for link in SystemAddress.objects.using(using).filter(**{field: instance}):
        refresh_related_search(SystemAddress, link, using)
