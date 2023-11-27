from django.shortcuts import render
from .models import Child

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, response
from django.contrib.auth import authenticate, login, logout

from django.http import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
import datetime

from .models import Child,Package,Rates
from .forms import CreateChildForm, UpdateChildForm#, SettingsForm



@login_required(login_url='login/')
def index(request):
    UserName =request.user.username
    return render(request, '../templates/base.html',{'UserName':UserName})


def UserLogOut(request):
    logout(request)
    return redirect('core:login')
    

def UserLogin(request):
    username = password = ''
    try:
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return HttpResponseRedirect(request.POST.get('next'))
            else:
                messages.error(request, "Invalid user credentials.Please check your username and password.")
        return render(request, '../templates/login.html')

    except Exception as e:
        messages.error(request, e)


@login_required(login_url='login/')
def getChildJson(reuest):
    chilList = list(Child.objects.all() \
        .values(
        'id',
        'admission_number',
        'child_first_name',
        'child_last_name',
        'admission_date',
        'fathers_contact_number',
        'mothers_contact_number',
        'resident_contact_number',
        'is_polymath_student',
        'is_active'
    ))

    return JsonResponse(chilList, safe=False)


@login_required(login_url='/login/')
def getChild(request):
    # clearing the session form the system. so the New id will be facilitated
    request.session['child_id'] = None
    request.session.modified = True

    # Child is defined by 'D' + next Id in the Table
    try:
        # trying to retrive the next primaryKey
        nextId = Child.objects.all().count()
        nextId += 1
    except:
        nextId = 1  # if the next ID is null define the record as the first

    child_form = CreateChildForm(initial={'admission_number': 'D' + str(nextId)})  # creating the form with the admission ID
    

    return render(request, '../templates/child.html', {'form': child_form,'UserName':request.user.username})

@login_required(login_url='/login/')
def getChildbyID(request, pk):
    try:

        child_form = None
        objChild = get_object_or_404(Child, pk=pk)
        if objChild is not None:
            child_form = UpdateChildForm(instance=objChild)

    except Exception as e:
        messages.error(request, e)
    return render(request, '../templates/partials/childUpdate.html', {'formU': child_form})


@login_required(login_url='/login/')
def createChild(request):
    try:
        if request.method == 'POST':
            # capturing the variables with data
            admission_number = request.POST.get('admission_number')
            child_first_name = request.POST.get('child_first_name')
            child_last_name = request.POST.get('child_last_name')
            date_of_birth = request.POST.get('date_of_birth')
            fathers_name = request.POST.get('fathers_name')
            fathers_contact_number = request.POST.get('fathers_contact_number')
            fathers_whatsapp_number = request.POST.get('fathers_whatsapp_number')
            mothers_name = request.POST.get('mothers_name')
            mothers_contact_number = request.POST.get('mothers_contact_number')
            mothers_whatsapp_number = request.POST.get('mothers_whatsapp_number')
            resident_contact_number = request.POST.get('resident_contact_number')
            address_line1 = request.POST.get('address_line1')
            address_line2 = request.POST.get('address_line2')
            address_line3 = request.POST.get('address_line3')
            email_address = request.POST.get('email_address')
            is_polymath_student = request.POST.get('is_polymath_student')
            recipt_number = request.POST.get('recipt_number')
            admission_date = request.POST.get('admission_date')
            is_active = request.POST.get('is_active')
            if is_polymath_student == 'on':
                is_polymath_student = True
            else:
                is_polymath_student = False

            if is_active == 'on':
                is_active = True
            else:
                is_active = False

        if request.POST.get('admission_number') is not None:
            objChild = Child.objects.get(admission_number=request.POST.get('admission_number'))
            if objChild is not None:
                objChild.fathers_contact_number = int(fathers_contact_number)
                objChild.fathers_whatsapp_number = int(fathers_whatsapp_number)
                objChild.mothers_contact_number = int(mothers_contact_number)
                objChild.mothers_whatsapp_number = int(mothers_whatsapp_number)
                objChild.address_line1 = address_line1
                objChild.address_line2 = address_line2
                objChild.address_line3 = address_line3
                objChild.email_address = email_address
                objChild.is_polymath_student = is_polymath_student
                objChild.user_updated = request.user.username
                objChild.is_active = is_active
                objChild.save()
                messages.success(request, "Child details updated.")
    except Exception as e:
        
        objChild = Child(
            admission_number=admission_number,
            child_first_name=child_first_name,
            child_last_name=child_last_name,
            date_of_birth=datetime.datetime.strptime(date_of_birth, '%Y-%m-%d').date(),
            fathers_name=fathers_name,
            fathers_contact_number=fathers_contact_number,
            fathers_whatsapp_number=fathers_whatsapp_number,
            mothers_name=mothers_name,
            mothers_contact_number=mothers_contact_number,
            mothers_whatsapp_number=mothers_whatsapp_number,
            resident_contact_number=resident_contact_number,
            address_line1=address_line1,
            address_line2=address_line2,
            address_line3=address_line3,
            email_address=email_address,
            is_polymath_student=is_polymath_student,
            recipt_number=recipt_number,
            user_created=request.user.username,
            admission_date=datetime.datetime.strptime(admission_date, '%Y-%m-%d').date(),
            is_active=is_active)
        objChild.save()
        messages.success(request, "Child details saved.")

    return redirect('core:view_child')

@login_required(login_url='/login/')
def deleteChild(request, pk):
    try:
        objChild = get_object_or_404(Child, pk=pk)

        if objChild is not None:
            objChild.is_active = False
            objChild.user_updated = request.user.username
            objChild.save()
           
    except Exception as e:
        messages.error(request, e)



@login_required(login_url='login/')
def getPackagesJson(reuest):
    packagesList = list(Package.objects.all() \
        .values(
        'id',
        'admission_number',
        'child_first_name',
        'child_last_name',
        'admission_date',
        'fathers_contact_number',
        'mothers_contact_number',
        'resident_contact_number',
        'is_polymath_student',
        'is_active'
    ))

    return JsonResponse(chilList, safe=False)


def getSettings(request):
    
        objSettings = BaseRates.objects.all().first()
        settings_form = SettingsForm(instance=objSettings)  
            
        return render(request, '../templates/settings.html', {'form': settings_form,'UserName':request.user.username,'settings':objSettings})


def saveSettings(request):
    return true
    