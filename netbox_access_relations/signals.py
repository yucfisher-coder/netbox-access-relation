"""信号处理器：在 SystemAddress 删除时维护共置标记的一致性。

Django 的 pre_delete / post_delete 信号用于在删除地址关联前后
重新计算受影响业务系统的 is_co_located 派生字段。
"""

from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from .models import SystemAddress
from .services.co_location import prepare_address_deletion, recalculate_co_location


@receiver(pre_delete, sender=SystemAddress)
def prepare_system_address_deletion(sender, instance, using, **kwargs):
    instance._co_location_change = prepare_address_deletion(instance, using=using)


@receiver(post_delete, sender=SystemAddress)
def recalculate_after_system_address_deletion(sender, instance, using, **kwargs):
    change = getattr(instance, "_co_location_change", None)
    if change is not None:
        recalculate_co_location(change.system_ids, using=using)
