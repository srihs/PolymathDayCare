from django import forms
from django.forms import ImageField
from django.db import models
from django.contrib.admin.widgets import AdminDateWidget
from .models import Child


class MyDateInput(forms.widgets.DateInput):
    input_type = 'date'

choices = ((1, 'Polymath Student'),)

class CreateChildForm(forms.ModelForm):
    admission_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    child_first_name = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    child_last_name = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    date_of_birth = forms.DateField(required=True, widget=MyDateInput(attrs={'class':'form-control','placeholder':'Date of birth', 'id': 'dob'}))
    fathers_name = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    fathers_contact_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    fathers_whatsapp_number =forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    mothers_name = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    mothers_contact_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    mothers_whatsapp_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    resident_contact_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    address_line1 = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    address_line2 = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    address_line3 = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))
    email_address =  forms.CharField(max_length=50, required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'id': 'email'}))
    is_polymath_student =forms.ChoiceField(choices =choices,required=True,widget=forms.RadioSelect(attrs={'class':'form-check-label'}))
    recipt_number = forms.CharField(max_length=250,required=True, widget=forms.TextInput(attrs={'class':'form-control'}))

    class Meta:
        model = Child
        fields = ('admission_number','child_first_name','admission_number','child_first_name','child_last_name',
                  'date_of_birth','fathers_name','fathers_contact_number','fathers_whatsapp_number','mothers_name',
                  'mothers_contact_number','mothers_whatsapp_number','resident_contact_number','address_line1','address_line2',
                  'address_line3','email_address','is_polymath_student','recipt_number')

