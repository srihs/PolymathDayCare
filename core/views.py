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
from datetime import datetime, timedelta

from decimal import Decimal
from django.db import transaction
from django.core import serializers
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.views.decorators.http import require_POST

from .models import Child, Package, Rates, ExtraCharges,RateHistory, Branch,DayCare,ChildEnrollment,Discount

from .forms import CreateChildForm, UpdateChildForm, CreateRatesForm,CreateExtraChargesForm, \
                    UpdateRatesForm,CreateRateHistoryForm,UpdateExtraChargesForm,CreatePackagesForm, CreateBranchForm, \
                    CreateBranchForm, UpdateBranchForm, CreateDayCareForm, UpdateDayCareForm, CreateDiscountForm,\
                    CreateEnrollmentForm


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
        initial={"admission_number": "D0" + str(nextId)}
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
            date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
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
            user_created=request.user.username,
            admission_date=datetime.strptime(
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
def getRateAmountByIdJs(request):
     if request.method == "GET":
        print("in the method")
        print(request.session.get('base_rate_id'))
        if not request.GET.get('base_rate_id') is None:
            print("base ID is not Null")
            objRateHistory = RateHistory.objects.get(pk =request.GET.get('base_rate_id'),is_active=True)
            if objRateHistory is not None:
                if request.GET.get('no_hours') is not None and request.GET.get('no_days_months') is not None:
                    print(Decimal(request.GET.get('no_hours')))
                    print(Decimal(request.GET.get('no_days_months')))
                    print(objRateHistory.standard_hourly_rate)
                    total_package_amount = objRateHistory.standard_hourly_rate * Decimal(request.GET.get('no_hours')) * Decimal(request.GET.get('no_days_months'))

                    return JsonResponse("{:,.2f}".format(total_package_amount), safe=False)
            else:
                return JsonResponse(None,safe=False)
        return JsonResponse("000.00",safe=False)

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
                    objRate.date_updated = datetime.now()
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



def calculate_duration(request):
    # Get the values of "from_time" and "to_time" from the POST request
    from_time_str = request.GET.get('from_time')
    to_time_str = request.GET.get('to_time')
    print(from_time_str)
    print(to_time_str)
    print("Print is not working")


    try:
        # Convert the time strings to datetime objects
        from_time = datetime.strptime(from_time_str, '%H:%M')
        to_time = datetime.strptime(to_time_str, '%H:%M')

       # Calculate the duration
        duration_seconds = (to_time - from_time).seconds
        duration_hours = duration_seconds // 3600
        duration_minutes = (duration_seconds % 3600) // 60

        # Return the result as JSON
        return JsonResponse({'duration_hours': duration_hours, 'duration_minutes': duration_minutes})
    except ValueError:
        # Handle invalid time format
        return JsonResponse({'error': 'Invalid time format'}, status=400)
    except Exception as e:
        # Handle other exceptions
        return JsonResponse({'error': str(e)}, status=500)


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
                            oldRate.effective_to =datetime.strptime(effective_from, "%Y-%m-%d").date()
                            oldRate.is_active = False
                            oldRate.user_updated = request.user.username
                            oldRate.date_updated = datetime.now
                            oldRate.save()
                            objRateHistory = RateHistory(
                            rate =  Rates.objects.get(pk=request.POST.get("rate_id")),
                            standard_hourly_rate = standard_hourly_rate,
                            effective_from =  datetime.strptime(effective_from, "%Y-%m-%d").date(),
                            is_active = True,
                            user_created = request.user.username)
                            objRateHistory.save()
                            messages.success(request, "Rate details updated.")
                    else:
                            objRateHistory = RateHistory(
                            rate =  Rates.objects.get(pk=request.POST.get("rate_id")),
                            standard_hourly_rate = standard_hourly_rate,
                            effective_from =  datetime.strptime(effective_from, "%Y-%m-%d").date(),
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
def getRateHistoryById(request):
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
        try:
        # trying to retrive the next primaryKey
            nextId = Package.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        package_form = CreatePackagesForm(initial={'package_code': "PKG00" + str(nextId)})
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
            "package_code",
            "package_name",
            "from_time",
            "to_time",
            "no_hours",
            "no_days_week",
            "no_days_months",
            "is_holiday_package",
            "base_rate",
            ))

        for i,n in enumerate(packageList):
            # query =Rates.objects.filter(pk=packageList[i]["base_rate"])
            # packageList[i]["base_rate"] = serializers.serialize('json',query)

            if n['is_holiday_package']:
                packageList[i]["is_holiday_package"] ="Yes"

            else:
                 packageList[i]["is_holiday_package"] ="No"



   return JsonResponse(packageList, safe=False)

@login_required
def checkIfHolidayPackage(id):
    is_holiday =None

    objBaseRate = Rates.objects.get(pk=id)
    if objBaseRate.is_holiday_rate:
        is_holiday = True
    else:
        is_holiday = False

    return is_holiday


@login_required
def savePackage(request):
    if request.method == "POST":
        form = CreatePackagesForm(request.POST)
        if form.is_valid():
            objPackage= form.save(commit=False)

            objBaseRate = Rates.objects.get(pk = request.POST.get("base_rate"))

            objPackage.base_rate = objBaseRate
            objPackage.user_created = request.user.username

            is_holiday_package = objBaseRate.checkIfHolidayPackage()

            objPackage.is_holiday_package = is_holiday_package
            objPackage.save()
            messages.success(request, "Package details saved.")
        else:
            messages.error(request,form.errors)

    else:
        messages.error(request,"Something went wrong")

    return redirect("core:view_packages")


@login_required
def getBranches(request):
    if request.method == "GET":
        try:
        # trying to retrive the next primaryKey
            nextId = Branch.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        branch_form = CreateBranchForm(initial={'branch_code': "BRN00" + str(nextId)})

    return render(
        request,
        "../templates/branch.html",
        {
            "form": branch_form,
            "UserName": request.user.username,
        },
    )



@login_required
def getBranchesJs(request):
   if request.method == "GET":
        branchList = list(
            Branch.objects.all().values(
            "id",
            "branch_code",
            "branch_name",
            "branch_contact_person",
            "branch_contact_mobile_number",
            "branch_contact_number",
            "address_line1",
            "address_line2",
            "address_line3",
            "is_active"
            ))


   return JsonResponse(branchList, safe=False)



@login_required
def saveBranch(request):
    if request.method == "POST":
        id = request.POST.get("id")
        branch_code = request.POST.get("branch_code")
        branch_name = request.POST.get("branch_name")
        branch_contact_person = request.POST.get("branch_contact_person")
        branch_contact_mobile_number = request.POST.get("branch_contact_mobile_number")
        branch_contact_number = request.POST.get("branch_contact_number")
        address_line1 = request.POST.get("address_line1")
        address_line2 = request.POST.get("address_line2")
        address_line3 = request.POST.get("address_line3")
        is_active = request.POST.get("is_active")


        if branch_code is not None:
                objBranch = Branch.objects.filter(
                    branch_code=branch_code
                ).first()
                print(objBranch)
                if objBranch is not None:
                    objBranch.branch_code = branch_code
                    objBranch.branch_name = branch_name
                    objBranch.branch_contact_person = branch_contact_person
                    objBranch.branch_contact_mobile_number = branch_contact_mobile_number
                    objBranch.branch_contact_number = branch_contact_number
                    objBranch.address_line1 = address_line1
                    objBranch.address_line2 = address_line2
                    objBranch.address_line3 = address_line3

                    if is_active == "on":
                        is_active = True
                    else:
                        is_active = False

                    objBranch.is_active = is_active

                    objBranch.user_updated = request.user.username
                    objBranch.date_updated = datetime.now()
                    objBranch.save()

                    messages.success(request, "Branch details updated.")
                else:
                    form = CreateBranchForm(request.POST)
                    if form.is_valid():
                        objBranch = form.save(commit=False)
                        objBranch.user_created = request.user.username
                        objBranch.save()
                        messages.success(request, "Branch details saved.")
                    else:
                        messages.error(request, form.errors)

    return redirect("core:view_branches")

@login_required
def getBranchForUpdateById(request,pk):
    try:
        updateBranch_form = None
        objBranch = get_object_or_404(Branch, pk=pk)

        if objBranch is not None:
            updateBranch_form = UpdateBranchForm(instance=objBranch)

        print(objBranch.id)

    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/branchUpdate.html", {"form": updateBranch_form}
    )


@login_required
def getDaycareCenters(request):
    if request.method == "GET":
        try:
        # trying to retrive the next primaryKey
            nextId = DayCare.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        branch_form = CreateDayCareForm(initial={'daycare_code': "DC00" + str(nextId)})

    return render(
        request,
        "../templates/dccenters.html",
        {
            "form": branch_form,
            "UserName": request.user.username,
        },
    )


@login_required
def saveDayCareCenter(request):
     if request.method == "POST":
        print("In the method")
        daycare_code = request.POST.get("daycare_code")
        daycare_name = request.POST.get("daycare_name")
        branch = request.POST.get("branch")
        daycare_incharge = request.POST.get("daycare_incharge")
        daycare_contact_mobile_number = request.POST.get("daycare_contact_mobile_number")
        daycare_contact_number = request.POST.get("daycare_contact_number")
        is_active = request.POST.get("is_active")
        try:
                if daycare_code is not None:
                    objDayCare = DayCare.objects.get(
                        daycare_code=daycare_code
                    )
                    if objDayCare is not None:
                        objDayCare.daycare_code = daycare_code
                        objDayCare.daycare_name = daycare_name
                        objDayCare.branch = branch
                        objDayCare.daycare_incharge = daycare_incharge
                        objDayCare.daycare_contact_mobile_number = daycare_contact_mobile_number
                        objDayCare.daycare_contact_number = daycare_contact_number
                        
                        if is_active == "on":
                            is_active = True
                        else:
                            is_active = False

                        objDayCare.is_active = is_active

                        objDayCare.user_updated = request.user.username
                        objDayCare.date_updated = datetime.now()
                        objDayCare.save()
                        messages.success(request, "Center details updated.")

        except :
            form = CreateDayCareForm(request.POST)
            if form.is_valid():
                objDayCare = form.save(commit=False)
                objDayCare.user_created = request.user.username
                objDayCare.save()
                messages.success(request, "Center details saved.")
            else:
                messages.error(request, form.errors)
                    
    
            return redirect("core:view_centers")


@login_required
def getDayCareCentersJs(request):
   if request.method == "GET":
        daycareList = list(
            DayCare.objects.all().values(
            "id",
            "daycare_code",
            "daycare_name",
            "daycare_incharge",
            "daycare_contact_number",
            "daycare_contact_mobile_number",
            "branch",
            "is_active",
            ))

        for i,n in enumerate(daycareList):
            if n['is_active']:
                daycareList[i]["is_active"] ="Yes"
            else:
                 daycareList[i]["is_active"] ="No"
            
   return JsonResponse(daycareList, safe=False)


@login_required
def getDayCareCenterNamebyIdJs(request):
    if request.GET.get('id') is not None:
        id = request.GET.get('id')
        objBranch = Branch.objects.get(pk=id)
        if objBranch is not None:
            centerName = objBranch.branch_code + "-" + objBranch.branch_name
        return JsonResponse(centerName, safe=False)
    

@login_required
def getDayCareCenterForUpdateById(request,pk):
    try:
        updateBranch_form = None
        objDaycareCenter = get_object_or_404(DayCare, pk=pk)

        if objDaycareCenter is not None:
            updateBranch_form = UpdateDayCareForm(instance=objDaycareCenter)

    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/centerUpdate.html", {"form": updateBranch_form}
    )


@login_required
def getDayCareCentersByBranchJs(request):
    
    if request.GET.get('id') is not None:
        id = request.GET.get('id')
        dayCareList =  list(DayCare.objects.filter(branch_id=id, is_active=True).values())
        return JsonResponse(dayCareList, safe=False)



@login_required
def getDiscounts(request):
    if request.method == "GET":
        try:
        # trying to retrive the next primaryKey
            nextId = Discount.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        discount_form = CreateDiscountForm(initial={'discount_code': "DS00" + str(nextId)})

    return render(
        request,
        "../templates/discount.html",
        {
            "form": discount_form,
            "UserName": request.user.username,
        },
    )

@login_required
def getDiscountJson(request):
    discountList = list(
        Discount.objects.all().values(
            "id",
            "discount_code",
            "discount_name",
            "discount_rate",
            "status",
            "is_active",
        )
    )
    print(discountList)

    return JsonResponse(discountList, safe=False)


@login_required
def saveDiscount(request):
    if request.method == "POST":
        
        discount_code = request.POST.get("discount_code")
        discount_name = request.POST.get("discount_name")
        discount_rate = request.POST.get("discount_rate")
        status = request.POST.get("status")
        is_active = request.POST.get("is_active")
        try:
                if discount_code is not None:
                    objDiscount = Discount.objects.get(
                        discount_code=discount_code
                    )
                    if objDiscount is not None:
                        objDiscount.discount_code = discount_code
                        objDiscount.discount_name = discount_name
                        objDiscount.discount_rate = discount_rate
                        objDiscount.status = status
                        if is_active == "on":
                            is_active = True
                        else:
                            is_active = False

                        objDiscount.is_active = is_active
                        objDiscount.user_updated = request.user.username
                        objDiscount.date_updated = datetime.now()
                        objDiscount.save()
                        messages.success(request, "Discount details updated.")

        except :
            form = CreateDiscountForm(request.POST)
            if form.is_valid():
                objDiscount = form.save(commit=False)
                objDiscount.user_created = request.user.username
                objDiscount.status = 'Pending Approval'
                objDiscount.save()
                messages.success(request, "Discount details saved.")
            else:
                messages.error(request, form.errors)
    
            return redirect("core:view_discounts")


@login_required
def approveDiscount(request):
    if request.GET.get('id') is not None:
        id = request.GET.get('id')
        print(id)
        objDiscount = Discount.objects.get(pk=id)
        print(objDiscount)
        if objDiscount is not None:
            objDiscount.status = "Approved"
            objDiscount.user_updated = request.user.username
            objDiscount.date_updated = datetime.now()
            objDiscount.save()
            print("Saved")
    return JsonResponse("Approved", safe=False)


@login_required
def rejectDiscount(request):
    print(request.GET.get('id'))
    if request.GET.get('id') is not None:
        id = request.GET.get('id')
        objDiscount = Discount.objects.get(pk=id)
        if objDiscount is not None:
            objDiscount.status = "Rejected"
            objDiscount.is_active = False
            objDiscount.user_updated = request.user.username
            objDiscount.date_updated = datetime.now()
            objDiscount.save()
    return JsonResponse("Rejected", safe=False)




@login_required
def getEnrollments(request):
    if request.method=="GET":
        try:
        # trying to retrive the next primaryKey
            nextId = ChildEnrollment.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        enrollment_form = CreateEnrollmentForm(initial={'enrollment_code': "E00" + str(nextId)})

    return render(
        request,
        "../templates/enrollment.html",
        {
            "form": enrollment_form,
            "UserName": request.user.username,
        },
    )


@login_required
def getEnrollmentsJS(request):
     enrolmentList = list(
        ChildEnrollment.objects.filter(child__enrollement_approved=False).annotate(
        child_name=Concat(F('child__child_first_name'), Value(' '), F('child__child_last_name')),
        normal_package_name=Concat(F('normal_package__package_code'), Value('-'), F('normal_package__package_name')),
        holiday_package_name=Concat(F('holiday_package__package_code'), Value('-'), F('holiday_package__package_name')),
        branch_name=Concat(F('branch__branch_code'), Value('-'), F('branch__branch_name')),
        center_name=Concat(F('center__daycare_code'), Value('-'), F('center__daycare_name')),
        discount_name=Concat(F('discount__discount_code'), Value('-'), F('discount__discount_name')),
    ).values(
            "id",
            "enrollment_code",
            "enrollment_date",
            "child_name",
            "normal_package_name",
            "holiday_package_name",
            "branch_name",
            "center_name",
            "discount_name",
            "status",
            "is_active",
        )
    )
    
     return JsonResponse(enrolmentList, safe=False)


@login_required
def saveEnrollments(request):
   if request.method == "POST":
        enrollment_code = request.POST.get("enrollment_code")
        enrollment_date = request.POST.get("enrollment_date")
        child = request.POST.get("child")
        branch = request.POST.get("branch")
        dayCare = request.POST.get("dayCare")
        normal_package = request.POST.get("normal_package")
        holiday_package = request.POST.get("holiday_package")
        discount = request.POST.get("discount")
        recipt_number = request.POST.get("recipt_number")
        is_active = request.POST.get("is_active")
        
        try:
                print(enrollment_code)
                if enrollment_code is not None:
                    objEnrollment = ChildEnrollment.objects.filter(
                        enrollment_code=enrollment_code
                    ).first()
                    if objEnrollment is not None:
                        print('Here')
                        objEnrollment.enrollment_code = enrollment_code
                        objEnrollment.enrollment_date = enrollment_date
                        objEnrollment.child = child
                        objEnrollment.branch = branch
                        objEnrollment.center = dayCare
                        objEnrollment.normal_package = normal_package
                        objEnrollment.holiday_package = holiday_package
                        objEnrollment.discount = discount
                        if is_active == "on":
                            is_active = True
                        else:
                            is_active = False

                        objEnrollment.is_active = is_active
                        objEnrollment.user_updated = request.user.username
                        objEnrollment.date_updated = datetime.now()
                        print('--------------------------------------------------------------')
                        objEnrollment.save()
                        messages.success(request, "Enrollment details updated.")
                else:  
                    form = CreateEnrollmentForm(request.POST)
                    if form.is_valid():
                        objEnrollment = form.save(commit=False)
                        objEnrollment.user_created = request.user.username
                        objEnrollment.status = 'Pending Approval'
                        objEnrollment.child = Child.objects.get(pk=child,is_active=True)
                        objChild = child
                        objChild.is_enrolled = True
                        objChild.save()

                        objEnrollment.branch = Branch.objects.get(pk=branch,is_active=True)
                        print('Daycare '+ dayCare)
                        objEnrollment.center =DayCare.objects.get(daycare_code=dayCare,is_active=True)
                        objEnrollment.normal_package = Package.objects.get(pk=normal_package,is_active=True)
                        objEnrollment.holiday_package = Package.objects.get(pk=holiday_package,is_active=True)
                        if discount is not None and discount!= "":
                            objEnrollment.discount = Discount.objects.get(pk = discount,is_active=True)
                        print('Discount '+discount)
                        objEnrollment.save()
                        messages.success(request, "Enrollment details saved.")
                    else:
                        messages.error(request, form.errors)      

        except Exception as e:
            messages.error(request, e)
            
    
        return redirect("core:view_enrollments")
   

@login_required
def getAllEnrollmentsJS(request):
     enrolmentList = list(
        ChildEnrollment.objects.filter(
        is_active=True,  # Add this filter for is_active
    ).annotate(
        child_name=Concat(F('child__child_first_name'), Value('-'), F('child__child_last_name')),
        normal_package_name=Concat(F('normal_package__package_code'), Value('-'), F('normal_package__package_name')),
        holiday_package_name=Concat(F('holiday_package__package_code'), Value('-'), F('holiday_package__package_name')),
        branch_name=Concat(F('branch__branch_code'), Value('-'), F('branch__branch_name')),
        center_name=Concat(F('center__daycare_code'), Value('-'), F('center__daycare_name')),
        discount_name=Concat(F('discount__discount_code'), Value('-'), F('discount__discount_name')),
    ).values(
            "id",
            "enrollment_code",
            "enrollment_date",
            "child_name",
            "normal_package_name",
            "holiday_package_name",
            "branch_name",
            "center_name",
            "discount_name",
            "status",
            "is_active",
        )
    )
    
     return JsonResponse(enrolmentList, safe=False)

    
@login_required
def deleteEnrollments(request,pk):
    try:
        objEnrollment = get_object_or_404(ChildEnrollment, pk=pk)

        if objEnrollment is not None:
            objEnrollment.is_active = False
            objEnrollment.user_updated = request.user.username
            objEnrollment.save()

    except Exception as e:
        messages.error(request, e)
    
    return JsonResponse("Sucess", safe=False)




