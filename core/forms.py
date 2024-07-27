from decimal import *

from django import forms
from django.core.validators import MinValueValidator

from .models import (
    AttendanceLog,
    Branch,
    Child,
    ChildEnrollment,
    DayCare,
    Discount,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    Package,
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
                "placeholder": "Father" "s Name",
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
                "readonly": "readonly",
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
                "readonly": "readonly",
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
                "placeholder": "Father" "s Name",
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

    class Meta:
        model = PackageType
        fields = ("package_type_name", "is_holiday_package")


# class CreateRateHistoryForm(forms.ModelForm):
#     standard_hourly_rate = forms.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal("0.01"))],
#         required=True,
#         widget=forms.NumberInput(
#             attrs={"class": "form-control", "placeholder": "Rate"}
#         ),
#     )

#     effective_from = forms.DateField(
#         required=True,
#         widget=MyDateInput(
#             attrs={
#                 "class": "form-control",
#                 "id": "effective_from",
#                 "placeholder": "Effective From",
#                 "required": "required",
#                 "data-provider": "flatpickr",
#                 "data-date-format": "Y-m-d",
#             }
#         ),
#     )

#     class Meta:
#         model = RateHistory
#         fields = ("standard_hourly_rate", "effective_from")


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

    class Meta:
        model = PackageType
        fields = ("package_type_name", "id")


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


class CreatePackagesForm(forms.ModelForm):
    # base_rate = forms.ModelChoiceField(
    #     required=True,
    #     queryset=Rates.objects.filter(is_active=True).order_by("rate_name"),
    #     empty_label="-Select Base Rate-",
    #     widget=forms.Select(
    #         attrs={
    #             "class": "form-control",
    #             "placeholder": "Base Rate",
    #             "id": "base_rate",
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
        model = Package
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
        required=True,
        queryset=Package.objects.filter(
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
        queryset=Package.objects.filter(
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
        queryset=Package.objects.filter(
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
        queryset=Package.objects.filter(
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
                "placeholder": "Effective To",
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
                "placeholder": "Effective To",
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
                "id": "effective_from_3",
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
                "placeholder": "Effective To",
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
                "id": "effective_from_4",
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
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_5",
                "placeholder": "Effective To",
                "required": "required",
                "data-provider": "flatpickr",
                "data-date-format": "Y-m-d",
            }
        ),
    )
    effective_to_5 = forms.DateField(
        required=True,
        widget=MyDateInput(
            attrs={
                "class": "form-control",
                "id": "effective_from_5",
                "placeholder": "Effective To",
                "required": "required",
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
    effective_from_6 = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "effective_from_1",
                "class": "form-control",
                "placeholder": "Effective From",
                "required": "required",
            }
        ),
    )
    effective_to_6 = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                "autocomplete": "off",
                "id": "effective_from_1",
                "class": "form-control",
                "placeholder": "Effective To",
                "required": "required",
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

    def __init__(self, *args, **kwargs):
        initial_data = kwargs.pop("initial_data", {})
        super().__init__(*args, **kwargs)
        for i in range(1, 7):
            self.fields[f"hour_number_{i}"].initial = initial_data.get(
                f"hour_number_{i}"
            )
            self.fields[f"extra_rate_{i}"].initial = initial_data.get(f"extra_rate_{i}")
            self.fields[f"effective_from_{i}"].initial = initial_data.get(
                f"effective_from_{i}"
            )
            self.fields[f"effective_to_{i}"].initial = initial_data.get(
                f"effective_to_{i}"
            )
