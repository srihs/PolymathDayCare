import calendar
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


# This model will hold the package types. Normal, Holiday, or Vacation packages.
# - Normal packages: Apply to regular working days
# - Holiday packages: Apply to public holidays (defined in /public_holidays/)
# - Vacation packages: Apply to polymath holidays (/polymath_holidays/) and other holidays (/other_holidays/)
# A package can only be ONE type - not a combination.
class PackageType(BaseClass):
    package_type_name = models.CharField(max_length=550)
    is_holiday_package = models.BooleanField(default=False)
    is_vacation_package = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Package Types"
        db_table = "dc_package_type"

    def __str__(self):
        return self.package_type_name

    def get_package_category(self):
        """Returns the package category as a string."""
        if self.is_holiday_package:
            return "Holiday"
        elif self.is_vacation_package:
            return "Vacation"
        return "Normal"

    def clean(self):
        """Ensure a package type can only be one category."""
        from django.core.exceptions import ValidationError
        if self.is_holiday_package and self.is_vacation_package:
            raise ValidationError("A package type cannot be both Holiday and Vacation. Please select only one.")


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
    discount = models.ForeignKey(
        "Discount",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Discount applied to this package mapping",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True)
    is_holiday_package = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Child Package Mapping"
        verbose_name_plural = "Child Package Mappings"
        db_table = "dc_child_package_mapping"


class AttendanceLog(BaseClass):
    REMOVAL_STATUS_CHOICES = (
        ("NONE", "None"),
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    child = models.ForeignKey("Child", on_delete=models.CASCADE)
    date_logged = models.DateField()
    time_logged = models.TimeField()
    # branch = models.ForeignKey("Branch", on_delete=models.CASCADE)
    # day_care = models.ForeignKey("DayCare", on_delete=models.CASCADE)

    # Removal request fields
    removal_requested = models.BooleanField(default=False)
    removal_reason = models.TextField(null=True, blank=True)
    removal_requested_by = models.CharField(max_length=50, null=True, blank=True)
    removal_requested_date = models.DateTimeField(null=True, blank=True)
    removal_approved_by = models.CharField(max_length=50, null=True, blank=True)
    removal_approved_date = models.DateTimeField(null=True, blank=True)
    removal_status = models.CharField(
        max_length=20, choices=REMOVAL_STATUS_CHOICES, default="NONE"
    )

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


# REDESIGNED MODELS - Replace your existing InvoiceMemo and InvoiceMemoDetail


class InvoiceMemo(BaseClass):
    """
    Main invoice memo - stores only summary/totals and basic info
    Individual month details are stored in InvoiceMemoDetail
    """

    # Basic memo information
    memo_date = models.DateField()
    memo_code = models.CharField(max_length=20, unique=True)
    child = models.ForeignKey("Child", on_delete=models.CASCADE)

    # Which month this memo is FOR (the main month)
    memo_month = models.IntegerField()  # 1-12
    memo_year = models.IntegerField()

    # SUMMARY TOTALS ONLY
    total_outstanding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Outstanding from 2 months ago",
    )
    total_previous_month = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Previous month net amount",
    )
    total_current_month = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, help_text="Current month net amount"
    )

    # GRAND TOTALS
    gross_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total of all charges before payments",
    )
    total_payments = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total payments across all months",
    )
    net_amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Final amount to pay (gross_total - total_payments)",
    )

    # Status and metadata
    STATUS_CHOICES = (
        ("GENERATED", "Generated"),
        ("SENT", "Sent to Parent"),
        ("PAID", "Fully Paid"),
        ("PARTIAL", "Partially Paid"),
        ("CREDIT", "Has Credit Balance"),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="GENERATED"
    )

    # Additional info
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Invoice Memo"
        verbose_name_plural = "Invoice Memos"
        db_table = "dc_invoice_memos"
        unique_together = ("child", "memo_year", "memo_month")
        ordering = ["-memo_year", "-memo_month", "-memo_date"]

    def __str__(self):
        return f"{self.memo_code} - {self.child.admission_number} - {self.get_memo_month_name()} {self.memo_year}"

    def get_memo_month_name(self):
        import calendar

        return calendar.month_name[self.memo_month]

    def calculate_totals(self):
        """Calculate all totals from detail records with FIXED logic"""
        from decimal import Decimal

        details = self.month_details.all()

        # Reset totals
        self.total_outstanding = Decimal("0.00")
        self.total_previous_month = Decimal("0.00")
        self.total_current_month = Decimal("0.00")
        self.gross_total = Decimal("0.00")
        self.total_payments = Decimal("0.00")

        for detail in details:
            # Ensure detail totals are calculated first
            detail.calculate_totals()

            # Add to memo totals based on type - USE NET_BALANCE (after payments)
            if detail.month_type == "OUTSTANDING":
                self.total_outstanding = detail.net_balance
            elif detail.month_type == "PREVIOUS":
                self.total_previous_month = detail.net_balance
            elif detail.month_type == "CURRENT":
                self.total_current_month = detail.net_balance

            # Track gross amounts and payments for reference
            self.gross_total += detail.gross_charges
            self.total_payments += detail.payments_received or Decimal("0.00")

        # FINAL NET AMOUNT = Sum of all net balances (already payment-adjusted)
        self.net_amount_due = (
            self.total_outstanding
            + self.total_previous_month
            + self.total_current_month
        )

        # Update status based on balance
        if self.net_amount_due <= 0:
            self.status = "CREDIT" if self.net_amount_due < 0 else "PAID"
        elif self.total_payments > 0:
            self.status = "PARTIAL"
        else:
            self.status = "GENERATED"

        # Save with specific fields to prevent recursion
        InvoiceMemo.objects.filter(pk=self.pk).update(
            total_outstanding=self.total_outstanding,
            total_previous_month=self.total_previous_month,
            total_current_month=self.total_current_month,
            gross_total=self.gross_total,
            total_payments=self.total_payments,
            net_amount_due=self.net_amount_due,
            status=self.status,
        )

    def add_payment(self, amount, month_type, receipt_number=None):
        """Add payment to specific month"""
        detail = self.month_details.filter(month_type=month_type).first()
        if detail:
            detail.add_payment(amount, receipt_number)
            self.calculate_totals()

    def get_memo_month_name(self):
        return calendar.month_name[self.memo_month]

    def apply_payment_hierarchically(
        self, payment_amount, receipt_number=None, payment_date=None
    ):
        """
        Apply payment hierarchically: Outstanding → Previous → Current
        Returns detailed breakdown of payment allocation
        """
        from decimal import Decimal

        if payment_date is None:
            payment_date = datetime.now().date()

        remaining_amount = Decimal(str(payment_amount))
        allocation_breakdown = []

        # Get month details in sequence order
        details = self.month_details.all().order_by("month_sequence")

        for detail in details:
            if remaining_amount <= 0:
                break

            # Only apply payment if this month has a positive balance
            if detail.net_balance > 0:
                amount_to_apply = min(remaining_amount, detail.net_balance)

                # Apply payment to this month
                detail.add_payment(amount_to_apply, receipt_number)

                allocation_breakdown.append(
                    {
                        "month_type": detail.month_type,
                        "month_name": detail.month_name,
                        "amount_applied": float(amount_to_apply),
                        "previous_balance": float(detail.net_balance + amount_to_apply),
                        "new_balance": float(detail.net_balance),
                        "receipt_number": receipt_number,
                    }
                )

                remaining_amount -= amount_to_apply

        # If there's still remaining amount, apply as advance to current month
        if remaining_amount > 0:
            current_detail = details.filter(month_type="CURRENT").first()
            if current_detail:
                current_detail.add_payment(remaining_amount, receipt_number)
                allocation_breakdown.append(
                    {
                        "month_type": "CURRENT",
                        "month_name": current_detail.month_name,
                        "amount_applied": float(remaining_amount),
                        "previous_balance": float(
                            current_detail.net_balance + remaining_amount
                        ),
                        "new_balance": float(current_detail.net_balance),
                        "receipt_number": receipt_number,
                        "note": "Applied as advance payment (creates credit)",
                    }
                )

        # Recalculate memo totals
        self.calculate_totals()

        return {
            "total_applied": float(payment_amount),
            "allocation_breakdown": allocation_breakdown,
            "memo_net_balance": float(self.net_amount_due),
        }

    def get_payment_summary(self):
        """Get comprehensive payment summary for all months"""
        details = self.month_details.all().order_by("month_sequence")
        payment_summary = []

        for detail in details:
            payments = detail.payment_receipts if detail.payment_receipts else []
            payment_summary.append(
                {
                    "month_type": detail.month_type,
                    "month_name": detail.month_name,
                    "year": detail.actual_year,
                    "gross_charges": float(detail.gross_charges),
                    "payments_received": float(detail.payments_received),
                    "net_balance": float(detail.net_balance),
                    "payment_count": len(payments),
                    "payment_details": payments,
                }
            )

        return payment_summary


class InvoiceMemoDetail(BaseClass):
    """
    Individual month details - each memo has exactly 3 records
    """

    MONTH_TYPE_CHOICES = (
        ("OUTSTANDING", "Outstanding (2 months ago)"),
        ("PREVIOUS", "Previous month"),
        ("CURRENT", "Current month"),
    )

    memo = models.ForeignKey(
        InvoiceMemo, on_delete=models.CASCADE, related_name="month_details"
    )

    # Month identification
    month_sequence = models.IntegerField()  # 1=Outstanding, 2=Previous, 3=Current
    month_type = models.CharField(max_length=20, choices=MONTH_TYPE_CHOICES)
    actual_month = models.IntegerField()  # 1-12 (the actual calendar month)
    actual_year = models.IntegerField()
    month_name = models.CharField(max_length=20)

    # DETAILED CHARGES - All stored here
    package_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    extra_hours_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    holiday_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # DEDUCTIONS
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # CALCULATED TOTALS
    gross_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # PAYMENTS
    payments_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_receipts = models.JSONField(default=list)  # List of payment records

    # FINAL BALANCE
    net_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ADDITIONAL DETAILS (for attendance tracking, etc.)
    package_name = models.CharField(max_length=200, blank=True)
    days_attended = models.IntegerField(default=0)
    expected_days = models.IntegerField(default=22)
    attendance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    is_half_charge_applied = models.BooleanField(default=False)

    # METADATA
    notes = models.TextField(blank=True, null=True)
    calculation_details = models.JSONField(
        default=dict
    )  # For storing breakdown details

    class Meta:
        verbose_name = "Invoice Month Detail"
        verbose_name_plural = "Invoice Month Details"
        db_table = "dc_invoice_memo_details"
        ordering = ["memo", "month_sequence"]
        unique_together = ("memo", "month_sequence")

    def __str__(self):
        return f"{self.memo.memo_code} - {self.month_name} {self.actual_year} ({self.month_type})"

    def calculate_totals(self):
        """Calculate all totals for this month with FIXED payment logic"""
        from decimal import Decimal

        # Calculate gross charges (before deductions)
        self.gross_charges = (
            (self.package_fee or Decimal("0.00"))
            + (self.extra_hours_charge or Decimal("0.00"))
            + (self.holiday_charges or Decimal("0.00"))
            + (self.other_charges or Decimal("0.00"))
        )

        # Calculate total deductions
        self.total_deductions = (self.discount_applied or Decimal("0.00")) + (
            self.other_deductions or Decimal("0.00")
        )

        # Calculate net charges (what should be paid)
        self.net_charges = self.gross_charges - self.total_deductions

        # Calculate final balance (charges - payments) - KEY FIX
        self.net_balance = self.net_charges - (
            self.payments_received or Decimal("0.00")
        )

    def add_payment(self, amount, receipt_number=None):
        """Add payment to this month"""
        from datetime import datetime
        from decimal import Decimal

        self.payments_received += Decimal(str(amount))

        # Add to payment receipts
        payment_record = {
            "amount": float(amount),
            "receipt_number": receipt_number,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
        }

        if isinstance(self.payment_receipts, list):
            self.payment_receipts.append(payment_record)
        else:
            self.payment_receipts = [payment_record]

        # Recalculate totals
        self.calculate_totals()
        self.save()

    def save(self, *args, **kwargs):
        """Auto-calculate totals on save"""
        # Only calculate if not in a recursive save
        if "update_fields" not in kwargs:
            self.calculate_totals()
        super().save(*args, **kwargs)


# In core/models.py

from django.db import models
from django.utils import timezone

# Assuming BaseClass, InvoiceMemo, and InvoiceMemoDetail are already defined as you provided.
# Just add this new model to your existing models.py file.


class PaymentTransaction(models.Model):
    id = models.AutoField(primary_key=True)
    memo = models.ForeignKey(
        "InvoiceMemo", on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ("CASH", "Cash"),
            ("BANK_TRANSFER", "Bank Transfer"),
            ("CHEQUE", "Cheque"),
            ("CARD", "Card"),
            ("OTHER", "Other"),
        ],
        default="CASH",
    )
    notes = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    user_created = models.CharField(
        max_length=50, default="system"
    )  # Added default for simplicity, adjust as needed
    date_updated = models.DateTimeField(auto_now=True)
    user_updated = models.CharField(
        max_length=50, default="system"
    )  # Added default for simplicity, adjust as needed
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"
        db_table = "dc_payment_transactions"
        ordering = ["-payment_date"]

    def __str__(self):
        return f"{self.memo.memo_code} - Rs.{self.amount} - {self.receipt_number}"

    def add_payment(self, amount, receipt_number=None):
        """Enhanced payment addition with better tracking"""
        from datetime import datetime
        from decimal import Decimal

        amount_decimal = Decimal(str(amount))
        self.payments_received += amount_decimal

        # Create payment record
        payment_record = {
            "amount": float(amount_decimal),
            "receipt_number": receipt_number
            or f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "month_type": self.month_type,
            "month_name": self.month_name,
        }

        # Initialize payment_receipts if None
        if not isinstance(self.payment_receipts, list):
            self.payment_receipts = []

        self.payment_receipts.append(payment_record)

        # Recalculate totals
        self.calculate_totals()
        self.save()

        return payment_record
