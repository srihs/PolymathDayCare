from django import forms
from django.forms import ImageField
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from django.core.validators import MinValueValidator
from .models import Child, Rates, ExtraCharges,RateHistory
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
                                                                             'data-provider': 'flatpickr','required': 'true','disabled': 'true'}))
    to_time = forms.TimeField(required=True, widget=forms.TimeInput(attrs={'id':'to_time','class': 'form-control','placeholder': 'To Time','required': 'true','disabled': 'true'}))
    
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