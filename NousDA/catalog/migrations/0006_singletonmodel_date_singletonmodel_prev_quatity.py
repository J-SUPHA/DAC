# Generated by Django 4.2.11 on 2024-05-01 04:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_rename_fifo_inventory_fifoi_rename_fifo_rid_fifor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="singletonmodel",
            name="date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="singletonmodel",
            name="prev_quatity",
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True
            ),
        ),
    ]
