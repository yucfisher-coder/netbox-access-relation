"""Small enhancements scoped to access-relations pages."""

from netbox.plugins import PluginTemplateExtension


class TableSelectionExtension(PluginTemplateExtension):
    def head(self):
        request = self.context.get("request")
        if request and request.path.startswith("/plugins/access-relations/"):
            return self.render("netbox_access_relations/inc/table_selection.html")
        return ""


template_extensions = (TableSelectionExtension,)
