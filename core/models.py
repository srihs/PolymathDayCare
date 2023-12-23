from django.db import models


class BaseClass(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    user_created = models.CharField(max_length=50)
    date_updated = models.DateTimeField(auto_now=True)
    user_updated = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Rates(BaseClass):
    rate_name = models.CharField(max_length=550)
    is_holiday_rate = models.BooleanField(default=False)

    class meta:
        verbose_name_plural = "Rates"

    def __str__(self):
        return self.rate_name
    
    def checkIfHolidayPackage(self):
        if self.is_holiday_rate:
            return True
        else:
            return False
    


class RateHistory(BaseClass): 
    rate = models.ForeignKey(Rates, on_delete=models.CASCADE)
    standard_hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)

    def __str__(self):
        return self.rate.rate_name 


class ExtraCharges(BaseClass):
    base_rate = models.ForeignKey(Rates, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    extra_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)
    
    class meta:
        unique_together = (("base_rate", "from_time","to_time"),)
        verbose_name = 'Extra Charge'
        verbose_name_plural = 'Extra Charges'
    
    def __str__(self):
        return self.base_rate.rate_name + "-" + str(self.from_time) + "-" +  str(self.to_time) +"-"+str(self.is_active)


class Child(BaseClass):
    admission_number = models.CharField(max_length=10)
    child_first_name = models.CharField(max_length=150)
    child_last_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    fathers_name = models.CharField(max_length=200)
    fathers_contact_number = models.IntegerField()
    fathers_whatsapp_number = models.IntegerField()
    mothers_name = models.CharField(max_length=200)
    mothers_contact_number = models.IntegerField()
    mothers_whatsapp_number = models.IntegerField()
    resident_contact_number = models.IntegerField()
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200)
    address_line3 = models.CharField(max_length=200)
    email_address = models.EmailField()
    is_polymath_student = models.BooleanField(default=False)
    recipt_number = models.CharField(max_length=50)
    admission_date = models.DateField()
    
    class meta:
        verbose_name = 'Child'
        verbose_name_plural = 'Children'

    def __str__(self):
        return self.admission_number +" - " +self.child_first_name + self.child_last_name

   



class Package(BaseClass):
    
    package_type= models.CharField(max_length=10)
    package_code = models.CharField(max_length=10)
    package_name = models.CharField(max_length=200)
    base_rate = models.ForeignKey(Rates, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    no_hours = models.DecimalField(max_digits=8, decimal_places=2)
    no_days_week = models.IntegerField()
    no_days_months = models.IntegerField()
    is_holiday_package = models.BooleanField()
    
    
    def __str__(self):
        return self.package_code +" - "+self.package_name
    
   


class HolidayType(BaseClass):
    holiday_code = models.CharField(max_length=10)
    holiday_type = models.CharField(max_length=100)

    def __str__(self):
        return self.holiday_code +" - "+ self.holiday_type


class Holiday(BaseClass):
    title = models.CharField(max_length=100)
    holiday_type = models.ForeignKey("HolidayType", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
