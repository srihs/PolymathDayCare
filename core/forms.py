from django import forms
from django.forms import ImageField
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from django.core.validators import MinValueValidator
from .models import Child, Rates, AdditionalCharges
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
    recipt_number = forms.CharField(required=False,max_length=250, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Receipt Number'}))
    admission_date = forms.DateField(required=True, widget=MyDateInput(attrs={'class': 'form-control',
                                                                              'id': 'admission_date',
                                                                              'placeholder': 'Admission Date',
                                                                              'required': 'required',
                                                                              'data-provider': 'flatpickr',
                                                                                      'data-date-format': 'Y-m-d'}))
    is_active = forms.BooleanField(required=False,widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox', 'checked': 'checked'}))

    class Meta:
        model = Child
        fields = ('admission_number', 'child_first_name', 'admission_number', 'child_first_name', 'child_last_name',
                          'date_of_birth', 'fathers_name', 'fathers_contact_number', 'fathers_whatsapp_number', 'mothers_name',
                          'mothers_contact_number', 'mothers_whatsapp_number', 'resident_contact_number', 'address_line1',
                          'address_line2', 'address_line3', 'email_address', 'is_polymath_student', 'recipt_number','is_active')


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
    recipt_number = forms.CharField(required=False, max_length=250, widget=forms.TextInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'placeholder': 'Receipt Number'}))
    admission_date = forms.DateField(required=True, widget=MyDateInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true', 'id': 'admission_date', 'data-provider': 'flatpickr',
               'data-date-format': '%Y-%m-%d', 'placeholder': 'Admission Date'}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(
        attrs={'class': 'form-check-input', 'type': 'checkbox'}))

    class Meta:
        model = Child
        fields = ('admission_number', 'child_first_name', 'admission_date', 'child_first_name', 'child_last_name',
                  'date_of_birth', 'fathers_name', 'fathers_contact_number', 'fathers_whatsapp_number', 'mothers_name',
                  'mothers_contact_number', 'mothers_whatsapp_number', 'resident_contact_number', 'address_line1',
                  'address_line2', 'address_line3', 'email_address', 'is_polymath_student', 'recipt_number',
                  'is_active')


class SettingsForm(forms.ModelForm):
    rate_name = forms.CharField(max_length=250, required=False,
                                    widget=forms.TextInput(
                                        attrs={'class': 'form-control', 'placeholder': 'Rate name'}))
    
    standard_hourly_rate = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Rate'}))
    
    is_holiday_rate = forms.BooleanField(required=False, 
                                         widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'type': 'checkbox'}))
    class Meta:
        model = Rates
        fields = ('rate_name','standard_hourly_rate','is_holiday_rate')
    
class AdditionalChargesForm(forms.ModelForm):
    extra_hours_standard_rate_first_hour =forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 1st hour'}))
    
    extra_hours_standard_rate_Second_hour =forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 2nd hour'}))
    
    extra_hours_standard_rate_third_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 3rd hour'}))
    
    extra_hours_standard_rate_fourth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 4th hour'}))
    
    extra_hours_standard_rate_fifth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 5th hour'}))
    
    extra_hours_standard_rate_sixth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 6th hour'}))
    
    extra_hours_standard_rate_seventh_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 7th hour'}))
    
    extra_hours_standard_rate_eighth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 8th hour'}))
    
    extra_hours_standard_rate_nineth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 9th hour'}))
    
    extra_hours_standard_rate_tenth_hour = forms.DecimalField(max_digits=15,
                                            decimal_places=2,
                                            validators=[MinValueValidator(Decimal('0.01'))],
                                            required=True,
                                            widget=forms.NumberInput(attrs={'class': 'form-control','placeholder': 'Extra rate 10th hour'}))
    
    effective_from = forms.DateField(required=True, widget=MyDateInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true', 'id': 'admission_date', 'data-provider': 'flatpickr',
               'data-date-format': '%Y-%m-%d', 'placeholder': 'Admission Date'}))
    effective_to = forms.DateField(required=True, widget=MyDateInput(
        attrs={'readonly': 'readonly','class': 'form-control', 'required': 'true', 'id': 'admission_date', 'data-provider': 'flatpickr',
               'data-date-format': '%Y-%m-%d', 'placeholder': 'Admission Date'}))

class Meta:
        model = AdditionalCharges
        fields = ('extra_hours_standard_rate_first_hour','extra_hours_standard_rate_Second_hour',
                  'extra_hours_standard_rate_third_hour','extra_hours_standard_rate_fourth_hour',
                  'extra_hours_standard_rate_fifth_hour','extra_hours_standard_rate_sixth_hour',
                  'extra_hours_standard_rate_seventh_hour','extra_hours_standard_rate_eighth_hour',
                  'extra_hours_standard_rate_nineth_hour','extra_hours_standard_rate_tenth_hour')