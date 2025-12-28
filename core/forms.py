from datetime import datetime
from decimal import *

from django import forms
from django.core.validators import MinValueValidator
import calendar

from datetime import datetime


from .models import (
    AttendanceLog,
    Branch,
    CenterChangerequest,
    Child,
    ChildEnrollment,
    DayCare,
    Discount,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    FixedPackage,
    FlexPackages,
    Holiday,
    PackageChangerequest,
    # HolidayType,
    PackageType,
)


class MyDateInput(forms.widgets.DateInput):
    input_type = "date"


class CreateChildForm(forms.ModelForm):
    CHOICES = [
        ("1", "Yes"),
        ("0", "No"),
    ]
    admission_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
    )
    child_first_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "First Name",
            }
        ),
    )
    child_last_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Last Name",
            }
        ),
    )
    date_of_birth = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "dob",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Date of Birth",
            }
        ),
    )
    fathers_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Fathers Name",
            }
        ),
    )
    fathers_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Contact number",
            }
        ),
    )
    fathers_whatsapp_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Whatsapp no",
            }
        ),
    )
    mothers_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Mothers Name",
            }
        ),
    )
    mothers_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Contact number",
            }
        ),
    )
    mothers_whatsapp_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Whatsapp no",
            }
        ),
    )
    resident_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Residency contact number"}
        ),
    )
    address_line1 = forms.CharField(
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line1"}
        ),
    )
    address_line2 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line2"}
        ),
    )
    address_line3 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line3"}
        ),
    )
    email_address = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "id": "email", "placeholder": "Email"}
        ),
    )
    is_polymath_student = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "type": "checkbox",
                "checked": "checked",
            }
        ),
    )

    admission_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "admission_date",
                "placeholder": "Admission Date",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "type": "checkbox",
                "checked": "checked",
            }
        ),
    )
    child_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={"class": "form-control", "id": "image", "required": "false"}
        ),
    )
    qr_code = forms.ImageField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "id": "qr_code", "required": "false"}
        )
    )

    class Meta:
        model = Child
        fields = (
            "admission_number",
            "child_first_name",
            "admission_number",
            "child_first_name",
            "child_last_name",
            "date_of_birth",
            "fathers_name",
            "fathers_contact_number",
            "fathers_whatsapp_number",
            "mothers_name",
            "mothers_contact_number",
            "mothers_whatsapp_number",
            "resident_contact_number",
            "address_line1",
            "address_line2",
            "address_line3",
            "email_address",
            "is_polymath_student",
            "is_active",
            "child_image",
            "qr_code",
        )


class UpdateChildForm(forms.ModelForm):
    CHOICES = [
        ("1", "Yes"),
        ("0", "No"),
    ]
    admission_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
    )
    child_first_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "First Name",
            }
        ),
    )
    child_last_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Last Name",
            }
        ),
    )
    date_of_birth = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "readonly": "readonly",
                "class": "form-control",
                "required": "true",
                "id": "dob",
                "data-provider": "flatpickr",
                "data-date-format": "%Y-%m-%d",
                "placeholder": "Date of Birth",
            }
        ),
    )
    fathers_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "class": "form-control",
                "required": "true",
                "placeholder": "Fathers Name",
            }
        ),
    )
    fathers_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Contact number",
            }
        ),
    )
    fathers_whatsapp_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Whatsapp no",
            }
        ),
    )
    mothers_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "class": "form-control",
                "required": "true",
                "placeholder": "Mothers Name",
            }
        ),
    )
    mothers_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Contact number",
            }
        ),
    )
    mothers_whatsapp_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "placeholder": "Whatsapp no",
            }
        ),
    )
    resident_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Residency contact number"}
        ),
    )
    address_line1 = forms.CharField(
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line1"}
        ),
    )
    address_line2 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line2"}
        ),
    )
    address_line3 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line3"}
        ),
    )
    email_address = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "id": "email", "placeholder": "Email"}
        ),
    )
    is_polymath_student = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    admission_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "readonly": "readonly",
                "class": "form-control",
                "required": "true",
                "id": "admission_date",
                "data-provider": "flatpickr",
                "data-date-format": "%Y-%m-%d",
                "placeholder": "Admission Date",
            }
        ),
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    child_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(
            attrs={"class": "form-control", "id": "image", "required": "false"}
        ),
    )
    qr_code = forms.ImageField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "id": "qr_code", "required": "false"}
        )
    )

    class Meta:
        model = Child
        fields = (
            "admission_number",
            "child_first_name",
            "admission_date",
            "child_first_name",
            "child_last_name",
            "date_of_birth",
            "fathers_name",
            "fathers_contact_number",
            "fathers_whatsapp_number",
            "mothers_name",
            "mothers_contact_number",
            "mothers_whatsapp_number",
            "resident_contact_number",
            "address_line1",
            "address_line2",
            "address_line3",
            "email_address",
            "is_polymath_student",
            "is_active",
            "child_image",
            "qr_code",
        )


class CreatePackageTypeForm(forms.ModelForm):
    package_type_name = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Rate name"}
        ),
    )
    is_holiday_package = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )
    is_vacation_package = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    class Meta:
        model = PackageType
        fields = ("package_type_name", "is_holiday_package", "is_vacation_package")

    def clean(self):
        cleaned_data = super().clean()
        is_holiday = cleaned_data.get("is_holiday_package")
        is_vacation = cleaned_data.get("is_vacation_package")
        if is_holiday and is_vacation:
            raise forms.ValidationError(
                "A package type cannot be both Holiday and Vacation. Please select only one."
            )
        return cleaned_data


class UpdatePackageTypeForm(forms.ModelForm):
    package_type_name = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Rate name"}
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    is_holiday_package = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    is_vacation_package = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    class Meta:
        model = PackageType
        fields = ("package_type_name", "id", "is_holiday_package", "is_vacation_package")

    def clean(self):
        cleaned_data = super().clean()
        is_holiday = cleaned_data.get("is_holiday_package")
        is_vacation = cleaned_data.get("is_vacation_package")
        if is_holiday and is_vacation:
            raise forms.ValidationError(
                "A package type cannot be both Holiday and Vacation. Please select only one."
            )
        return cleaned_data


class CreateExtraChargesForm(forms.ModelForm):
    package_type = forms.ModelChoiceField(
        required=True,
        queryset=PackageType.objects.filter(is_active=True).order_by(
            "package_type_name"
        ),
        empty_label="-Select Package Type -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Package Type",
                "id": "package_type",
            }
        ),
    )
    from_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "id": "from_time",
                "class": "form-control",
                "placeholder": "From Time",
                "data-provider": "flatpickr",
                "required": "true",
            }
        ),
    )
    to_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "id": "to_time",
                "class": "form-control",
                "placeholder": "To Time",
                "required": "true",
            }
        ),
    )

    extra_rate = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Rate"}
        ),
    )
    effective_from = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "effective_from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Effective from",
            }
        ),
    )
    effective_to = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Effective to",
            }
        ),
    )

    class Meta:
        model = ExtraHoursAfter530
        fields = (
            "package_type",
            "from_time",
            "extra_rate",
            "to_time",
            "effective_from",
            "effective_to",
        )


class UpdateExtraChargesForm(forms.ModelForm):
    from_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "id": "from_time",
                "class": "form-control",
                "placeholder": "From Time",
                "data-provider": "flatpickr",
                "required": "true",
            }
        ),
    )
    to_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "id": "to_time",
                "class": "form-control",
                "placeholder": "To Time",
                "required": "true",
            }
        ),
    )

    extra_rate = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Rate"}
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = ExtraHoursAfter530
        fields = (
            "id",
            "from_time",
            "extra_rate",
            "to_time",
        )


class CreateFixedPackagesForm(forms.ModelForm):
    # package_term = forms.ModelChoiceField(
    #     required=True,
    #     queryset=PackageTerm.objects.filter(is_active=True).order_by(
    #         "package_type_code"
    #     ),
    #     empty_label="-Select Package Term-",
    #     widget=forms.Select(
    #         attrs={
    #             "class": "form-control",
    #             "placeholder": "Base Rate",
    #             "id": "package_term",
    #         }
    #     ),
    # )
    package_type = forms.ModelChoiceField(
        required=True,
        empty_label="-Select package type -",
        queryset=PackageType.objects.filter(is_active=True).order_by(
            "package_type_name"
        ),
        label="- Package Type -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "package_type",
            }
        ),
    )

    package_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Package Name"}
        ),
    )

    package_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Package Code"}
        ),
    )

    from_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "from_time",
                "class": "form-control",
                "placeholder": "From Time",
                "required": "required",
            }
        ),
    )
    to_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "to_time",
                "class": "form-control",
                "placeholder": "To Time",
                "required": "required",
            }
        ),
    )

    no_days_week = forms.IntegerField(
        validators=[MinValueValidator(int("0"))],
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "No of days for a week"}
        ),
    )
    no_days_months = forms.IntegerField(
        validators=[MinValueValidator(int("0"))],
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "No of days for a month",
                "id": "no_days_months",
            }
        ),
    )

    package_total = forms.DecimalField(
        decimal_places=2,
        max_digits=12,
        validators=[MinValueValidator(Decimal("00.00"))],
        required=True,
        widget=forms.NumberInput(
            attrs={
                "autocomplete": "off",
                "id": "package_total",
                "class": "form-control",
                "placeholder": "Package total",
            }
        ),
    )

    class Meta:
        model = FixedPackage
        fields = (
            "package_name",
            "package_code",
            "package_type",
            "from_time",
            "to_time",
            "no_days_week",
            "no_days_months",
            "package_total",
        )


class CreateFlexPackagesForm(forms.ModelForm):
    package_type = forms.ModelChoiceField(
        required=True,
        empty_label="-Select package type -",
        queryset=PackageType.objects.filter(is_active=True).order_by(
            "package_type_name"
        ),
        label="- Package Type -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "package_type",
            }
        ),
    )

    package_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Package Name"}
        ),
    )

    package_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Package Code"}
        ),
    )

    no_hours = forms.IntegerField(
        validators=[MinValueValidator(int("0"))],
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "No of hours"}
        ),
    )

    no_days_week = forms.IntegerField(
        validators=[MinValueValidator(int("0"))],
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "No of days for a week"}
        ),
    )
    no_days_months = forms.IntegerField(
        validators=[MinValueValidator(int("0"))],
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "No of days for a month",
                "id": "no_days_months",
            }
        ),
    )

    package_total = forms.DecimalField(
        decimal_places=2,
        max_digits=12,
        validators=[MinValueValidator(Decimal("00.00"))],
        required=True,
        widget=forms.NumberInput(
            attrs={
                "autocomplete": "off",
                "id": "package_total",
                "class": "form-control",
                "placeholder": "Package total",
            }
        ),
    )

    class Meta:
        model = FlexPackages
        fields = (
            "package_name",
            "package_code",
            "package_type",
            "no_hours",
            "no_days_week",
            "no_days_months",
            "package_total",
        )


class CreateBranchForm(forms.ModelForm):
    branch_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Branch Code",
                "readonly": "readonly",
            }
        ),
    )

    branch_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Branch Name"}
        ),
    )

    branch_contact_person = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contact person name"}
        ),
    )

    branch_contact_mobile_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Mobile number"}
        ),
    )

    branch_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone number"}
        ),
    )

    address_line1 = forms.CharField(
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line1"}
        ),
    )

    address_line2 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line2"}
        ),
    )

    address_line3 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line3"}
        ),
    )

    class Meta:
        model = Branch
        fields = (
            "branch_code",
            "branch_name",
            "branch_contact_person",
            "branch_contact_mobile_number",
            "branch_contact_number",
            "address_line1",
            "address_line2",
            "address_line3",
        )


class UpdateBranchForm(forms.ModelForm):
    branch_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Branch Code",
                "readonly": "readonly",
            }
        ),
    )

    branch_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Branch Name"}
        ),
    )

    branch_contact_person = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contact person name"}
        ),
    )

    branch_contact_mobile_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Mobile number"}
        ),
    )

    branch_contact_number = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Phone number"}
        ),
    )

    address_line1 = forms.CharField(
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line1"}
        ),
    )

    address_line2 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line2"}
        ),
    )

    address_line3 = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Address Line3"}
        ),
    )

    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    class Meta:
        model = Branch
        fields = (
            "branch_code",
            "branch_name",
            "branch_contact_person",
            "branch_contact_mobile_number",
            "branch_contact_number",
            "address_line1",
            "address_line2",
            "address_line3",
            "is_active",
        )


class CreateDayCareForm(forms.ModelForm):
    daycare_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Center Code",
                "readonly": "readonly",
            }
        ),
    )

    daycare_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Center Name"}
        ),
    )

    branch = forms.ModelChoiceField(
        required=True,
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-Select branch-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "branch"}
        ),
    )

    daycare_incharge = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Incharge Name"}
        ),
    )

    daycare_contact_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Mobile Number"}
        ),
    )

    daycare_contact_mobile_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contact Number"}
        ),
    )

    class Meta:
        model = DayCare
        fields = (
            "daycare_code",
            "daycare_name",
            "branch",
            "daycare_incharge",
            "daycare_contact_number",
            "daycare_contact_mobile_number",
        )


class UpdateDayCareForm(forms.ModelForm):
    daycare_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Center Code",
                "readonly": "readonly",
            }
        ),
    )

    daycare_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Center Name"}
        ),
    )

    branch = forms.ModelChoiceField(
        required=True,
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-Select branch-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "branch"}
        ),
    )

    daycare_incharge = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Incharge Name"}
        ),
    )

    daycare_contact_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Mobile Number"}
        ),
    )

    daycare_contact_mobile_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contact Number"}
        ),
    )

    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "type": "checkbox"}
        ),
    )

    class Meta:
        model = DayCare
        fields = (
            "daycare_code",
            "daycare_name",
            "branch",
            "daycare_incharge",
            "daycare_contact_number",
            "daycare_contact_mobile_number",
            "is_active",
        )


class CreateDiscountForm(forms.ModelForm):
    discount_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Center Code",
                "readonly": "readonly",
            }
        ),
    )

    discount_name = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Discount Name"}
        ),
    )

    discount_rate = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Discount rate"}
        ),
    )

    class Meta:
        model = Discount
        fields = ("discount_code", "discount_name", "discount_rate")


class CreateEnrollmentForm(forms.ModelForm):
    enrollment_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Center Code",
                "readonly": "readonly",
            }
        ),
    )

    enrollment_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "effective_from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Enrolment Date",
            }
        ),
    )
    child = forms.ModelChoiceField(
        required=True,
        queryset=Child.objects.filter(is_active=True, is_enrolled=False).order_by(
            "admission_number"
        ),
        empty_label="-Select child-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "child"}
        ),
    )

    branch = forms.ModelChoiceField(
        required=True,
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-Select branch-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "branch"}
        ),
    )

    # dayCare = forms.ModelChoiceField(required=True, queryset=DayCare.objects.filter(is_active=True,branch=0).order_by('daycare_code'),empty_label="-Select daycare-",
    #                                 widget=forms.Select(
    #                                     attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'dayCare'}))

    dayCare = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Daycare center",
                "list": "branches",
            }
        ),
    )

    normal_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True,
            package_type__is_holiday_package=False,
            package_type__is_vacation_package=False,
        ).order_by("package_code"),
        required=False,
        empty_label="-Select normal package-",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "normal_package",
            }
        ),
    )

    holiday_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=True
        ).order_by("package_code"),
        empty_label="-Select holiday package-",
        required=True,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "holiday_package",
            }
        ),
    )

    vacation_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_vacation_package=True
        ).order_by("package_code"),
        empty_label="-Select vacation package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "vacation_package",
            }
        ),
    )

    flex_package = forms.ModelChoiceField(
        queryset=FlexPackages.objects.filter(is_active=True).order_by("package_code"),
        empty_label="-Select flex package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "flex_package",
            }
        ),
    )

    discount = forms.ModelChoiceField(
        required=False,
        queryset=Discount.objects.filter(is_active=True, status="Approved").order_by(
            "discount_code"
        ),
        empty_label="-Select discounts-",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "discount",
            }
        ),
    )
    recipt_number = forms.CharField(
        required=False,
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Receipt Number"}
        ),
    )

    class Meta:
        model = ChildEnrollment
        fields = (
            "enrollment_code",
            "enrollment_date",
            "child",
            "branch",
            "dayCare",
            "normal_package",
            "holiday_package",
            "vacation_package",
            "flex_package",
            "discount",
            "recipt_number",
        )


class CreateCheckInForm(forms.ModelForm):
    child = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Child", "list": "children"}
        ),
    )

    date_logged = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "date_logged",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Date",
            }
        ),
    )

    time_logged = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "time_logged",
                "class": "form-control",
                "placeholder": "Time",
                "required": "required",
            }
        ),
    )

    class Meta:
        model = AttendanceLog
        fields = ("date_logged", "time_logged")


class SearchForm(forms.Form):
    from_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "from_date",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "From date",
            }
        ),
    )

    to_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "to_date",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "To date",
            }
        ),
    )

    # class CreateExtraChargesTill530form(forms.ModelForm)
    enrollment_code = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Center Code",
                "readonly": "readonly",
            }
        ),
    )

    enrollment_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "effective_from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Enrolment Date",
            }
        ),
    )
    child = forms.ModelChoiceField(
        required=True,
        queryset=Child.objects.filter(is_active=True, is_enrolled=False).order_by(
            "admission_number"
        ),
        empty_label="-Select child-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "child"}
        ),
    )

    branch = forms.ModelChoiceField(
        required=True,
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-Select branch-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "branch"}
        ),
    )

    # dayCare = forms.ModelChoiceField(required=True, queryset=DayCare.objects.filter(is_active=True,branch=0).order_by('daycare_code'),empty_label="-Select daycare-",
    #                                 widget=forms.Select(
    #                                     attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'dayCare'}))

    dayCare = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Daycare center",
                "list": "branches",
            }
        ),
    )

    normal_package = forms.ModelChoiceField(
        required=True,
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=False
        ).order_by("package_code"),
        empty_label="-Select normal package-",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "normal_package",
            }
        ),
    )

    holiday_package = forms.ModelChoiceField(
        required=True,
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=True
        ).order_by("package_code"),
        empty_label="-Select holiday package-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "Base Rate", "id": "package"}
        ),
    )

    discount = forms.ModelChoiceField(
        required=False,
        queryset=Discount.objects.filter(is_active=True, status="Approved").order_by(
            "discount_code"
        ),
        empty_label="-Select discounts-",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "discount",
            }
        ),
    )
    recipt_number = forms.CharField(
        required=False,
        max_length=250,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Receipt Number"}
        ),
    )

    class Meta:
        model = ChildEnrollment
        fields = (
            "enrollment_code",
            "enrollment_date",
            "child",
            "branch",
            "dayCare",
            "normal_package",
            "holiday_package",
            "discount",
            "recipt_number",
        )


class CreateExtraHoursUpTo530Form(forms.ModelForm):
    hour_number_1 = forms.IntegerField(required=False, label="First Hour")
    extra_rate_1 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_1 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_1",
                "placeholder": "Effective From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_1 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_1",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    hour_number_2 = forms.IntegerField(required=False, label="Second Hour")
    extra_rate_2 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_2 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_2",
                "placeholder": "Effective From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_2 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_2",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    hour_number_3 = forms.IntegerField(required=False, label="Third Hour")
    extra_rate_3 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_3 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_3",
                "placeholder": "Effective From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_3 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_3",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    hour_number_4 = forms.IntegerField(required=False, label="Fourth Hour")
    extra_rate_4 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_4 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_4",
                "placeholder": "Effective From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_4 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_4",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    hour_number_5 = forms.IntegerField(required=False, label="Fifth Hour")
    extra_rate_5 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_5 = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_5",
                "required": "False",
                "placeholder": "Effective From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_5 = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_5",
                "required": "False",
                "placeholder": "Effective To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    hour_number_6 = forms.IntegerField(required=False, label="Sixth Hour")
    extra_rate_6 = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from_6 = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "False",
                "id": "effective_from_6",
                "placeholder": "Effective from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_6 = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_6",
                "required": "False",
                "placeholder": "Effective To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    class Meta:
        model = ExtraHoursUpTo530
        fields = (
            "hour_number",
            "extra_rate",
            "effective_from",
            "effective_to",
        )


class UpdateExtraHoursUpTo530Form(forms.ModelForm):
    extra_rate = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Extra Rate"}
        ),
    )
    effective_from = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_1",
                "placeholder": "Effective From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_to_1",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = ExtraHoursUpTo530
        fields = (
            "extra_rate",
            "effective_from",
            "effective_to",
            "id",
        )


class AttendanceReportForm(forms.Form):
    child = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Child", "list": "children"}
        ),
    )

    from_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "from_date",
                "placeholder": "From",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    to_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "to_date",
                "placeholder": "To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        required=False,
        empty_label="-Select the branch-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "branch", "id": "branch"}
        ),
    )

    center = forms.ModelChoiceField(
        required=False,
        queryset=DayCare.objects.none(),
        empty_label="-Select the center-",
        widget=forms.Select(
            attrs={"class": "form-control", "placeholder": "center", "id": "center"}
        ),
    )


class CreatePublicHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "autocomplete": "off",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "autocomplete": "off",
            },
        ),
    )

    class Meta:
        model = Holiday
        fields = ("title", "start_date", "end_date")


class UpdatePublicHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = Holiday
        fields = ("id", "title", "start_date", "end_date")


class CreatePolymathHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    class Meta:
        model = Holiday
        fields = ("title", "start_date", "end_date")


class UpdatePolymathHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = Holiday
        fields = ("id", "title", "start_date", "end_date")


class CreateOtherhHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    class Meta:
        model = Holiday
        fields = ("title", "start_date", "end_date")


class UpdateOtherHolidayForm(forms.ModelForm):
    title = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Holiday Name",
            }
        ),
    )

    start_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "start_date",
                "placeholder": "From",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    end_date = forms.DateField(
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "end_date",
                "placeholder": "To",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )

    id = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = Holiday
        fields = ("id", "title", "start_date", "end_date")


class CreatePackageChangeRequestForm(forms.ModelForm):
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, enrollement_approved=True
        ).order_by("admission_number"),
        empty_label="-Select Child -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Old fixed package",
                "id": "child",
            }
        ),
    )

    new_fixed_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=False
        ).order_by("package_code"),
        empty_label="-Select fixed package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Old fixed package",
                "id": "new_fixed_package",
            }
        ),
    )
    new_flex_package = forms.ModelChoiceField(
        queryset=FlexPackages.objects.filter(
            is_active=True, package_type__is_holiday_package=False
        ).order_by("package_code"),
        empty_label="-Select flex package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "New flex package",
                "id": "new_flex_package",
            }
        ),
    )

    new_holiday_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=True
        ),
        empty_label="-Select holiday package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "holiday_package",
            }
        ),
    )

    new_vacation_package = forms.ModelChoiceField(
        queryset=FixedPackage.objects.filter(
            is_active=True, package_type__is_vacation_package=True
        ),
        empty_label="-Select vacation package-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Vacation Package",
                "id": "vacation_package",
            }
        ),
    )

    reason_for_request = forms.CharField(
        max_length=550,
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "id": "reason_for_request",
                "placeholder": "Reason for the change request",
                "rows": "3",
            }
        ),
    )

    effective_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_date",
                "placeholder": "Effective from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "required": "true",
            }
        ),
    )

    class Meta:
        model = PackageChangerequest
        fields = (
            "child",
            "new_fixed_package",
            "new_flex_package",
            "new_holiday_package",
            "new_vacation_package",
            "reason_for_request",
            "effective_date",
        )


class ChildSearchForm(forms.ModelForm):
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(is_active=True).order_by("admission_number"),
        empty_label="-Select Child -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Child",
                "id": "child",
            }
        ),
    )

    class Meta:
        model = Child
        fields = ("child",)


class CreateCenterChangeRequestForm(forms.ModelForm):
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, enrollement_approved=True
        ).order_by("admission_number"),
        empty_label="-Select Child -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Old fixed package",
                "id": "child",
            }
        ),
    )

    new_branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        empty_label="-Select new branch-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "New flex package",
                "id": "new_flex_package",
            }
        ),
    )

    new_center = forms.ModelChoiceField(
        queryset=DayCare.objects.filter(is_active=True),
        empty_label="-Select new center-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Base Rate",
                "id": "holiday_package",
            }
        ),
    )

    reason_for_request = forms.CharField(
        max_length=550,
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "id": "reason_for_request",
                "placeholder": "Reason for the change request",
                "rows": "3",
            }
        ),
    )

    effective_date = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_date",
                "placeholder": "Effective from",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "required": "true",
            }
        ),
    )

    class Meta:
        model = CenterChangerequest
        fields = (
            "child",
            "new_center",
            "new_branch",
            "effective_date",
        )



class GenerateInvoiceForm(forms.Form):
    """Simplified form for invoice generation"""

    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, enrollement_approved=True
        ).order_by("admission_number"),
        empty_label="-Select Child -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Old fixed package",
                "id": "child",
            }
        ),
    )

    month = forms.ChoiceField(
        choices=[
            ("1", "January"),
            ("2", "February"),
            ("3", "March"),
            ("4", "April"),
            ("5", "May"),
            ("6", "June"),
            ("7", "July"),
            ("8", "August"),
            ("9", "September"),
            ("10", "October"),
            ("11", "November"),
            ("12", "December"),
        ],
        initial=datetime.now().month,
        widget=forms.Select(
            attrs={"class": "form-control", "id": "month", "required": "required"}
        ),
    )

    year = forms.ChoiceField(
        choices=[(i, i) for i in range(2020, 2030)],
        initial=datetime.now().year,
        widget=forms.Select(
            attrs={"class": "form-control", "id": "year", "required": "required"}
        ),
    )


class InvoiceSearchForm(forms.Form):
    """Form for searching invoices"""

    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, enrollement_approved=True
        ).order_by("admission_number"),
        empty_label="-Select Child -",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "placeholder": "Old fixed package",
                "id": "child",
            }
        ),
    )

    from_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "id": "search_from_date",
                "type": "date",
                "placeholder": "From Date",
            }
        ),
    )

    to_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "id": "search_to_date",
                "type": "date",
                "placeholder": "To Date",
            }
        ),
    )

    status = forms.ChoiceField(
        choices=[
            ("", "-All Status-"),
            ("GENERATED", "Generated"),
            ("SENT", "Sent to Parent"),
            ("PAID", "Fully Paid"),
            ("PARTIAL", "Partially Paid"),
            ("CREDIT", "Has Credit Balance"),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "search_status"}),
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-All Branches-",
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "search_branch"}),
    )


# Add this updated form to your forms.py file (or replace the existing one)


class ExtraHoursReportForm(forms.Form):
    """Complete form for extra hours report filters"""

    REPORT_TYPE_CHOICES = [
        ("detailed", "Detailed Report"),
        ("monthly", "Monthly Summary"),
        ("child", "By Child"),
    ]

    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, enrollement_approved=True
        ).order_by("admission_number"),
        empty_label="-All Children-",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "child",
            }
        ),
    )

    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        initial="detailed",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "report_type",
            }
        ),
    )

    from_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "id": "from_date",
                "type": "date",
                "placeholder": "From Date",
            }
        ),
    )

    to_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "id": "to_date",
                "type": "date",
                "placeholder": "To Date",
            }
        ),
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True).order_by("branch_code"),
        empty_label="-All Branches-",
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "branch"}),
    )

    center = forms.ModelChoiceField(
        queryset=DayCare.objects.filter(is_active=True).order_by("daycare_code"),
        empty_label="-All Centers-",
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "center"}),
    )


# Add this form to your forms.py file

class LoadInvoiceMemoForm(forms.Form):
    """Form for loading/searching invoice memos"""
    
    # Child selection with enhanced widget
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(is_active=True, is_enrolled=True).order_by('admission_number'),
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'id': 'load_child',
            'data-placeholder': 'Search by admission number or child name...'
        }),
        label="Child",
        help_text="Select child to search memo for",
        required=True
    )
    
    # Month selection
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'load_month'
        }),
        label="Month",
        required=True
    )
    
    # Year selection
    current_year = datetime.now().year
    YEAR_CHOICES = [(year, year) for year in range(current_year - 2, current_year + 2)]
    year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'load_year'
        }),
        label="Year",
        initial=current_year,
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current month and year as default
        current_date = datetime.now()
        self.fields['month'].initial = current_date.month
        self.fields['year'].initial = current_date.year
    """Form for loading/searching invoice memos"""
    
    # Child selection with enhanced widget
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(is_active=True, is_enrolled=True).order_by('admission_number'),
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'id': 'load_child',
            'data-placeholder': 'Search by admission number or child name...'
        }),
        label="Child",
        help_text="Select child to search memo for",
        required=True
    )
    
    # Month selection
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'load_month'
        }),
        label="Month",
        required=True
    )
    
    # Year selection
    current_year =datetime.now().year
    YEAR_CHOICES = [(year, year) for year in range(current_year - 2, current_year + 2)]
    year = forms.ChoiceField(
        choices=YEAR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'load_year'
        }),
        label="Year",
        initial=current_year,
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current month and year as default
        current_date = datetime.now()
        self.fields['month'].initial = current_date.month
        self.fields['year'].initial = current_date.year




# Add these enhanced forms to your forms.py file

class EnhancedCheckInForm(forms.ModelForm):
    """Enhanced check-in form with better validation"""
    
    SEARCH_TYPE_CHOICES = [
        ('date_range', 'Date Range'),
        ('child', 'Specific Child'),
    ]
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        initial='date_range',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'search_type'
        }),
        label='Search Type'
    )
    
    child = forms.CharField(
        max_length=250,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control", 
                "placeholder": "Search by admission number or name", 
                "list": "children",
                "autocomplete": "off"
            }
        ),
        label="Child"
    )

    date_logged = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "required": "true",
                "id": "date_logged",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
                "placeholder": "Select Date",
            }
        ),
        label="Date"
    )

    time_logged = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "time_logged",
                "class": "form-control",
                "placeholder": "Select Time",
                "required": "required",
            }
        ),
        label="Time"
    )
    
    from_date = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "from_date",
                "placeholder": "From Date",
                "max": datetime.now().strftime('%Y-%m-%d')
            }
        ),
        label="From Date"
    )
    
    to_date = forms.DateField(
        required=False,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "to_date", 
                "placeholder": "To Date",
                "max": datetime.now().strftime('%Y-%m-%d')
            }
        ),
        label="To Date"
    )

    class Meta:
        model = AttendanceLog
        fields = ("child", "date_logged", "time_logged")
        
    def clean_child(self):
        """Validate child admission number"""
        child_input = self.cleaned_data.get('child')
        
        if not child_input:
            raise forms.ValidationError("Child selection is required")
        
        # Extract admission number if input contains full name
        if ' - ' in child_input:
            admission_number = child_input.split(' - ')[0].strip()
        else:
            admission_number = child_input.strip()
        
        try:
            child = Child.objects.get(
                admission_number=admission_number,
                is_active=True,
                enrollement_approved=True
            )
            return admission_number
        except Child.DoesNotExist:
            raise forms.ValidationError(
                f"Child with admission number '{admission_number}' not found or not enrolled"
            )
    
    def clean_date_logged(self):
        """Validate attendance date"""
        date_logged = self.cleaned_data.get('date_logged')
        
        if not date_logged:
            raise forms.ValidationError("Date is required")
        
        # Cannot be future date
        if date_logged > datetime.now().date():
            raise forms.ValidationError("Cannot log attendance for future dates")
        
        # Cannot be more than 30 days old
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        if date_logged < thirty_days_ago:
            raise forms.ValidationError("Cannot log attendance more than 30 days old")
        
        return date_logged
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        child_admission = cleaned_data.get('child')
        date_logged = cleaned_data.get('date_logged')
        time_logged = cleaned_data.get('time_logged')
        
        if child_admission and date_logged:
            try:
                child = Child.objects.get(admission_number=child_admission)
                
                # Check if child was enrolled on this date
                if child.admission_date and child.admission_date > date_logged:
                    raise forms.ValidationError(
                        f"Child was not enrolled on {date_logged}. "
                        f"Admission date: {child.admission_date}"
                    )
                
                # Check for exact duplicate
                if time_logged and AttendanceLog.objects.filter(
                    child=child,
                    date_logged=date_logged,
                    time_logged=time_logged
                ).exists():
                    raise forms.ValidationError(
                        f"Duplicate entry: {child.child_first_name} already has "
                        f"a record for {date_logged} at {time_logged}"
                    )
                    
            except Child.DoesNotExist:
                pass  # Already handled in clean_child
        
        return cleaned_data


class MissingAttendanceSearchForm(forms.Form):
    """Form for searching missing attendance records"""
    
    SEARCH_TYPE_CHOICES = [
        ('date_range', 'Date Range'),
        ('child', 'Specific Child'),
    ]
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPE_CHOICES,
        initial='date_range',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'search_type'
        }),
        label='Search Type'
    )
    
    child = forms.ModelChoiceField(
        queryset=Child.objects.filter(
            is_active=True, 
            enrollement_approved=True
        ).order_by('admission_number'),
        empty_label="-Select Child-",
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'child_select'
        }),
        label='Child'
    )
    
    from_date = forms.DateField(
        required=False,
        widget=MyDateInput(attrs={
            'class': 'form-control',
            'id': 'from_date',
            'placeholder': 'From Date'
        }),
        label='From Date'
    )
    
    to_date = forms.DateField(
        required=False,
        widget=MyDateInput(attrs={
            'class': 'form-control',
            'id': 'to_date',
            'placeholder': 'To Date'
        }),
        label='To Date'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        search_type = cleaned_data.get('search_type')
        child = cleaned_data.get('child')
        from_date = cleaned_data.get('from_date')
        to_date = cleaned_data.get('to_date')
        
        if search_type == 'child' and not child:
            raise forms.ValidationError("Please select a child for child-specific search")
        
        if search_type == 'date_range':
            if not from_date or not to_date:
                raise forms.ValidationError("Please select both from and to dates for date range search")
            
            if from_date > to_date:
                raise forms.ValidationError("From date cannot be after to date")
        
        return cleaned_data


class BulkAttendanceFixForm(forms.Form):
    """Form for bulk fixing attendance records"""
    
    fixes_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    def clean_fixes_data(self):
        import json
        
        fixes_data = self.cleaned_data.get('fixes_data')
        
        try:
            fixes = json.loads(fixes_data)
            
            if not isinstance(fixes, list):
                raise forms.ValidationError("Invalid fixes data format")
            
            if len(fixes) == 0:
                raise forms.ValidationError("No fixes provided")
            
            if len(fixes) > 100:  # Reasonable limit
                raise forms.ValidationError("Too many fixes (maximum 100 allowed)")
            
            # Validate each fix
            for i, fix in enumerate(fixes):
                if not isinstance(fix, dict):
                    raise forms.ValidationError(f"Fix {i+1}: Invalid format")
                
                required_fields = ['child_admission', 'date_logged', 'time_logged']
                for field in required_fields:
                    if field not in fix or not fix[field]:
                        raise forms.ValidationError(f"Fix {i+1}: Missing {field}")
            
            return fixes
            
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format")