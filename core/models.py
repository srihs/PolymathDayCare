from django.db import models

# Create your models here.
class BaseClass(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    user_created = models.CharField(max_length=50)
    date_updated = models.DateTimeField(auto_now=True)
    user_created = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True    


class Child(BaseClass):
    admission_number = models.CharField(max_length=10)
    child_first_name = models.CharField(max_length=150)
    child_last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    fathers_name = models.CharField(max_length=200)
    fathers_contact_number = models.IntegerField(max_length=10)
    fathers_whatsapp_number = models.IntegerField(max_length=10)
    mothers_name = models.CharField(max_length=200)
    mothers_contact_number = models.IntegerField(max_length=10)
    mothers_whatsapp_number = models.IntegerField(max_length=10)
    resident_contact_number = models.IntegerField(max_length=10)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200)
    address_line3 = models.CharField(max_length=200)
    email_address = models.EmailField()
    is_polymath_student = models.BooleanField(default=False)
    recipt_number = models.CharField(max_length=50)
    admission_date = models.DateField()


class PackageType(BaseClass):
    package_type_code = models.CharField(max_length=10)
    package_type = models.CharField(max_length=100)
    
    
class Package(BaseClass):
    package_code = models.CharField(max_length=10)
    package_type = models.ForeignKey('PackageType',on_delete=models.CASCADE)
    package_name = models.CharField(max_length=200)
    hours_per_day = models.IntegerField() 
    no_of_days = models.IntegerField()
    days_per_month = models.ImageField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    amount = models.DecimalField(decimal_places=2,max_digits=10)


class HolidayType(BaseClass):
    holiday_code = models.CharField(max_length=10)
    holiday_type =models.CharField(max_length=100)


class Holiday(BaseClass):
    title = models.CharField(max_length=100)
    holiday_type = models.ForeignKey('HolidayType',on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()


