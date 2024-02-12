from django import forms
from django.forms import ImageField
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from django.core.validators import MinValueValidator
from .models import Child, Rates, ExtraCharges,RateHistory,Package, Branch,DayCare, ChildEnrollment, Discount,AttendanceLog
from decimal import *


class MyDateInput(forms.widgets.DateInput):
    input_type = 'date'


class CreateChildForm(forms.ModelForm):
    CHOICES = [
        ('1', 'Yes'),
        ('0', 'No'),
    ]
    admission_number = forms.CharField(max_length=250, required=True,
                                       widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}))
    child_first_name = forms.CharField(max_length=250, required=True,
                                       widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true',
                                                                     'placeholder': 'First Name'}))
    child_last_name = forms.CharField(max_length=250, required=True,
                                      widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true',
                                                                    'placeholder': 'Last Name'}))
    date_of_birth = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'required': 'true', 'id': 'dob', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Date of Birth'}))
    fathers_name = forms.CharField(max_length=250, required=True,
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true',
                                                                 'placeholder': 'Father''s Name'}))
    fathers_contact_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Contact number'}))
    fathers_whatsapp_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Whatsapp no'}))
    mothers_name = forms.CharField(max_length=250, required=True,
                                   widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true',
                                                                 'placeholder': 'Mothers Name'}))
    mothers_contact_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Contact number'}))
    mothers_whatsapp_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Whatsapp no'}))
    resident_contact_number = forms.CharField(max_length=250, required=True,
                                              widget=forms.TextInput(attrs={'class': 'form-control',
                                                                            'placeholder': 'Residency contact number'}))
    address_line1 = forms.CharField(max_length=250, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Address Line1'}))
    address_line2 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line2'}))
    address_line3 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line3'}))
    email_address = forms.CharField(max_length=50, required=False,
                                    widget=forms.EmailInput(
                                        attrs={'class': 'form-control', 'id': 'email', 'placeholder': 'Email'}))
    is_polymath_student = forms.BooleanField(required=False,widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox', 'checked': 'checked'}))
    
    admission_date = forms.DateField(required=True, widget=MyDateInput(attrs={'class': 'form-control',
                                                                              'id': 'admission_date',
                                                                              'placeholder': 'Admission Date',
                                                                              'required': 'required',
                                                                              'data-provider': 'flatpickr',
                                                                                      'data-date-format': 'Y-m-d'}))
    is_active = forms.BooleanField(required=False,widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox', 'checked': 'checked'}))
    child_image = forms.ImageField(required=False,widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'image','required': 'false'}))
    qr_code =  forms.ImageField(widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'qr_code','required': 'false'}))

    class Meta:
        model = Child
        fields = ('admission_number', 'child_first_name', 'admission_number', 'child_first_name', 'child_last_name',
                          'date_of_birth', 'fathers_name', 'fathers_contact_number', 'fathers_whatsapp_number', 'mothers_name',
                          'mothers_contact_number', 'mothers_whatsapp_number', 'resident_contact_number', 'address_line1',
                          'address_line2', 'address_line3', 'email_address', 'is_polymath_student','is_active','child_image','qr_code')


class UpdateChildForm(forms.ModelForm):
    CHOICES = [
        ('1', 'Yes'),
        ('0', 'No'),
    ]
    admission_number = forms.CharField(max_length=250, required=True,
                                       widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control'}))
    child_first_name = forms.CharField(max_length=250, required=True,
                                       widget=forms.TextInput(attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true',
                                                                     'placeholder': 'First Name'}))
    child_last_name = forms.CharField(max_length=250, required=True,
                                      widget=forms.TextInput(attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true',
                                                                    'placeholder': 'Last Name'}))
    date_of_birth = forms.DateField(required=True, widget=MyDateInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true', 'id': 'dob', 'data-provider': 'flatpickr',
               'data-date-format': '%Y-%m-%d', 'placeholder': 'Date of Birth'}))
    fathers_name = forms.CharField(max_length=250, required=True,
                                   widget=forms.TextInput(attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true',
                                                                 'placeholder': 'Father''s Name'}))
    fathers_contact_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Contact number'}))
    fathers_whatsapp_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Whatsapp no'}))
    mothers_name = forms.CharField(max_length=250, required=True,
                                   widget=forms.TextInput(attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true',
                                                                 'placeholder': 'Mothers Name'}))
    mothers_contact_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Contact number'}))
    mothers_whatsapp_number = forms.CharField(max_length=250, required=True, widget=forms.TextInput(
        attrs={'class': 'form-control', 'required': 'true', 'placeholder': 'Whatsapp no'}))
    resident_contact_number = forms.CharField(max_length=250, required=True,
                                              widget=forms.TextInput(attrs={'class': 'form-control',
                                                                            'placeholder': 'Residency contact number'}))
    address_line1 = forms.CharField(max_length=250, widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Address Line1'}))
    address_line2 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line2'}))
    address_line3 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line3'}))
    email_address = forms.CharField(max_length=50, required=False,
                                    widget=forms.EmailInput(
                                        attrs={'class': 'form-control', 'id': 'email', 'placeholder': 'Email'}))
    is_polymath_student = forms.BooleanField(required=False, widget=forms.CheckboxInput(
        attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    admission_date = forms.DateField(required=True, widget=MyDateInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true', 'id': 'admission_date', 'data-provider': 'flatpickr',
               'data-date-format': '%Y-%m-%d', 'placeholder': 'Admission Date'}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(
        attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    child_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'image','required': 'false'}))
    qr_code =  forms.ImageField(widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'qr_code','required': 'false'}))

    class Meta:
        model = Child
        fields = ('admission_number', 'child_first_name', 'admission_date', 'child_first_name', 'child_last_name',
                  'date_of_birth', 'fathers_name', 'fathers_contact_number', 'fathers_whatsapp_number', 'mothers_name',
                  'mothers_contact_number', 'mothers_whatsapp_number', 'resident_contact_number', 'address_line1',
                  'address_line2', 'address_line3', 'email_address', 'is_polymath_student',
                  'is_active','child_image','qr_code')


class CreateRatesForm(forms.ModelForm):
    rate_name = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Rate name'}))
    is_holiday_rate = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    
    class Meta:
        model = Rates
        fields = ('rate_name','is_holiday_rate')


class CreateRateHistoryForm(forms.ModelForm):
    standard_hourly_rate = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Rate'}))
    
    effective_from = forms.DateField(required=True, widget=MyDateInput(attrs={'class': 'form-control',
                                                                              'id': 'effective_from',
                                                                              'placeholder': 'Effective From',
                                                                              'required': 'required',
                                                                              'data-provider': 'flatpickr',
                                                                                      'data-date-format': 'Y-m-d'}))
    
    
    
    class Meta:
        model = RateHistory
        fields = ('standard_hourly_rate','effective_from')

    


class UpdateRatesForm(forms.ModelForm):
    rate_name = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', }))
    
    id = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', }))
    
    is_holiday_rate = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    class Meta:
        model = Rates
        fields = ('rate_name','id','is_holiday_rate')
        
        
        
    
class CreateExtraChargesForm(forms.ModelForm):
    base_rate = forms.ModelChoiceField(required=True, queryset=Rates.objects.filter(is_active=True).order_by('rate_name'),empty_label="-Select Base Rate-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'base_rate'}))
    from_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'id':'from_time','class': 'form-control','placeholder': 'From Time',
                                                                             'data-provider': 'flatpickr','required': 'true'}))
    to_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'id':'to_time','class': 'form-control','placeholder': 'To Time','required': 'true'}))
    
    extra_rate =forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Rate'}))
    effective_from = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'required': 'true', 'id': 'effective_from', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Effective from'}))
    effective_to = forms.DateField(required=False, widget=MyDateInput(
        attrs={'class': 'form-control', 'id': 'effective_to', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Effective to'}))

    class Meta:
        model = ExtraCharges
        fields = ('base_rate','from_time','extra_rate','to_time','effective_from','effective_to')


class UpdateExtraChargesForm(forms.ModelForm):
    
    from_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'id':'from_time','class': 'form-control','placeholder': 'From Time',
                                                                             'data-provider': 'flatpickr','required': 'true','readonly': 'true'}))
    to_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'id':'to_time','class': 'form-control','placeholder': 'To Time','required': 'true','readonly': 'true'}))
    
    extra_rate =forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Rate'}))
    effective_from = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'required': 'true', 'id': 'effective_from', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Effective from'}))
    effective_to = forms.DateField(required=False, widget=MyDateInput(
        attrs={'class': 'form-control', 'id': 'effective_to', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Effective to'}))

    class Meta:
        model = ExtraCharges
        fields = ('from_time','extra_rate','to_time','effective_from','effective_to')  



class CreatePackagesForm(forms.ModelForm):
    Daily = "Daily"
    Weekly = "Weekly"
    Monthly = "Monthly"
    HOURLY = "Hourly"

    packageType = [
        (Daily, "Daily"),
        (Weekly, "Weekly"),
        (Monthly, "Monthly"),
        (HOURLY, "Hourly"),
    ]

    base_rate = forms.ModelChoiceField(required=True, queryset=Rates.objects.filter(is_active=True).order_by('rate_name'),empty_label="-Select Base Rate-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'base_rate'}))

    package_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Package Name' }))
    
    package_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Package Code' }))
    
    package_type = forms.ChoiceField(required=True, choices = packageType,label="- Package Type -",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'base_rate'}))
  
    from_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'autocomplete': 'off','id':'from_time','class': 'form-control','placeholder': 'From Time',
                                                                             'required': 'required'}))
    to_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'autocomplete': 'off','id':'to_time','class': 'form-control','placeholder': 'To Time','required': 'required'}))
    
    no_hours = forms.DecimalField(decimal_places=2, max_digits=4, validators=[MinValueValidator(Decimal('00.00'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'autocomplete': 'off','id':'no_hours','class': 'form-control','placeholder': 'No of hours'}))
    no_days_week = forms.IntegerField(validators=[MinValueValidator(int('0'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'No of days for a week'}))
    no_days_months =forms.IntegerField(validators=[MinValueValidator(int('0'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'No of days for a month'}))
    is_holiday_package = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
   

    class Meta:
        model = Package
        fields = ('package_name','package_code','package_type','from_time','to_time','no_hours','no_days_week','no_days_months','is_holiday_package')   




class CreateBranchForm(forms.ModelForm):

    branch_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Branch Code','readonly': 'readonly' }))
    
    branch_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Branch Name' }))
    
    branch_contact_person = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Contact person name' }))
    
    branch_contact_mobile_number = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Mobile number' }))
    
    branch_contact_number = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Phone number' }))
    
    address_line1 = forms.CharField(max_length=250, widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line1'}))
    
    address_line2 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line2'}))
    
    address_line3 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line3'}))
    
    
    
    class Meta:
        model = Branch
        fields = ('branch_code','branch_name','branch_contact_person','branch_contact_mobile_number','branch_contact_number','address_line1','address_line2','address_line3')  



class UpdateBranchForm(forms.ModelForm):

    branch_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Branch Code','readonly': 'readonly' }))
    
    branch_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Branch Name' }))
    
    branch_contact_person = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Contact person name' }))
    
    branch_contact_mobile_number = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Mobile number' }))
    
    branch_contact_number = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Phone number' }))
    
    address_line1 = forms.CharField(max_length=250, widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line1'}))
    
    address_line2 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line2'}))
    
    address_line3 = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Address Line3'}))
    
    is_active = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    class Meta:
        model = Branch
        fields = ('branch_code','branch_name','branch_contact_person','branch_contact_mobile_number','branch_contact_number','address_line1','address_line2','address_line3','is_active')  


class CreateDayCareForm(forms.ModelForm):

    daycare_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Code','readonly': 'readonly' }))
    
    daycare_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Name' }))
    
    branch = forms.ModelChoiceField(required=True, queryset=Branch.objects.filter(is_active=True).order_by('branch_code'),empty_label="-Select branch-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'branch'}))
    
    daycare_incharge = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Incharge Name' }))
    
    daycare_contact_number = forms.CharField(max_length=10, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Mobile Number' }))

    daycare_contact_mobile_number = forms.CharField(max_length=10, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Contact Number' }))
    
    
    class Meta:
        model = DayCare
        fields = ('daycare_code','daycare_name','branch','daycare_incharge','daycare_contact_number','daycare_contact_mobile_number')  



class UpdateDayCareForm(forms.ModelForm):
    daycare_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Code','readonly': 'readonly' }))
    
    daycare_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Name' }))
    
    branch = forms.ModelChoiceField(required=True, queryset=Branch.objects.filter(is_active=True).order_by('branch_code'),empty_label="-Select branch-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'branch'}))
    
    daycare_incharge = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Incharge Name' }))
    
    daycare_contact_number = forms.CharField(max_length=10, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Mobile Number' }))

    daycare_contact_mobile_number = forms.CharField(max_length=10, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Contact Number' }))
    
    is_active = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    
    
    class Meta:
        model = DayCare
        fields = ('daycare_code','daycare_name','branch','daycare_incharge','daycare_contact_number','daycare_contact_mobile_number','is_active')  


class CreateDiscountForm(forms.ModelForm):
    discount_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Code','readonly': 'readonly' }))
    
    discount_name = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Discount Name' }))
    
    discount_rate = forms.CharField(max_length=10, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Discount rate' }))
    
    class Meta:
        model = Discount
        fields = ('discount_code','discount_name','discount_rate') 



class CreateEnrollmentForm(forms.ModelForm):

    enrollment_code = forms.CharField(max_length=250, required=True,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control','placeholder': 'Center Code','readonly': 'readonly' }))
    
    enrollment_date = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'required': 'true', 'id': 'effective_from', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Enrolment Date'}))
    child = forms.ModelChoiceField(required=True, queryset=Child.objects.filter(is_active=True,is_enrolled=False).order_by('admission_number'),empty_label="-Select child-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'child'}))
    
    branch = forms.ModelChoiceField(required=True, queryset=Branch.objects.filter(is_active=True).order_by('branch_code'),empty_label="-Select branch-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'branch'}))
    
    # dayCare = forms.ModelChoiceField(required=True, queryset=DayCare.objects.filter(is_active=True,branch=0).order_by('daycare_code'),empty_label="-Select daycare-",
    #                                 widget=forms.Select(
    #                                     attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'dayCare'}))

    dayCare = forms.CharField(max_length=250,required=True,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Daycare center','list': 'branches'}))

    normal_package = forms.ModelChoiceField(required=True, queryset=Package.objects.filter(is_active=True,is_holiday_package=False).order_by('package_code'),empty_label="-Select normal package-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'normal_package'}))
    
    holiday_package = forms.ModelChoiceField(required=True, queryset=Package.objects.filter(is_active=True,is_holiday_package=True).order_by('package_code'),empty_label="-Select holiday package-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'package'}))
    
    discount = forms.ModelChoiceField(required=False,queryset=Discount.objects.filter(is_active=True,status="Approved").order_by('discount_code'),empty_label="-Select discounts-",
                                    widget=forms.Select(
                                        attrs={'class': 'form-control', 'placeholder': 'Base Rate','id': 'discount'}))
    recipt_number = forms.CharField(required=False,max_length=250, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Receipt Number'}))
    
    class Meta:
        model = ChildEnrollment
        fields = ('enrollment_code','enrollment_date','child','branch','dayCare','normal_package','holiday_package','discount','recipt_number')  



class CreateCheckInForm(forms.ModelForm):
                                   
    child = forms.CharField(max_length=250,required=True,widget=forms.TextInput(attrs={'class':'form-control','placeholder':'Child','list': 'children'}))

    date_logged = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'required': 'true', 'id': 'date_logged', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'Date'}))
    
    
    time_logged = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'autocomplete': 'off','id':'time_logged','class': 'form-control','placeholder': 'Time',
                                                                             'required': 'required'}))
    
    
    class Meta:
        model = AttendanceLog
        fields = ('date_logged','time_logged') 




class SearchForm(forms.Form):
    from_date = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control', 'id': 'from_date', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'From date'}))
    
    to_date = forms.DateField(required=True, widget=MyDateInput(
        attrs={'class': 'form-control','id': 'to_date', 'data-provider': 'flatpickr',
               'data-date-format': 'Y-m-d', 'placeholder': 'To date'}))