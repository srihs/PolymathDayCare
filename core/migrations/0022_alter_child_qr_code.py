# Generated by Django 5.0.1 on 2024-02-10 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_remove_child_image_child_child_image_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='child',
            name='qr_code',
            field=models.CharField(max_length=200),
        ),
    ]
