from django.db import migrations, models


def canonicalize_any_services(apps, schema_editor):
    PolicyService = apps.get_model("netbox_access_relations", "PolicyService")
    for policy_id in PolicyService.objects.filter(is_any=True).values_list("policy_id", flat=True).distinct():
        services = PolicyService.objects.filter(policy_id=policy_id, is_any=True).order_by("pk")
        keeper = services.first()
        services.exclude(pk=keeper.pk).delete()
        keeper.protocol = "tcp"
        keeper.save(update_fields=("protocol",))


class Migration(migrations.Migration):
    dependencies = [("netbox_access_relations", "0005_accesspolicy_policyservice_and_more")]

    operations = [
        migrations.RemoveConstraint(model_name="policyservice", name="accessrel_policyservice_unique_any"),
        migrations.RunPython(canonicalize_any_services, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="policyservice",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_any=True),
                fields=("policy",),
                name="accessrel_policyservice_single_any",
            ),
        ),
    ]
