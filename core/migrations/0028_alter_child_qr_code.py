# Generated by Django 5.0.1 on 2024-02-11 09:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_child_qr_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='child',
            name='qr_code',
            field=models.CharField(max_length=200, null=True),
        ),
    ]
