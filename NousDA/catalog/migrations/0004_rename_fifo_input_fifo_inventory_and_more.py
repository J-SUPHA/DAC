# Generated by Django 4.2.11 on 2024-05-01 03:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_alter_singletonmodel_options_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='FIFO_Input',
            new_name='FIFO_Inventory',
        ),
        migrations.RenameModel(
            old_name='FIFO_Output',
            new_name='FIFO_rid',
        ),
        migrations.RenameModel(
            old_name='HIFO_Input',
            new_name='HIFO_Inventory',
        ),
        migrations.RenameModel(
            old_name='HIFO_Output',
            new_name='HIFO_Rid',
        ),
        migrations.RenameModel(
            old_name='LIFO_Input',
            new_name='LIFO_Inventory',
        ),
        migrations.RenameModel(
            old_name='LIFO_Output',
            new_name='LIFO_Rid',
        ),
    ]
