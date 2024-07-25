from datetime import datetime
from decimal import Decimal

from django.db import models


# This model will hold the most common properties of the each model.
class BaseClass(models.Model):
    id = models.AutoField(primary_key=True)
    date_created = models.DateTimeField(auto_now_add=True)
    user_created = models.CharField(max_length=50)
    date_updated = models.DateTimeField(auto_now=True)
    user_updated = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# This model will hold the package types.Normal or Holiday packages.
class PackageType(BaseClass):
    package_type_name = models.CharField(max_length=550)
    is_holiday_package = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Package Types"
        db_table = "dc_package_type"

    def __str__(self):
        return self.package_type_name


# This model will hold the discounts .
class Discount(BaseClass):
    STATUS_CHOICES = (
        ("PENDING_APPROVAL", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )
    discount_code = models.CharField(max_length=250)
    discount_name = models.CharField(max_length=250)
    discount_rate = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending Approval"
    )

    class Meta:
        verbose_name = "discount"
        verbose_name_plural = "discounts"
        db_table = "dc_discount"

    def __str__(self):
        return self.discount_code + " - " + self.discount_name


# These models were used to hold the rate base system.
# This was changed after they decided to move to package base system.

# class Rates(BaseClass):
#     rate_name = models.CharField(max_length=550)
#     is_holiday_rate = models.BooleanField(default=False)

#     class Meta:
#         verbose_name_plural = "Rates"
#         db_table = "dc_rate"

#     def __str__(self):
#         return self.rate_name

#     def checkIfHolidayPackage(self):
#         if self.is_holiday_rate:
#             return True
#         else:
#             return False


# class RateHistory(BaseClass):
#     rate = models.ForeignKey(Rates, on_delete=models.CASCADE)
#     standard_hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
#     effective_from = models.DateField()
#     effective_to = models.DateField(null=True)

#     class Meta:
#         verbose_name_plural = "Rate History"
#         db_table = "dc_ratehistory"

#     def __str__(self):
#         return self.rate.rate_name


class ExtraHoursAfter530(BaseClass):
    package_type = models.ForeignKey(PackageType, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    extra_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)

    class Meta:
        unique_together = (("from_time", "to_time", "package_type"),)
        verbose_name = "Extra Charge"
        verbose_name_plural = "Extra Charges"
        db_table = "dc_extrachargeafter530"

    def __str__(self):
        return (
            self.package_type.package_type_name
            + "-"
            + str(self.from_time)
            + "-"
            + str(self.to_time)
            + "-"
            + str(self.is_active)
        )


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
    is_enrolled = models.BooleanField(default=False)
    admission_date = models.DateField()
    child_image = models.ImageField(upload_to="child_images/", null=True)
    qr_code = models.CharField(max_length=200, null=True)

    class Meta:
        verbose_name = "Child"
        verbose_name_plural = "Children"
        db_table = "dc_child"

    def __str__(self):
        return (
            self.admission_number
            + " - "
            + self.child_first_name
            + " "
            + self.child_last_name
        )


class Package(BaseClass):
    package_code = models.CharField(max_length=10)
    package_name = models.CharField(max_length=200)
    package_type = models.ForeignKey(PackageType, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    no_hours = models.DecimalField(max_digits=10, decimal_places=2)
    no_days_week = models.IntegerField()
    no_days_months = models.IntegerField()
    package_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "package"
        verbose_name_plural = "packages"
        db_table = "dc_package"

    def __str__(self):
        return self.package_code + " - " + self.package_name

    def calculate_time_difference(self):
        # Combine from_time and to_time with a dummy date to create datetime objects
        from_time_dt = datetime.combine(datetime.min, self.from_time)
        to_time_dt = datetime.combine(datetime.min, self.to_time)

        # Calculate the difference in seconds
        dt = abs(to_time_dt - from_time_dt)

        # Convert the difference to hours (decimal)
        difference_in_hours = dt.total_seconds() / 3600

        return Decimal(difference_in_hours).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        # Calculate the time difference and set it to no_hours
        self.no_hours = self.calculate_time_difference()
        super().save(*args, **kwargs)


class ExtraHoursUpTo530(BaseClass):
    package_type = models.ForeignKey(PackageType, on_delete=models.CASCADE)
    from_time = models.TimeField()
    to_time = models.TimeField()
    extra_rate = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)

    class Meta:
        verbose_name = "extra charges till 5.30"
        verbose_name_plural = "extra charges till 5.30"
        db_table = "dc_extrachargestill530"

    def __str__(self):
        return (
            self.package_type.package_type_name
            + "-"
            + str(self.from_time)
            + "-"
            + str(self.to_time)
            + "-"
            + str(self.is_active)
        )


class PackageExtraHoursMapping(BaseClass):
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    extra_hours_upto_530 = models.ForeignKey(
        ExtraHoursUpTo530, on_delete=models.CASCADE
    )
    extra_hours_after_530 = models.ForeignKey(
        ExtraHoursAfter530, on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = "package mapping extra charges upto 5.30"
        verbose_name_plural = "extra charges upto 5.30"
        db_table = "dc_packageextrachargesmapping"


class HolidayType(BaseClass):
    holiday_code = models.CharField(max_length=10)
    holiday_type = models.CharField(max_length=100)

    class Meta:
        verbose_name = "holiday type"
        verbose_name_plural = "holiday Types"
        db_table = "dc_holidaytypes"

    def __str__(self):
        return self.holiday_code + " - " + self.holiday_type


class Holiday(BaseClass):
    title = models.CharField(max_length=100)
    holiday_type = models.ForeignKey("HolidayType", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        db_table = "dc_holiday"


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
        verbose_name = "branch"
        verbose_name_plural = "branches"
        db_table = "dc_branch"

    def __str__(self):
        return self.branch_code + " - " + self.branch_name


class DayCare(BaseClass):
    daycare_code = models.CharField(max_length=10)
    daycare_name = models.CharField(max_length=150)
    daycare_incharge = models.CharField(max_length=150)
    daycare_contact_number = models.CharField(max_length=15)
    daycare_contact_mobile_number = models.CharField(max_length=15)
    branch = models.ForeignKey("Branch", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "center"
        verbose_name_plural = "centers"
        db_table = "dc_center"

    def __str__(self):
        return self.daycare_code + " - " + self.daycare_name


class ChildEnrollment(BaseClass):
    STATUS_CHOICES = (
        ("PENDING_APPROVAL", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )
    enrollment_code = models.CharField(max_length=20)
    enrollment_date = models.DateField()
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    normal_package = models.ForeignKey(
        "Package", on_delete=models.CASCADE, related_name="normal_package"
    )
    holiday_package = models.ForeignKey(
        "Package", on_delete=models.CASCADE, related_name="holiday_package"
    )
    branch = models.ForeignKey("Branch", on_delete=models.CASCADE)
    center = models.ForeignKey("DayCare", on_delete=models.CASCADE)
    discount = models.ForeignKey(
        "Discount", on_delete=models.CASCADE, null=True, blank=True
    )
    recipt_number = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending Approval"
    )

    class Meta:
        verbose_name = "enrollment"
        verbose_name_plural = "enrollments"
        db_table = "dc_childenrollment"

    def __str__(self):
        return self.child


class AttendanceLog(BaseClass):
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    date_logged = models.DateField()
    time_logged = models.TimeField()

    class Meta:
        verbose_name = "Attendance Log"
        verbose_name_plural = "Attendance Logs"
        db_table = "dc_attendancelog"


class ExtraChargesHistory(BaseClass):
    extra_charges_after530 = models.ForeignKey(
        ExtraHoursAfter530, on_delete=models.CASCADE, null=True, blank=True
    )
    extra_charges_before530 = models.ForeignKey(
        ExtraHoursUpTo530, on_delete=models.CASCADE, null=True, blank=True
    )
    from_time = models.TimeField()
    to_time = models.TimeField()
    extra_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)

    class Meta:
        verbose_name = "Extra Charge History"
        verbose_name_plural = "Extra Charge History"
        db_table = "dc_extrachargeshistory"
