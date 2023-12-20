from django.shortcuts import render
from .models import Child

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, response
from django.contrib.auth import authenticate, login, logout

from django.http import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils.http import url_has_allowed_host_and_scheme

import datetime

from decimal import Decimal
from django.db import transaction

from .models import Child, Package, Rates, ExtraCharges,RateHistory
from .forms import CreateChildForm, UpdateChildForm, CreateRatesForm,CreateExtraChargesForm, \
                    UpdateRatesForm,CreateRateHistoryForm,UpdateExtraChargesForm,CreatePackagesForm


#   This method 
@login_required
def index(request):
    UserName = request.user.username
    return render(request, "../templates/base.html", {"UserName": UserName})


def UserLogOut(request):
    logout(request)
    return redirect("core:home")


def UserLogin(request):
    username = password = ""
    try:
        if request.method == "POST":
            username = request.POST.get("username")
            password = request.POST.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)

                    next_url = request.POST.get("next", "")
                    if url_has_allowed_host_and_scheme(next_url, allowed_hosts=request.get_host()):
                        return HttpResponseRedirect(next_url)
                    else:
                        # Handle invalid or unsafe redirect URLs
                        return redirect("")  # Redirect to a default URL or homepage
                
                   
                        
            else:
                messages.error(
                    request,
                    "Invalid user credentials.Please check your username and password.",
                )
        

    except Exception as e:
        messages.error(request, e)
    
    return render(request, "../templates/login.html")


@login_required
def getChildJson(reuest):
    chilList = list(
        Child.objects.all().values(
            "id",
            "admission_number",
            "child_first_name",
            "child_last_name",
            "admission_date",
            "fathers_contact_number",
            "mothers_contact_number",
            "resident_contact_number",
            "is_polymath_student",
            "is_active",
        )
    )

    return JsonResponse(chilList, safe=False)


@login_required
def getChild(request):
    # clearing the session form the system. so the New id will be facilitated
    request.session["child_id"] = None
    request.session.modified = True

    # Child is defined by 'D' + next Id in the Table
    try:
        # trying to retrive the next primaryKey
        nextId = Child.objects.all().count()
        nextId += 1
    except:
        nextId = 1  # if the next ID is null define the record as the first

    child_form = CreateChildForm(
        initial={"admission_number": "D" + str(nextId)}
    )  # creating the form with the admission ID

    return render(
        request,
        "../templates/child.html",
        {"form": child_form, "UserName": request.user.username},
    )


@login_required
def getChildbyID(request, pk):
    try:
        child_form = None
        objChild = get_object_or_404(Child, pk=pk)
        if objChild is not None:
            child_form = UpdateChildForm(instance=objChild)

    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/childUpdate.html", {"formU": child_form}
    )


@login_required
def createChild(request):
    try:
        if request.method == "POST":
            # capturing the variables with data
            admission_number = request.POST.get("admission_number")
            child_first_name = request.POST.get("child_first_name")
            child_last_name = request.POST.get("child_last_name")
            date_of_birth = request.POST.get("date_of_birth")
            fathers_name = request.POST.get("fathers_name")
            fathers_contact_number = request.POST.get("fathers_contact_number")
            fathers_whatsapp_number = request.POST.get("fathers_whatsapp_number")
            mothers_name = request.POST.get("mothers_name")
            mothers_contact_number = request.POST.get("mothers_contact_number")
            mothers_whatsapp_number = request.POST.get("mothers_whatsapp_number")
            resident_contact_number = request.POST.get("resident_contact_number")
            address_line1 = request.POST.get("address_line1")
            address_line2 = request.POST.get("address_line2")
            address_line3 = request.POST.get("address_line3")
            email_address = request.POST.get("email_address")
            is_polymath_student = request.POST.get("is_polymath_student")
            recipt_number = request.POST.get("recipt_number")
            admission_date = request.POST.get("admission_date")
            is_active = request.POST.get("is_active")
            if is_polymath_student == "on":
                is_polymath_student = True
            else:
                is_polymath_student = False

            if is_active == "on":
                is_active = True
            else:
                is_active = False

        if request.POST.get("admission_number") is not None:
            objChild = Child.objects.get(
                admission_number=request.POST.get("admission_number")
            )
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
            date_of_birth=datetime.datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
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
            admission_date=datetime.datetime.strptime(
                admission_date, "%Y-%m-%d"
            ).date(),
            is_active=is_active,
        )
        objChild.save()
        messages.success(request, "Child details saved.")

    return redirect("core:view_child")


@login_required
def deleteChild(request, pk):
    try:
        objChild = get_object_or_404(Child, pk=pk)

        if objChild is not None:
            objChild.is_active = False
            objChild.user_updated = request.user.username
            objChild.save()

    except Exception as e:
        messages.error(request, e)


@login_required
def getRatesJs(reuest):
    rateList = list(
        Rates.objects.filter(is_active=1).values(
            "id",
            "rate_name",
            "is_holiday_rate",
            "is_active",
        )
    )

    return JsonResponse(rateList, safe=False)

@login_required
def getRates(request):
    if request.method == "GET":
        settings_form = CreateRatesForm()
    
    else:    
        objSettings = Rates.objects.all().first()
        settings_form = CreateRatesForm(instance=objSettings)

    return render(
        request,
        "../templates/ratesettings.html",
        {
            "form": settings_form,
            "UserName": request.user.username,
        },
    )

@login_required
def getRateByID(request, pk):
    try:
        rate_form = None
        objRate = get_object_or_404(Rates, pk=pk)
        
        if objRate is not None:
            rate_form = UpdateRatesForm(instance=objRate)

    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/rateUpdate.html", {"formU": rate_form}
    )
    


@login_required
def saveRates(request):
    try:
        if request.method == "POST":
            form = UpdateRatesForm(request.POST)
            objRates= form.save(commit=False)
            # capturing the variables with data
            
            rate_name = request.POST.get("rate_name")
            is_holiday_rate = request.POST.get("is_holiday_rate")
            is_active = request.POST.get("is_active")

            if is_holiday_rate == "on":
                is_holiday_rate = True
            else:
                is_holiday_rate = False


            if request.POST.get("id") is not None:
                objRate = Rates.objects.get(
                    id=request.POST.get("id")
                )
                if objRate is not None:

                    objRate.rate_name = rate_name
                    objRate.is_holiday_rate = is_holiday_rate
                    objRate.is_active = True
                    objRate.user_updated =request.user.username
                    objRate.date_updated = datetime.datetime.now()
                    objRate.save()
                    messages.success(request, "Rate details updated.")
            else:
                objRate = Rates(
                rate_name = rate_name,
                is_holiday_rate = is_holiday_rate,
                is_active = True,
                user_created=request.user.username)
                objRate.save()
                messages.success(request, "Rate details saved.")

    except Exception as e:
        messages.error(request, e)
    return redirect("core:view_rates")        
    

@login_required
def getAdditionalRates(request):
    if request.method == "GET":
        if not request.session.get('base_rate_id') is None:
            form = CreateExtraChargesForm(initial={'base_rate': request.session.get('base_rate_id')})
        else:
            form = CreateExtraChargesForm()
    return render(
        request,
        "../templates/additionalrates.html",
        {
            "form": form,
            "UserName": request.user.username,
        },
    )
    
    
@login_required
def getAdditionalRatesJs(request):
    additionalRatesList = None
    if request.GET.get('base_rate_id') is not None:
        id = request.GET.get('base_rate_id')
        additionalRatesList = list(
            ExtraCharges.objects.filter(base_rate_id=id, is_active=True).values(
            "id",
            "base_rate", 
            "from_time",
            "to_time",
            "extra_rate",
            "effective_from",
            "effective_to",
            "is_active",
            )
    )
        for i,n in enumerate(additionalRatesList):
            if n['effective_to']==None:
                additionalRatesList[i]["effective_to"] ="-"
    return JsonResponse(additionalRatesList, safe=False)


@login_required
def getAdditionalRateById(request):
    try:
        rate_form = None
        if request.GET.get('rate_id') is not None:
            objRate = get_object_or_404(ExtraCharges, pk=request.GET.get('rate_id'))
            request.session['id'] = objRate.id
            request.session.modified = True
        
        if objRate is not None:
            rate_form = UpdateExtraChargesForm(instance=objRate)

    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/extrarateupdate.html", {"formU": rate_form}
    )
    


@login_required
def saveAdditionalRates(request):
    request.session['base_rate_id'] = None
    request.session.modified = True
    if request.method == "POST":
        form = CreateExtraChargesForm(request.POST)

        if form.is_valid():
           
            objAdditionalRates= form.save(commit=False)
            objExtraChargestchek = ExtraCharges.objects.filter(base_rate=objAdditionalRates.base_rate.id,
                                                               from_time=objAdditionalRates.from_time,
                                                               to_time=objAdditionalRates.to_time).first()
            
            if objExtraChargestchek is not None:
                print(objExtraChargestchek.id)
                messages.error(request,"This time slot is already defined")
            else:
                objAdditionalRates.user_created = request.user.username
                request.session['base_rate_id'] = objAdditionalRates.base_rate.id
                request.session.modified = True
                objAdditionalRates.save()
                messages.success(request, "Additional rate details saved.")
        else:
            messages.error(request,form.errors)
                
    return redirect("core:view_additional_rates") 


@login_required
def updateAdditionalRates(request):
    base_rate_id =None
    try:
        if request.method == "POST":
            form = UpdateExtraChargesForm(request.POST)
            if request.session['id'] is not None:
                objAdditionalRates = ExtraCharges.objects.get(pk=request.session['id'])
                if objAdditionalRates is not None:
                    with transaction.atomic():
                        base_rate_id =objAdditionalRates.base_rate.id
                        objAdditionalRates.is_active =False
                        objAdditionalRates.user_updated =request.user.username
                        objAdditionalRates.save()
                        if form.is_valid():
                            objNewAdditionalRates= form.save(commit=False)
                            print(objNewAdditionalRates)
                            objNewAdditionalRates.base_rate = Rates.objects.get(pk=base_rate_id)
                            objNewAdditionalRates.user_created = request.user.username
                            objNewAdditionalRates.save()
                            messages.success(request, "Additional rate details Updated.")
                        else:
                            messages.error(request,form.errors)

                else:
                    messages.error(request,form.errors)
            else:
                    messages.error(request,"No rate found")
    except Exception as e:
        messages.error(request, e)

    return redirect("core:view_additional_rates") 





# This method will save the Rate history for a give base rate. 
# Operation :- get the base rate id. Check for the validity and retrive the previous rates and set the effective_to date to effective_date
#if not previous rates are found, Create a new rate entry.
@login_required
@transaction.atomic
def saveBaseRate(request):
    try:
        objRateHistory = None
        standard_hourly_rate = request.POST.get("standard_hourly_rate")
        effective_from = request.POST.get("effective_from")

        if request.method == "POST":
            if request.POST.get("rate_id") is not None:
                oldRate = RateHistory.objects.filter(
                        rate_id=request.POST.get("rate_id"),is_active=True
                    ).first() 
                with transaction.atomic():
                    if oldRate is not None:
                        if oldRate.effective_to is None and oldRate.is_active == True:
                            oldRate.effective_to =datetime.datetime.strptime(effective_from, "%Y-%m-%d").date()
                            oldRate.is_active = False
                            oldRate.user_updated = request.user.username
                            oldRate.date_updated = datetime.datetime.now
                            oldRate.save()
                            objRateHistory = RateHistory(
                            rate =  Rates.objects.get(pk=request.POST.get("rate_id")),
                            standard_hourly_rate = standard_hourly_rate,
                            effective_from =  datetime.datetime.strptime(effective_from, "%Y-%m-%d").date(),
                            is_active = True,
                            user_created = request.user.username)
                            objRateHistory.save()
                            messages.success(request, "Rate details updated.")
                    else:
                            objRateHistory = RateHistory(
                            rate =  Rates.objects.get(pk=request.POST.get("rate_id")),
                            standard_hourly_rate = standard_hourly_rate,
                            effective_from =  datetime.datetime.strptime(effective_from, "%Y-%m-%d").date(),
                            is_active = True,
                            user_created = request.user.username)
                            objRateHistory.save()
                            messages.success(request, "Rate details saved.")
            else:
                messages.error(request, "Rate ")
    except Exception as e:
        messages.error(request, e)
    return redirect("core:view_rates")   


@login_required
def getRateHistoryById(request,pk):
    baseRateName = None
    if request.GET.get('rate_id') is not None:
        id = request.GET.get('rate_id')
        objBaseRate = Rates.objects.get(pk=id)
        if objBaseRate is not None:
            baseRateName = objBaseRate.rate_name
            id = objBaseRate.id
    history_form = CreateRateHistoryForm()   
    return render(request, "../templates/partials/addratesforbase.html", {"formU": history_form, "baseRateName":baseRateName,"id":id})


@login_required
def getRatesforRatesJs(request):
   if request.GET.get('rate_id') is not None:
        id = request.GET.get('rate_id')
        ratesList = list(
            RateHistory.objects.filter(rate_id=id).values(
            "id",
            "standard_hourly_rate",
            "effective_from",
            "effective_to",
            "is_active",
            ))
        for i,n in enumerate(ratesList):
            if n['effective_to']==None:
                ratesList[i]["effective_to"] ="-"
            if n['is_active'] == True:
                ratesList[i]["is_active"] ="Active"
            else:
                 ratesList[i]["is_active"] ="Inactive"

    
   return JsonResponse(ratesList, safe=False)


@login_required
def getPackages(request):
    if request.method == "GET":
        package_form = CreatePackagesForm()
    
    

    return render(
        request,
        "../templates/packages.html",
        {
            "form": package_form,
            "UserName": request.user.username,
        },
    )


@login_required
def getPackagesJs(request):
   if request.method == "GET":
        packageList = list(
            Package.objects.all().values(
            "id",
            "package_type",
            "base_rate",
            "package_code",
            "package_name",
            "from_time",
            "to_time",
            "no_hours", 
            "no_days_week",
            "no_days_months",
            "is_holiday_package",
            ))
        for i,n in enumerate(packageList):
            packageList[i]["base_rate"] = Rates.objects.get(pk=packageList[i]["base_rate"])
            if n['is_holiday_package'] == True:
                packageList[i]["is_holiday_package"] ="Yes"
            else:
                 packageList[i]["is_holiday_package"] ="No"

    
   return JsonResponse(packageList, safe=False)