import enum
from django.db import models

class BaseClass(models.Model):

    
    id = models.AutoField(primary_key=True)
    date_created = models.DateTimeField(auto_now_add=True)
    user_created = models.CharField(max_length=50)
    date_updated = models.DateTimeField(auto_now=True)
    user_updated = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Discount(BaseClass):
    STATUS_CHOICES = (
        ('PENDING_APPROVAL' , "Pending Approval"),
        ('APPROVED' , "Approved"),
        ('REJECTED' , "Rejected"),
    )
    discount_code = models.CharField(max_length=250)
    discount_name = models.CharField(max_length=250)
    discount_rate = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default ='Pending Approval'
    )


    class Meta:
        verbose_name = 'discount'
        verbose_name_plural = 'discounts'
    
    def __str__(self):
        return self.discount_code +" - " +self.discount_name 
    



class Rates(BaseClass):
    rate_name = models.CharField(max_length=550)
    is_holiday_rate = models.BooleanField(default=False)

    class Meta:
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

    class Meta:
        verbose_name_plural = "Rate History"

    def __str__(self):
        return self.rate.rate_name 


class ExtraCharges(BaseClass):
    base_rate = models.ForeignKey(Rates, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    extra_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)
    
    class Meta:
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
    enrollement_approved = models.BooleanField(default=False)
    is_enrolled =models.BooleanField(default=False)
    admission_date = models.DateField()
    
    class Meta:
        verbose_name = 'Child'
        verbose_name_plural = 'Children'

    def __str__(self):
        return self.admission_number +" - " +self.child_first_name + " " + self.child_last_name

   



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

    class Meta:
        verbose_name = 'package'
        verbose_name_plural = 'packages'
    
    
    def __str__(self):
        return self.package_code +" - "+self.package_name
    
    


class HolidayType(BaseClass):
    holiday_code = models.CharField(max_length=10)
    holiday_type = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'holiday type'
        verbose_name_plural = 'holiday Types'


    def __str__(self):
        return self.holiday_code +" - "+ self.holiday_type


class Holiday(BaseClass):
    title = models.CharField(max_length=100)
    holiday_type = models.ForeignKey("HolidayType", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holidays'

    


class Branch(BaseClass):
    branch_code = models.CharField(max_length=10)
    branch_name = models.CharField(max_length=150)
    branch_contact_person = models.CharField(max_length=150)
    branch_contact_mobile_number = models.CharField(max_length=15)
    branch_contact_number = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200)
    address_line3 = models.CharField(max_length=200)

    class Meta:
        verbose_name = 'branch'
        verbose_name_plural = 'branches'

    def __str__(self):
        return self.branch_code +" - "+ self.branch_name


class DayCare(BaseClass):
    daycare_code = models.CharField(max_length=10)
    daycare_name = models.CharField(max_length=150)
    daycare_incharge = models.CharField(max_length=150)
    daycare_contact_number = models.CharField(max_length=15)
    daycare_contact_mobile_number = models.CharField(max_length=15)
    branch = models.ForeignKey("Branch", on_delete=models.CASCADE)


    class Meta:
        verbose_name = 'branch'
        verbose_name_plural = 'branches'
    
    def __str__(self):
        return self.daycare_code +" - "+ self.daycare_name


class ChildEnrollment(BaseClass):
    STATUS_CHOICES = (
        ('PENDING_APPROVAL' , "Pending Approval"),
       ('APPROVED' , "Approved"),
       ( 'REJECTED' , "Rejected"),
    )
    enrollment_code = models.CharField(max_length=20)
    enrollment_date = models.DateField()
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    normal_package = models.ForeignKey("Package", on_delete=models.CASCADE, related_name='normal_package')
    holiday_package = models.ForeignKey("Package", on_delete=models.CASCADE, related_name='holiday_package')
    branch = models.ForeignKey("Branch", on_delete=models.CASCADE)
    center = models.ForeignKey("DayCare", on_delete=models.CASCADE)
    discount = models.ForeignKey("Discount", on_delete=models.CASCADE,null=True, blank=True)
    recipt_number = models.CharField(max_length=50,null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default ='Pending Approval'
    )

    class Meta:
        verbose_name = 'enrollment'
        verbose_name_plural = 'enrollments'
    
    def __str__(self):
        return self.child 
    


class AttendanceLog(BaseClass):
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    date_logged = models.DateField()
    time_logged = models.TimeField()

    class Meta:
        verbose_name = 'Attendance Log'
        verbose_name_plural = 'Attendance Logs'
