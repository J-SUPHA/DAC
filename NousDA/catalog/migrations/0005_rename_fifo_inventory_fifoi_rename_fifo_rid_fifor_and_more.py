# Generated by Django 4.2.11 on 2024-05-01 03:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_rename_fifo_input_fifo_inventory_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='FIFO_Inventory',
            new_name='FIFOI',
        ),
        migrations.RenameModel(
            old_name='FIFO_rid',
            new_name='FIFOR',
        ),
        migrations.RenameModel(
            old_name='HIFO_Inventory',
            new_name='HIFOI',
        ),
        migrations.RenameModel(
            old_name='HIFO_Rid',
            new_name='HIFOR',
        ),
        migrations.RenameModel(
            old_name='LIFO_Inventory',
            new_name='LIFOI',
        ),
        migrations.RenameModel(
            old_name='LIFO_Rid',
            new_name='LIFOR',
        ),
        migrations.RenameModel(
            old_name='Transactions',
            new_name='Transaction',
        ),
    ]
