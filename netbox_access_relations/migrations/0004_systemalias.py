import django.db.models.deletion
import django.db.models.functions.text
import taggit.managers
import utilities.json
from django.db import migrations, models


CREATE_SHARED_NAMESPACE_GUARD = r"""
CREATE OR REPLACE FUNCTION accessrel_check_system_name_namespace()
RETURNS trigger AS $$
DECLARE
    normalized_name text := lower(btrim(NEW.name));
BEGIN
    -- Serialize competing canonical/alias writes for the same normalized value.
    PERFORM pg_advisory_xact_lock(hashtextextended(normalized_name, 0));

    IF TG_TABLE_NAME = 'netbox_access_relations_applicationsystem' THEN
        IF EXISTS (
            SELECT 1 FROM netbox_access_relations_systemalias
            WHERE lower(btrim(name)) = normalized_name
        ) THEN
            RAISE EXCEPTION 'application system name conflicts with a system alias'
                USING ERRCODE = 'unique_violation',
                      CONSTRAINT = 'accessrel_system_name_shared_namespace';
        END IF;
    ELSE
        IF EXISTS (
            SELECT 1 FROM netbox_access_relations_applicationsystem
            WHERE lower(btrim(name)) = normalized_name
        ) THEN
            RAISE EXCEPTION 'system alias conflicts with an application system name'
                USING ERRCODE = 'unique_violation',
                      CONSTRAINT = 'accessrel_system_name_shared_namespace';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER accessrel_appsystem_namespace_guard
BEFORE INSERT OR UPDATE OF name ON netbox_access_relations_applicationsystem
FOR EACH ROW EXECUTE FUNCTION accessrel_check_system_name_namespace();

CREATE TRIGGER accessrel_systemalias_namespace_guard
BEFORE INSERT OR UPDATE OF name ON netbox_access_relations_systemalias
FOR EACH ROW EXECUTE FUNCTION accessrel_check_system_name_namespace();
"""

DROP_SHARED_NAMESPACE_GUARD = r"""
DROP TRIGGER IF EXISTS accessrel_appsystem_namespace_guard
    ON netbox_access_relations_applicationsystem;
DROP TRIGGER IF EXISTS accessrel_systemalias_namespace_guard
    ON netbox_access_relations_systemalias;
DROP FUNCTION IF EXISTS accessrel_check_system_name_namespace();
"""


class Migration(migrations.Migration):
    dependencies = [("netbox_access_relations", "0003_localize_model_metadata")]

    operations = [
        migrations.CreateModel(
            name="SystemAlias",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="Alias")),
                (
                    "system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aliases",
                        to="netbox_access_relations.applicationsystem",
                        verbose_name="Application system",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "System alias",
                "verbose_name_plural": "System aliases",
                "ordering": ("name", "pk"),
            },
        ),
        migrations.AddConstraint(
            model_name="systemalias",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                name="accessrel_systemalias_name_ci_unique",
                violation_error_message="A system alias with this name already exists.",
            ),
        ),
        migrations.RunSQL(CREATE_SHARED_NAMESPACE_GUARD, DROP_SHARED_NAMESPACE_GUARD),
    ]
