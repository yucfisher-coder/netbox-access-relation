from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("netbox_access_relations", "0006_global_any_services")]

    operations = [
        migrations.AlterField(
            model_name="policyservice",
            name="port_start",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Port start"),
        ),
        migrations.AlterField(
            model_name="policyservice",
            name="port_end",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Port end"),
        ),
    ]
