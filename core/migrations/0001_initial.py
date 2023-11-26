# Generated by Django 4.2.7 on 2023-11-26 06:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BaseRates',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('user_created', models.CharField(max_length=50)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('user_updated', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('standard_hourly_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('extra_hours_standard_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('extra_hours_standard_increase_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('holiday_hourly_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('extra_hours_holiday_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('extra_hours_holiday_increase_rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('effective_from', models.DateField()),
                ('effective_to', models.DateField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Child',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('user_created', models.CharField(max_length=50)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('user_updated', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('admission_number', models.CharField(max_length=10)),
                ('child_first_name', models.CharField(max_length=150)),
                ('child_last_name', models.CharField(max_length=150)),
                ('date_of_birth', models.DateField()),
                ('fathers_name', models.CharField(max_length=200)),
                ('fathers_contact_number', models.IntegerField()),
                ('fathers_whatsapp_number', models.IntegerField()),
                ('mothers_name', models.CharField(max_length=200)),
                ('mothers_contact_number', models.IntegerField()),
                ('mothers_whatsapp_number', models.IntegerField()),
                ('resident_contact_number', models.IntegerField()),
                ('address_line1', models.CharField(max_length=200)),
                ('address_line2', models.CharField(max_length=200)),
                ('address_line3', models.CharField(max_length=200)),
                ('email_address', models.EmailField(max_length=254)),
                ('is_polymath_student', models.BooleanField(default=False)),
                ('recipt_number', models.CharField(max_length=50)),
                ('admission_date', models.DateField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='HolidayType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('user_created', models.CharField(max_length=50)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('user_updated', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('holiday_code', models.CharField(max_length=10)),
                ('holiday_type', models.CharField(max_length=100)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Package',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('user_created', models.CharField(max_length=50)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('user_updated', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('package_code', models.CharField(max_length=10)),
                ('package_name', models.CharField(max_length=200)),
                ('rate', models.DecimalField(decimal_places=2, max_digits=8)),
                ('from_time', models.DateTimeField()),
                ('to_time', models.DateTimeField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('user_created', models.CharField(max_length=50)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('user_updated', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('title', models.CharField(max_length=100)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('holiday_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.holidaytype')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
