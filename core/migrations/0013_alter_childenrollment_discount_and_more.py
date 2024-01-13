# Generated by Django 4.2.7 on 2024-01-13 14:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_alter_childenrollment_discount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='childenrollment',
            name='discount',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.discount'),
        ),
        migrations.AlterField(
            model_name='childenrollment',
            name='recipt_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
