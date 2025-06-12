import os
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone


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
        db_table = "dc_extra_charge_after_530"

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
    date_of_birth = models.DateField(null=True, blank=True)
    fathers_name = models.CharField(max_length=200)
    fathers_contact_number = models.IntegerField(null=True, blank=True)
    fathers_whatsapp_number = models.IntegerField(null=True, blank=True)
    mothers_name = models.CharField(max_length=200)
    mothers_contact_number = models.IntegerField(null=True, blank=True)
    mothers_whatsapp_number = models.IntegerField(null=True, blank=True)
    resident_contact_number = models.CharField(max_length=15, null=True, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200)
    address_line3 = models.CharField(max_length=200)
    email_address = models.EmailField(null=True, blank=True)
    is_polymath_student = models.BooleanField(default=False)
    enrollement_approved = models.BooleanField(default=False)
    is_enrolled = models.BooleanField(default=False)
    admission_date = models.DateField(null=True, blank=True)
    child_image = models.ImageField(upload_to="child_images/", null=True)
    qr_code = models.CharField(max_length=200, null=True)
    leave_date = models.DateField(null=True, blank=True)

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


class PackageTerm(BaseClass):
    package_type_code = models.CharField(max_length=10)
    package_type_name = models.CharField(max_length=100)
    is_fixed_package = models.BooleanField(default=True)
    is_dynamic_package = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Package Term"
        verbose_name_plural = "Package Terms"
        db_table = "dc_package_terms"

    def __str__(self):
        return self.package_type_code + " - " + self.package_type_name


class FixedPackage(BaseClass):
    package_code = models.CharField(max_length=10)
    package_name = models.CharField(max_length=200)
    package_type = models.ForeignKey(PackageType, on_delete=models.CASCADE)
    package_term = models.ForeignKey(PackageTerm, on_delete=models.CASCADE, default=1)
    from_time = models.TimeField()
    to_time = models.TimeField()
    no_hours = models.DecimalField(max_digits=10, decimal_places=2)
    no_days_week = models.IntegerField()
    no_days_months = models.IntegerField()
    package_total = models.DecimalField(max_digits=12, decimal_places=2)
    # is_holiday_package = models.BooleanField(default=False)

    class Meta:
        verbose_name = "fixed package"
        verbose_name_plural = "fixed packages"
        db_table = "dc_fixed_packages"

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


class FlexPackages(BaseClass):
    package_code = models.CharField(max_length=10)
    package_name = models.CharField(max_length=200)
    package_type = models.ForeignKey(PackageType, on_delete=models.CASCADE)
    package_term = models.ForeignKey(PackageTerm, on_delete=models.CASCADE, default=2)
    no_hours = models.DecimalField(max_digits=10, decimal_places=2)
    no_days_week = models.IntegerField()
    no_days_months = models.IntegerField()
    package_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "flex package"
        verbose_name_plural = "flex packages"
        db_table = "dc_flex_packages"

    def __str__(self):
        return self.package_code + " - " + self.package_name


class ExtraHoursUpTo530(BaseClass):
    hour_number = models.IntegerField(null=True, blank=True)
    extra_rate = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "extra charges till 5.30"
        verbose_name_plural = "extra charges till 5.30"
        db_table = "dc_extra_charges_till_530"

    def __str__(self):
        return f"{self.hour_number} - {self.extra_rate} - {self.effective_from} - {self.effective_to}"


class PackageExtraHoursMapping(BaseClass):
    fixed_package = models.ForeignKey(
        FixedPackage, on_delete=models.CASCADE, null=True, blank=True
    )
    flex_package = models.ForeignKey(
        FlexPackages, on_delete=models.CASCADE, null=True, blank=True
    )

    extra_hours_upto_530 = models.ForeignKey(
        ExtraHoursUpTo530,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="extraHoursUpto530",
    )
    extra_hours_after_530 = models.ForeignKey(
        ExtraHoursAfter530,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="extraHoursAfter530",
    )

    class Meta:
        verbose_name = "package mapping extra charges upto 5.30"
        verbose_name_plural = "extra charges upto 5.30"
        db_table = "dc_package_extra_charges_mapping"


# class HolidayType(BaseClass):
#     holiday_code = models.CharField(max_length=10)
#     holiday_type = models.CharField(max_length=100)
#     is_polymath_holiday = models.BooleanField(
#         null=True,
#         blank=True,
#     )
#     is_public_holiday = models.BooleanField(
#         null=True,
#         blank=True,
#     )

#     class Meta:
#         verbose_name = "holiday type"
#         verbose_name_plural = "holiday Types"
#         db_table = "dc_holidaytypes"

#     def __str__(self):
#         return self.holiday_code + " - " + self.holiday_type


class Holiday(BaseClass):
    title = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    start_year = models.CharField(max_length=4)
    end_year = models.CharField(max_length=4)
    is_polymath_holiday = models.BooleanField(
        null=True,
        blank=True,
    )
    is_public_holiday = models.BooleanField(
        null=True,
        blank=True,
    )
    is_other_school_holiday = models.BooleanField(
        null=True,
        blank=True,
    )
    no_of_days = models.IntegerField(default=0)
    weekdays_count = models.IntegerField(default=0)
    weekends_count = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        db_table = "dc_holidays"

    def save(self, *args, **kwargs):
        # Set start_year and end_year based on start_date and end_date
        if self.start_date:
            self.start_year = str(self.start_date.year)
        else:
            self.start_year = str(
                timezone.now().year
            )  # Default to current year if no start_date

        if self.end_date:
            self.end_year = str(self.end_date.year)
        else:
            self.end_year = str(
                timezone.now().year
            )  # Default to current year if no end_date

        # Calculate number of days, weekdays, and weekends
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.no_of_days = delta.days + 1  # Include the start date

            # Initialize counts
            weekdays_count = 0
            weekends_count = 0

            for i in range(self.no_of_days):
                day = self.start_date + timedelta(days=i)
                if day.weekday() < 5:  # Monday to Friday are 0 to 4
                    weekdays_count += 1
                else:  # Saturday and Sunday are 5 and 6
                    weekends_count += 1

            self.weekdays_count = weekdays_count
            self.weekends_count = weekends_count
        else:
            self.no_of_days = 0
            self.weekdays_count = 0
            self.weekends_count = 0

        super().save(*args, **kwargs)


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
        db_table = "dc_child_enrollment"

    def __str__(self):
        return self.enrollment_code


class ChildPackageMapping(BaseClass):
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    normal_package = models.ForeignKey(
        "FixedPackage",
        on_delete=models.CASCADE,
        related_name="normal_package",
        null=True,
        blank=True,
    )
    holiday_package = models.ForeignKey(
        "FixedPackage",
        on_delete=models.CASCADE,
        related_name="holiday_package",
        null=True,
        blank=True,
    )
    flex_package = models.ForeignKey(
        "FlexPackages",
        on_delete=models.CASCADE,
        related_name="flex_package",
        null=True,
        blank=True,
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)
    is_holiday_package = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Child Package Mapping"
        verbose_name_plural = "Child Package Mappings"
        db_table = "dc_child_package_mapping"


class AttendanceLog(BaseClass):
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    date_logged = models.DateField()
    time_logged = models.TimeField()
    # branch = models.ForeignKey("Branch", on_delete=models.CASCADE)
    # day_care = models.ForeignKey("DayCare", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Attendance Log"
        verbose_name_plural = "Attendance Logs"
        db_table = "dc_attendance_log"

    def __str__(self):
        return (
            self.child.child_first_name
            + " "
            + self.child.child_last_name
            + " - "
            + str(self.date_logged)
        )


class ExtraChargesHistory(BaseClass):
    extra_charges_after530 = models.ForeignKey(
        ExtraHoursAfter530, on_delete=models.CASCADE, null=True, blank=True
    )
    extra_charges_before530 = models.ForeignKey(
        ExtraHoursUpTo530, on_delete=models.CASCADE, null=True, blank=True
    )
    from_time = models.TimeField(null=True, blank=True)
    to_time = models.TimeField(null=True, blank=True)
    extra_rate = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)

    class Meta:
        verbose_name = "Extra Charge History"
        verbose_name_plural = "Extra Charge History"
        db_table = "dc_extra_charges_history"


class Invoice(BaseClass):
    invoice_date = models.DateField()
    invoice_no = models.CharField(max_length=10, null=True, blank=True)
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    receipt_no = models.CharField(max_length=10, null=True, blank=True)
    paid_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    balance_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "Invoices"
        verbose_name_plural = "Invoices"
        db_table = "dc_invoices"


class PackageChangerequest(BaseClass):
    STATUS_CHOICES = (
        ("PENDING_APPROVAL", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )
    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    old_fixed_package = models.ForeignKey(
        FixedPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_old_fixed_package",
    )
    new_fixed_package = models.ForeignKey(
        FixedPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_new_fixed_package",
    )
    old_flexed_package = models.ForeignKey(
        FlexPackages,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_old_flex_package",
    )

    new_flexed_package = models.ForeignKey(
        FlexPackages,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_new_flex_package",
    )
    old_holiday_package = models.ForeignKey(
        FixedPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_old_holiday_package",
    )

    new_holiday_package = models.ForeignKey(
        FixedPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_new_holiday_package",
    )
    date_requested = models.DateField(auto_now_add=True)
    effective_date = models.DateField(default=timezone.now)
    date_approved = models.DateField(null=True)
    reason_for_request = models.TextField()
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending Approval"
    )

    def __str__(self):
        return self.child.child_first_name + " " + self.child.child_last_name

    class Meta:
        verbose_name = "Package Change Request"
        verbose_name_plural = "Package Change Requests"
        db_table = "dc_package_change_request"


class CenterChangerequest(BaseClass):
    STATUS_CHOICES = (
        ("PENDING_APPROVAL", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    child = models.ForeignKey("Child", on_delete=models.CASCADE)

    old_center = models.ForeignKey(
        DayCare,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_old_center",
    )

    new_center = models.ForeignKey(
        DayCare,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_new_center",
    )

    old_branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_old_branch",
    )

    new_branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_new_branch",
    )
    date_requested = models.DateField(auto_now_add=True)
    effective_date = models.DateField(default=timezone.now)
    date_approved = models.DateField(null=True)
    reason_for_request = models.TextField()
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="Pending Approval"
    )

    class Meta:
        verbose_name = "Center Change Request"
        verbose_name_plural = "Center Change Requests"
        db_table = "dc_center_change_request"


class EnrollmentForm(BaseClass):
    """
    Model to track generated enrollment forms
    """

    enrollment = models.ForeignKey("ChildEnrollment", on_delete=models.CASCADE)
    pdf_filename = models.CharField(max_length=255)
    pdf_path = models.CharField(max_length=500)
    file_size = models.IntegerField(default=0)
    generated_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Enrollment Form"
        verbose_name_plural = "Enrollment Forms"
        db_table = "dc_enrollment_forms"

    def __str__(self):
        return (
            f"Forms for {self.enrollment.child.admission_number} - {self.pdf_filename}"
        )

    def get_download_url(self):
        return f"/download-enrollment-forms/{self.enrollment.id}/"

    def file_exists(self):
        return os.path.exists(self.pdf_path)
