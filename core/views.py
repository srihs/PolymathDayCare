from django.shortcuts import render
from .models import Child
from .forms import CreateChildForm
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, response
from django.contrib.auth import authenticate, login
from django.http import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import datetime

from .models import Child


# Create your views here.
@login_required(login_url='login/')
def index(request):
    return render(request, '../templates/base.html')


def UserLogin(request):
    username = password = ''
    try:
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')
            print(request.POST.get('next'))
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
    childrenList = Child.objects.all()
    child_form = CreateChildForm(initial={'admission_number': 'D' + str(nextId),
                                          'admission_date': datetime.datetime.now().date().strftime(
                                              '%m/%d/%Y')})  # creating the form with the admission ID
    print(datetime.datetime.now().date().strftime('%m/%d/%Y'))

    return render(request, '../templates/child.html', {'form': child_form,'childrenList':childrenList})


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

        if is_polymath_student == 'on':
            is_polymath_student = True
        else:
            is_polymath_student = False

        if 'child_id' in request.session and request.session['child_id'] is not None:
            # Editing the record
            objChild = get_object_or_404(Child, pk=request.session['child_id'])
            if objChild is not None:
                objChild.child_first_name = request.POST.get('child_first_name')
            objChild.child_last_name = request.POST.get('child_last_name')
            objChild.date_of_birth = request.POST.get('date_of_birth')
            objChild.fathers_name = request.POST.get('fathers_name')
            objChild.fathers_contact_number = request.POST.get('fathers_contact_number')
            objChild.fathers_whatsapp_number = request.POST.get('fathers_whatsapp_number')
            objChild.mothers_name = request.POST.get('mothers_name')
            objChild.mothers_contact_number = request.POST.get('mothers_contact_number')
            objChild.mothers_whatsapp_number = request.POST.get('mothers_whatsapp_number')
            objChild.resident_contact_number = request.POST.get('resident_contact_number')
            objChild.address_line1 = request.POST.get('address_line1')
            objChild.address_line2 = request.POST.get('address_line2')
            objChild.address_line3 = request.POST.get('address_line3')
            objChild.email_address = request.POST.get('email_address')
            objChild.is_polymath_student = request.POST.get('is_polymath_student')
            objChild.recipt_number = request.POST.get('recipt_number')
            objChild.admission_date = request.POST.get('admission_date')
            objChild.user_updated = request.user.username
            objChild.save()
            messages.success(request, "Child details updated.")
        else:
            # New Child
            print('-in Create-')
            objChild = Child(
                admission_number=admission_number,
                child_first_name=child_first_name,
                child_last_name=child_last_name,
                date_of_birth= datetime.datetime.strptime(date_of_birth, '%Y-%m-%d').date(),
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
                user_created= request.user.username,
                admission_date=datetime.datetime.strptime(admission_date,'%Y-%m-%d').date())
            objChild.save()
            messages.success(request, "Child details saved.")
    except Exception as e:
        messages.error(request, e)

    return redirect('core:view_child')
