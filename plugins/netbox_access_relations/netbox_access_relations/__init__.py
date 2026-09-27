"""NetBox Access Relations plugin."""

from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginConfig


class AccessRelationsConfig(PluginConfig):
    name = "netbox_access_relations"
    verbose_name = _("Access Relations")
    description = _("Manage access relations using supported NetBox extension points.")
    version = "1.0.3"
    author = "NetBox Access Relations maintainers"
    base_url = "access-relations"
    min_version = "4.7.0"
    max_version = "4.7.99"
    default_settings = {}

    def ready(self):
        super().ready()

        from . import signals  # noqa: F401

__version__ = "1.0.3"
config = AccessRelationsConfig

__all__ = ("config",)
