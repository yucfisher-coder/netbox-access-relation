from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_access_relations", "0002_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="applicationsystem",
            options={
                "ordering": ("name", "pk"),
                "verbose_name": "Application system",
                "verbose_name_plural": "Application systems",
            },
        ),
        migrations.AlterModelOptions(
            name="systemaddress",
            options={
                "ordering": ("system", "pk"),
                "verbose_name": "System address",
                "verbose_name_plural": "System addresses",
            },
        ),
        migrations.AlterField(
            model_name="applicationsystem",
            name="name",
            field=models.CharField(max_length=200, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="applicationsystem",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("inactive", "Inactive")],
                db_index=True,
                default="active",
                max_length=16,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="applicationsystem",
            name="is_co_located",
            field=models.BooleanField(
                db_index=True,
                default=False,
                editable=False,
                help_text="Automatically set when a native address object is shared with another system.",
                verbose_name="Co-located",
            ),
        ),
        migrations.AlterField(
            model_name="systemaddress",
            name="system",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="addresses",
                to="netbox_access_relations.applicationsystem",
                verbose_name="Application system",
            ),
        ),
        migrations.AlterField(
            model_name="systemaddress",
            name="prefix",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_relation_system_addresses",
                to="ipam.prefix",
                verbose_name="Prefix",
            ),
        ),
        migrations.AlterField(
            model_name="systemaddress",
            name="ip_address",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_relation_system_addresses",
                to="ipam.ipaddress",
                verbose_name="IP address",
            ),
        ),
        migrations.AlterField(
            model_name="systemaddress",
            name="ip_range",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_relation_system_addresses",
                to="ipam.iprange",
                verbose_name="IP range",
            ),
        ),
    ]
