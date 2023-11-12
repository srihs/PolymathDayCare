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


# Create your views here.
@login_required(login_url='/login/')
def index(request):
    return render(request, '../templates/base.html')

def UserLogin(request):
    print("--In Login--")
    username = password = ''
    if request.method == 'POST':
        print("--In Post--")
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(username)
        print(password)
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
            return HttpResponseRedirect(request.POST.get('next'))

    return render(request, '../templates/login.html')

@login_required(login_url='/login/')
def getChild(request):
    print('---in GET---')
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
    print(nextId)
    child_form = CreateChildForm(initial={'admission_number': 'D' + str(nextId),'admission_date': datetime.datetime.now().date().strftime('%m/%d/%Y')})  # creating the form with the admission ID
    print(datetime.datetime.now().date().strftime('%m/%d/%Y'))


    return render(request, '../templates/child.html', {'form': child_form})
