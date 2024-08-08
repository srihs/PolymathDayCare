import datetime
import os
from datetime import datetime, time, timedelta

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.http import *
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    CreateBranchForm,
    CreateCheckInForm,
    CreateChildForm,
    CreateDayCareForm,
    CreateDiscountForm,
    CreateEnrollmentForm,
    CreateExtraChargesForm,
    CreateExtraHoursUpTo530Form,
    CreatePackagesForm,
    CreatePackageTypeForm,
    SearchForm,
    UpdateBranchForm,
    UpdateChildForm,
    UpdateDayCareForm,
    UpdateExtraChargesForm,
    UpdateExtraHoursUpTo530Form,
    UpdatePackageTypeForm,
)
from .models import (
    AttendanceLog,
    Branch,
    Child,
    ChildEnrollment,
    DayCare,
    Discount,
    ExtraChargesHistory,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    Package,
    PackageExtraHoursMapping,
    PackageType,
)


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
                    if url_has_allowed_host_and_scheme(
                        next_url, allowed_hosts=request.get_host()
                    ):
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


def generateQR(admission_no):
    qr_directory = os.path.join(settings.MEDIA_ROOT, "qr")

    # Create the 'qr' directory if it doesn't exist
    try:
        os.makedirs(qr_directory, exist_ok=True)
    except Exception:
        messages.error(request, "Error creating 'qr' directory: {e}")

    # Generate the QR code
    qr = qrcode.make(settings.PROD_URL + settings.QR_METHOD_NAME + admission_no)

    # Save the QR code image to the 'qr' directory
    file_name = admission_no + ".png"
    file_path = os.path.join(qr_directory, file_name)

    try:
        qr.save(file_path)
    except Exception:
        messages.error(request, "Error saving QR code image")

    return file_name


@login_required
def getChildJson(reuest):
    chilList = list(
        Child.objects.all().values(
            "id",
            "admission_number",
            "child_image",
            "child_first_name",
            "child_last_name",
            "admission_date",
            "fathers_contact_number",
            "mothers_contact_number",
            "resident_contact_number",
            "is_polymath_student",
            "is_active",
            "qr_code",
        )
    )

    return JsonResponse(chilList, safe=False)


@login_required
def getChildWithEnrolementsJson(reuest):
    chilList = list(
        Child.objects.filter(is_enrolled=True, enrollement_approved=True).values(
            "id",
            "admission_number",
            "child_image",
            "child_first_name",
            "child_last_name",
            "admission_date",
            "fathers_contact_number",
            "mothers_contact_number",
            "resident_contact_number",
            "is_polymath_student",
            "is_active",
            "qr_code",
        )
    )

    return JsonResponse(chilList, safe=False)


@login_required
def getAllChildrenJS(request):
    childList = list(Child.objects.filter(is_active=True).values())
    return JsonResponse(childList, safe=False)


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
            child_image = request.FILES["child_image"]
            if is_polymath_student == "on":
                is_polymath_student = True
            else:
                is_polymath_student = False

            if is_active == "on":
                is_active = True
            else:
                is_active = False

        if request.POST.get("admission_number") is not None:
            user = User.objects.get(username=request.user.username)
            if user.groups.filter(name="Data Entry").exists():
                messages.error(
                    request, "You are not authorized to performe this operation."
                )
            else:
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
                    if objChild.qr_code == None:
                        objChild.qr_code = generateQR(admission_number)
                    objChild.child_image = child_image
                    objChild.save()
                    messages.success(request, "Child details updated.")
    except Exception:
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
            qr_code=generateQR(admission_number),
            child_image=child_image,
            admission_date=datetime.strptime(admission_date, "%Y-%m-%d").date(),
            is_active=is_active,
        )
        objChild.save()
        messages.success(request, "Child details saved.")

    return redirect("core:view_child")


@login_required
def deleteChild(request, pk):
    try:
        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(
                request, "You are not authorized to performe this operation."
            )
        else:
            objChild = get_object_or_404(Child, pk=pk)
            if objChild is not None:
                objChild.is_active = False
                objChild.user_updated = request.user.username
                objChild.save()

    except Exception as e:
        messages.error(request, e)

    return JsonResponse("Success", safe=False)


@login_required
def getPackageTypeJs(reuest):
    packageTypeList = list(
        PackageType.objects.filter(is_active=True).values(
            "id",
            "package_type_name",
            "is_holiday_package",
            "is_active",
        )
    )

    return JsonResponse(packageTypeList, safe=False)


@login_required
def getPacakgeTypes(request):
    if request.method == "GET":
        settings_form = CreatePackageTypeForm()

    else:
        objSettings = PackageType.objects.all().first()
        settings_form = CreatePackageTypeForm(instance=objSettings)

    return render(
        request,
        "../templates/packagetypes.html",
        {
            "form": settings_form,
            "UserName": request.user.username,
        },
    )


# @login_required
# def getRateByID(request, pk):
#     try:
#         rate_form = None
#         objRate = get_object_or_404(Rates, pk=pk)

#         if objRate is not None:
#             rate_form = UpdateRatesForm(instance=objRate)

#     except Exception as e:
#         messages.error(request, e)
#     return render(
#         request, "../templates/partials/rateUpdate.html", {"formU": rate_form}
#     )


@login_required
def getPackageTypeIdJs(request):
    if request.GET.get("packageType_id") is not None:
        id = request.GET.get("packageType_id")
        packageTypeList = list(
            PackageType.objects.filter(id=id).values(
                "id",
                "package_type_name",
                "is_holiday_package",
                "is_active",
            )
        )
        for i, n in enumerate(packageTypeList):
            if n["is_active"] == True:
                packageTypeList[i]["is_active"] = "Active"
            else:
                packageTypeList[i]["is_active"] = "Inactive"

    return JsonResponse(packageTypeList, safe=False)


@login_required
def getPackageTypeId(request):
    try:
        package_type_form = None
        if request.GET.get("packageType_id") is not None:
            objPackageType = get_object_or_404(
                PackageType, pk=request.GET.get("packageType_id")
            )
            request.session["id"] = objPackageType.id
            request.session.modified = True

        if objPackageType is not None:
            package_type_form = UpdatePackageTypeForm(instance=objPackageType)

    except Exception as e:
        messages.error(request, e)
    return render(
        request,
        "../templates/partials/packagetypeUpdate.html",
        {"formU": package_type_form},
    )


@login_required
def savePackageTypes(request):
    try:
        if request.method == "POST":
            form = UpdatePackageTypeForm(request.POST)
            objPackageType = form.save(commit=False)

            # capturing the variables with data
            package_type_name = request.POST.get("package_type_name")
            is_holiday_package = request.POST.get("is_holiday_package")

            if is_holiday_package == "on":
                is_holiday_package = True
            else:
                is_holiday_package = False

            if request.POST.get("id") is not None:
                objPackageType = PackageType.objects.get(id=request.POST.get("id"))
                if objPackageType is not None:
                    user = User.objects.get(username=request.user.username)
                    if user.groups.filter(name="Data Entry").exists():
                        messages.error(
                            request,
                            "You are not authorized to performe this operation.",
                        )
                    else:
                        objPackageType.package_type_name = package_type_name
                        objPackageType.is_holiday_package = is_holiday_package
                        objPackageType.is_active = True
                        objPackageType.user_updated = request.user.username
                        objPackageType.date_updated = datetime.now()
                        objPackageType.save()
                        messages.success(request, "Package type details updated.")
            else:
                objPackageType = PackageType(
                    package_type_name=package_type_name,
                    is_holiday_package=is_holiday_package,
                    is_active=True,
                    user_created=request.user.username,
                )
                objPackageType.save()
                messages.success(request, "Pakage type saved.")

    except Exception as e:
        messages.error(request, e)
    return redirect("core:view_package_types")


@login_required
def getAdditionalRatesUpto530(request):
    form = None
    if request.method == "GET":
        form = CreateExtraHoursUpTo530Form()
    return render(
        request,
        "../templates/extrahourseupto530.html",
        {
            "form": form,
            "UserName": request.user.username,
        },
    )


@login_required
@transaction.atomic
def saveAdditionalRatesUpTo530(request):
    request.session["package_type_id_upto530"] = None
    if request.method == "POST":
        form = CreateExtraHoursUpTo530Form(request.POST)
        user = User.objects.get(username=request.user.username)
        # ---------- Check for the permission ----
        if user.groups.filter(name="Data Entry").exists():
            messages.error(
                request,
                "You are not authorized to performe this operation.",
            )
        else:
            if form.is_valid():
                for i in range(1, 7):
                    hour_number = i
                    extra_rate = form.cleaned_data.get(f"extra_rate_{i}")
                    effective_from = form.cleaned_data.get(f"effective_from_{i}")
                    effective_to = form.cleaned_data.get(f"effective_to_{i}")
                    if extra_rate is not None and effective_from is not None:
                        with transaction.atomic():
                            objExtraHoursUpTo530 = ExtraHoursUpTo530.objects.create(
                                hour_number=hour_number,
                                extra_rate=extra_rate,
                                effective_from=effective_from,
                                effective_to=effective_to,
                            )
                            ExtraChargesHistory.objects.create(
                                extra_charges_before530=objExtraHoursUpTo530,
                                extra_rate=objExtraHoursUpTo530.extra_rate,
                                effective_from=objExtraHoursUpTo530.effective_from,
                                effective_to=objExtraHoursUpTo530.effective_to,
                            )
                messages.success(request, "Additional rate details saved.")
            else:
                messages.error(request, form.errors)

    return redirect("core:additional_rates_upto530")


@login_required
@transaction.atomic
def updateAdditionalRatesUpto530(request):
    try:
        if request.method == "POST":
            id = request.POST.get("id")
            extra_rate = request.POST.get("extra_rate")
            effective_from = request.POST.get("effective_from")
            effective_to = request.POST.get("effective_to")
            if id is not None:
                user = User.objects.get(username=request.user.username)
                objNewAdditionalRates = get_object_or_404(ExtraHoursUpTo530, pk=id)
                if objNewAdditionalRates is not None:
                    if user.groups.filter(name="Data Entry").exists():
                        messages.error(
                            request,
                            "You are not authorized to performe this operation.",
                        )
                    else:
                        objNewAdditionalRates.extra_rate = extra_rate
                        objNewAdditionalRates.effective_from = effective_from
                        objNewAdditionalRates.effective_to = effective_to
                        objNewAdditionalRates.user_updated = request.user.username
                        objNewAdditionalRates.save()

                        # ---------------- This section will save a log in to the extra charge history table------------
                        ExtraChargesHistory.objects.create(
                            extra_charges_before530=objNewAdditionalRates,
                            extra_rate=objNewAdditionalRates.extra_rate,
                            effective_from=objNewAdditionalRates.effective_from,
                            effective_to=objNewAdditionalRates.effective_to,
                            user_created=request.user.username,
                        )
                        messages.success(request, "Additional rate details Updated.")
                else:
                    messages.error(
                        request,
                        "No rate found.",
                    )
            else:
                messages.error(
                    request,
                    "No ID found.",
                )

    except Exception as e:
        messages.error(request, e)

    return redirect("core:additional_rates_upto530")


@login_required
def getAdditionalRatesUpto530ByJs(request):
    if request.method == "GET":
        additionalRatesList = None
        additionalRatesList = list(
            ExtraHoursUpTo530.objects.filter(
                is_active=True, extra_rate__isnull=False
            ).values(
                "id", "hour_number", "extra_rate", "effective_from", "effective_to"
            )
        )
    return JsonResponse(additionalRatesList, safe=False)


@login_required
def getAdditionalRatesUpto530HistoryByIdJS(request):
    if request.GET.get("id") is not None:
        additionalRatesHistoryList = list(
            ExtraChargesHistory.objects.filter(
                extra_charges_before530=request.GET.get("id")
            ).values(
                "id",
                "extra_rate",
                "effective_from",
                "effective_to",
                "extra_charges_before530",
                "date_created",
                "user_created",
                "is_active",
            )
        )
    return JsonResponse(additionalRatesHistoryList, safe=False)


@login_required
def getAdditionalRatesUpto530toUpdatebyId(request):
    update_form = None
    try:
        if request.GET.get("id") is not None:
            objAdditionalRatesUpto530 = get_object_or_404(
                ExtraHoursUpTo530, pk=request.GET.get("id")
            )

            if objAdditionalRatesUpto530 is not None:
                update_form = UpdateExtraHoursUpTo530Form(
                    instance=objAdditionalRatesUpto530
                )

    except Exception as e:
        messages.error(request, e)
    return render(
        request,
        "../templates/partials/extraHoursUpTo530Update.html",
        {"form": update_form},
    )


@login_required
def getAdditionalRates(request):
    if request.method == "GET":
        packageTypeCount = PackageType.objects.all().count()

        if packageTypeCount == 0:
            messages.error(request, "Package Types are not defined.")

        if request.session.get("package_type_id") is not None:
            form = CreateExtraChargesForm(
                initial={"package_type": request.session.get("package_type_id")}
            )
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
def getAdditionalRatesafter530HistoryByIdJS(request):
    if request.GET.get("id") is not None:
        additionalRatesHistoryList = list(
            ExtraChargesHistory.objects.filter(
                extra_charges_after530=request.GET.get("id")
            ).values(
                "id",
                "extra_rate",
                "from_time",
                "to_time",
                "extra_charges_after530",
                "date_created",
                "user_created",
                "is_active",
                "effective_from",
                "effective_to",
            )
        )
    return JsonResponse(additionalRatesHistoryList, safe=False)


@login_required
def getAdditionalRatesJs(request):
    additionalRatesList = None
    if request.GET.get("package_type_id") is not None:
        additionalRatesList = list(
            ExtraHoursAfter530.objects.filter(
                is_active=True, package_type=request.GET.get("package_type_id")
            ).values(
                "id",
                "from_time",
                "to_time",
                "extra_rate",
                "effective_from",
                "effective_to",
            )
        )
        for i, n in enumerate(additionalRatesList):
            if n["effective_to"] == None:
                additionalRatesList[i]["effective_to"] = "-"
    return JsonResponse(additionalRatesList, safe=False)


@login_required
def getAdditionalRatesByIdJs(request):
    if request.GET.get("package_type_Id") is not None:
        additionalRatesList = None
        additionalRatesList = list(
            ExtraHoursAfter530.objects.filter(
                is_active=True, package_type=request.GET.get("package_type_Id")
            ).values(
                "id",
                "from_time",
                "to_time",
                "extra_rate",
                "effective_from",
                "effective_to",
            )
        )
        for i, n in enumerate(additionalRatesList):
            if n["effective_to"] == None:
                additionalRatesList[i]["effective_to"] = "-"
    return JsonResponse(additionalRatesList, safe=False)


@login_required
def getAdditionalRateById(request):
    try:
        rate_form = None
        if request.GET.get("rate_id") is not None:
            objRate = get_object_or_404(
                ExtraHoursAfter530, pk=request.GET.get("rate_id")
            )
            request.session["id"] = objRate.id
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
    request.session["package_type_id"] = None
    if request.method == "POST":
        form = CreateExtraChargesForm(request.POST)
        user = User.objects.get(username=request.user.username)

        # ---------- Check for the permission ----
        if user.groups.filter(name="Data Entry").exists():
            messages.error(
                request,
                "You are not authorized to performe this operation.",
            )
        else:
            if form.is_valid():
                objAdditionalRates = form.save(commit=False)

                # ----------Check if the entered timeslot already defined -----------------
                objExtraChargestchek = ExtraHoursAfter530.objects.filter(
                    from_time=objAdditionalRates.from_time,
                    to_time=objAdditionalRates.to_time,
                    package_type=request.session["package_type_id"],
                ).first()

                if objExtraChargestchek is not None:
                    messages.error(request, "This time slot is already defined")
                else:
                    # ------- New timeslot and this is not defined before -------
                    objAdditionalRates.user_created = request.user.username
                    request.session["package_type_id"] = (
                        objAdditionalRates.package_type.id
                    )
                    request.session.modified = True
                    objAdditionalRates.save()

                    # ---------------- This section will save a log in to the extra charge history table------------
                    with transaction.atomic():  # <-- if the extra charge history fails, addtional rates will be failed.
                        objExtrachargeHistory = ExtraChargesHistory(
                            extra_charges_after530=objAdditionalRates,
                            from_time=objAdditionalRates.from_time,
                            to_time=objAdditionalRates.to_time,
                            extra_rate=objAdditionalRates.extra_rate,
                            effective_from=objAdditionalRates.effective_from,
                            effective_to=objAdditionalRates.effective_to,
                            user_created=objAdditionalRates.user_created,
                            date_created=objAdditionalRates.date_created,
                        )
                        objExtrachargeHistory.save()
                        messages.success(request, "Additional rate details saved.")
                    # ------------------------------------------------------------------------------------------------
            else:
                messages.error(request, form.errors)

    return redirect("core:view_additional_rates")


@login_required
def updateAdditionalRates(request):
    try:
        if request.method == "POST":
            id = request.POST.get("id")
            from_time = request.POST.get("from_time")
            to_time = request.POST.get("to_time")
            extra_rate = request.POST.get("extra_rate")

            if id is not None:
                user = User.objects.get(username=request.user.username)
                objNewAdditionalRates = get_object_or_404(ExtraHoursAfter530, pk=id)

                if objNewAdditionalRates is not None:
                    if user.groups.filter(name="Data Entry").exists():
                        messages.error(
                            request,
                            "You are not authorized to performe this operation.",
                        )
                    else:
                        objNewAdditionalRates.extra_rate = extra_rate
                        objNewAdditionalRates.from_time = from_time
                        objNewAdditionalRates.to_time = to_time
                        objNewAdditionalRates.user_updated = request.user.username
                        objNewAdditionalRates.save()
                        # ---------------- This section will save a log in to the extra charge history table------------
                        with transaction.atomic():  # <-- if the extra charge history fails, addtional rates will be failed.
                            objExtrachargeHistory = ExtraChargesHistory(
                                extra_charges_after530=objNewAdditionalRates,
                                from_time=objNewAdditionalRates.from_time,
                                to_time=objNewAdditionalRates.to_time,
                                extra_rate=objNewAdditionalRates.extra_rate,
                                effective_from=objNewAdditionalRates.effective_from,
                                effective_to=objNewAdditionalRates.effective_to,
                                user_created=objNewAdditionalRates.user_created,
                                date_created=objNewAdditionalRates.date_created,
                            )
                            objExtrachargeHistory.save()
                        messages.success(request, "Additional rate details Updated.")
                else:
                    messages.error(
                        request,
                        "No rate found.",
                    )

            else:
                messages.error(
                    request,
                    "No ID found.",
                )

    except Exception as e:
        messages.error(request, e)

    return redirect("core:view_additional_rates")


def calculate_duration(request):
    # Get the values of "from_time" and "to_time" from the POST request
    from_time_str = request.GET.get("from_time")
    to_time_str = request.GET.get("to_time")

    try:
        # Convert the time strings to datetime objects
        from_time = datetime.strptime(from_time_str, "%H:%M")
        to_time = datetime.strptime(to_time_str, "%H:%M")

        # Calculate the duration
        duration_seconds = (to_time - from_time).seconds
        duration_hours = duration_seconds // 3600
        duration_minutes = (duration_seconds % 3600) // 60

        # Return the result as JSON
        return JsonResponse(
            {"duration_hours": duration_hours, "duration_minutes": duration_minutes}
        )
    except ValueError:
        # Handle invalid time format
        return JsonResponse({"error": "Invalid time format"}, status=400)
    except Exception as e:
        # Handle other exceptions
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getExtraHoursUpto530(request):
    try:
        objxtraHoursUpto530 = None
        rate_form = None
        if request.GET.get("rate_id") is not None:
            objxtraHoursUpto530 = get_object_or_404(
                ExtraHoursUpTo530, pk=request.GET.get("rate_id")
            )
            request.session["id"] = objxtraHoursUpto530.id
            request.session.modified = True

        if objxtraHoursUpto530 is not None:
            rate_form = CreateExtraHoursUpTo530Form(instance=objxtraHoursUpto530)
        else:
            rate_form = CreateExtraHoursUpTo530Form()

    except Exception as e:
        messages.error(request, e)
    return render(request, "../templates/extrahourseupto530.html", {"form": rate_form})


@login_required
def getPackages(request):
    if request.method == "GET":
        try:
            # trying to retrive the next primaryKey
            nextId = Package.objects.all().count()
            nextId += 1
            packageTypeCount = PackageType.objects.all().count()
            extraChargesCount = ExtraHoursAfter530.objects.all().count()
            additionalChargesUpto530 = ExtraHoursUpTo530.objects.filter(is_active=True)
            additionalChargesAfter530 = ExtraHoursAfter530.objects.filter(
                is_active=True
            )

            if packageTypeCount == 0:
                messages.error(request, "Package Types are not defined.")
            if extraChargesCount == 0:
                messages.error(request, "Extra charges are not defined.")

        except:
            nextId = 1  # if the next ID is null define the record as the first

        package_form = CreatePackagesForm(
            initial={"package_code": "PKG00" + str(nextId)}
        )
    return render(
        request,
        "../templates/packages.html",
        {
            "form": package_form,
            "additionalChargesUpto530": additionalChargesUpto530,
            "additionalChargesAfter530": additionalChargesAfter530,
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
                "package_total",
            )
        )

        for i, n in enumerate(packageList):
            if n["package_type"]:
                package_type = PackageType.objects.filter(
                    pk=packageList[i]["package_type"]
                ).first()
                packageList[i]["package_type"] = package_type.package_type_name

    return JsonResponse(packageList, safe=False)


# @login_required
# def checkIfHolidayPackage(id):
#     is_holiday = None

#     objBaseRate = Rates.objects.get(pk=id)
#     if objBaseRate.is_holiday_rate:
#         is_holiday = True
#     else:
#         is_holiday = False

#     return is_holiday


@login_required
@transaction.atomic
def savePackage(request):
    extrChargesUpTo530 = None
    extrChargesUpTo530 = None
    if request.method == "POST":
        form = CreatePackagesForm(request.POST)
        if form.is_valid():
            objPackage = form.save(commit=False)

            objPackageType = PackageType.objects.get(
                pk=request.POST.get("package_type")
            )
            objPackage.package_type = objPackageType
            objPackage.user_created = request.user.username

            objPackage.save()

            extrChargesAfter530 = ExtraHoursAfter530.objects.filter(
                package_type=objPackageType
            )
            if not objPackageType.is_holiday_package:
                if objPackage.to_time < time(
                    17, 30
                ):  # should replace with the cutoff time
                    extrChargesUpTo530 = ExtraHoursUpTo530.objects.all()

            if extrChargesAfter530 is not None:
                for rateAfter530 in extrChargesAfter530:
                    if rateAfter530.to_time > objPackage.to_time:
                        objMapping = PackageExtraHoursMapping()
                        objMapping.package = objPackage
                        objMapping.extra_hours_after_530 = rateAfter530
                        objMapping.save()

            if extrChargesUpTo530 is not None:
                for rateBefore530 in extrChargesUpTo530:
                    objMapping = PackageExtraHoursMapping()
                    objMapping.package = objPackage
                    objMapping.extra_hours_upto_530 = rateBefore530
                    objMapping.save()

            messages.success(request, "Package details saved.")
        else:
            messages.error(request, form.errors)

    else:
        messages.error(request, "Something went wrong")

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

        branch_form = CreateBranchForm(initial={"branch_code": "BRN00" + str(nextId)})

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
                "is_active",
            )
        )

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
            objBranch = Branch.objects.filter(branch_code=branch_code).first()
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
def getBranchForUpdateById(request, pk):
    try:
        updateBranch_form = None
        objBranch = get_object_or_404(Branch, pk=pk)

        if objBranch is not None:
            updateBranch_form = UpdateBranchForm(instance=objBranch)

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

        branch_form = CreateDayCareForm(initial={"daycare_code": "DC00" + str(nextId)})

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
        daycare_code = request.POST.get("daycare_code")
        daycare_name = request.POST.get("daycare_name")
        branch = request.POST.get("branch")
        daycare_incharge = request.POST.get("daycare_incharge")
        daycare_contact_mobile_number = request.POST.get(
            "daycare_contact_mobile_number"
        )
        daycare_contact_number = request.POST.get("daycare_contact_number")
        is_active = request.POST.get("is_active")
        try:
            if daycare_code is not None:
                objDayCare = DayCare.objects.get(daycare_code=daycare_code)
                if objDayCare is not None:
                    objDayCare.daycare_code = daycare_code
                    objDayCare.daycare_name = daycare_name
                    objDayCare.branch = branch
                    objDayCare.daycare_incharge = daycare_incharge
                    objDayCare.daycare_contact_mobile_number = (
                        daycare_contact_mobile_number
                    )
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

        except:
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
            )
        )

        for i, n in enumerate(daycareList):
            if n["is_active"]:
                daycareList[i]["is_active"] = "Yes"
            else:
                daycareList[i]["is_active"] = "No"

    return JsonResponse(daycareList, safe=False)


@login_required
def getDayCareCenterNamebyIdJs(request):
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        objBranch = Branch.objects.get(pk=id)
        if objBranch is not None:
            centerName = objBranch.branch_code + "-" + objBranch.branch_name
        return JsonResponse(centerName, safe=False)


@login_required
def getDayCareCenterForUpdateById(request, pk):
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
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        dayCareList = list(
            DayCare.objects.filter(branch_id=id, is_active=True).values()
        )
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

        discount_form = CreateDiscountForm(
            initial={"discount_code": "DS00" + str(nextId)}
        )

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
                objDiscount = Discount.objects.get(discount_code=discount_code)
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

        except:
            form = CreateDiscountForm(request.POST)
            if form.is_valid():
                objDiscount = form.save(commit=False)
                objDiscount.user_created = request.user.username
                objDiscount.status = "Pending Approval"
                objDiscount.save()
                messages.success(request, "Discount details saved.")
            else:
                messages.error(request, form.errors)

            return redirect("core:view_discounts")


@login_required
def approveDiscount(request):
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        objDiscount = Discount.objects.get(pk=id)
        if objDiscount is not None:
            objDiscount.status = "Approved"
            objDiscount.user_updated = request.user.username
            objDiscount.date_updated = datetime.now()
            objDiscount.save()
    return JsonResponse("Approved", safe=False)


@login_required
def rejectDiscount(request):
    prin(request.GET.get("id"))
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
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
    if request.method == "GET":
        try:
            # trying to retrive the next primaryKey
            nextId = ChildEnrollment.objects.all().count()
            nextId += 1
        except:
            nextId = 1  # if the next ID is null define the record as the first

        enrollment_form = CreateEnrollmentForm(
            initial={"enrollment_code": "E00" + str(nextId)}
        )

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
        ChildEnrollment.objects.filter(status="Pending Approval", is_active=True)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
            normal_package_name=Concat(
                F("normal_package__package_code"),
                Value("-"),
                F("normal_package__package_name"),
            ),
            holiday_package_name=Concat(
                F("holiday_package__package_code"),
                Value("-"),
                F("holiday_package__package_name"),
            ),
            branch_name=Concat(
                F("branch__branch_code"), Value("-"), F("branch__branch_name")
            ),
            center_name=Concat(
                F("center__daycare_code"), Value("-"), F("center__daycare_name")
            ),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
        )
        .values(
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
def getEnrollmentsForApprovalJS(request):
    enrolmentList = list(
        ChildEnrollment.objects.filter(child__enrollement_approved=False)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
            normal_package_name=Concat(
                F("normal_package__package_code"),
                Value("-"),
                F("normal_package__package_name"),
            ),
            holiday_package_name=Concat(
                F("holiday_package__package_code"),
                Value("-"),
                F("holiday_package__package_name"),
            ),
            branch_name=Concat(
                F("branch__branch_code"), Value("-"), F("branch__branch_name")
            ),
            center_name=Concat(
                F("center__daycare_code"), Value("-"), F("center__daycare_name")
            ),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
        )
        .values(
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
            if enrollment_code is not None:
                objEnrollment = ChildEnrollment.objects.filter(
                    enrollment_code=enrollment_code
                ).first()

            if objEnrollment is not None:
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
                objEnrollment.save()
                messages.success(request, "Enrollment details updated.")
            else:
                form = CreateEnrollmentForm(request.POST)
                if form.is_valid():
                    objEnrollment = form.save(commit=False)
                    objEnrollment.user_created = request.user.username
                    objEnrollment.status = "Pending Approval"
                    objEnrollment.child = Child.objects.get(pk=child, is_active=True)
                    objChild = objEnrollment.child
                    objChild.is_enrolled = True
                    objChild.save()

                    objEnrollment.branch = Branch.objects.get(pk=branch, is_active=True)
                    objEnrollment.center = DayCare.objects.get(
                        daycare_code=dayCare, is_active=True
                    )
                    objEnrollment.normal_package = Package.objects.get(
                        pk=normal_package, is_active=True
                    )
                    objEnrollment.holiday_package = Package.objects.get(
                        pk=holiday_package, is_active=True
                    )
                    if discount is not None and discount != "":
                        objEnrollment.discount = Discount.objects.get(
                            pk=discount, is_active=True
                        )
                    objEnrollment.save()
                    messages.success(request, "Enrollment details saved.")
        except Exception as e:
            messages.error(request, e)

        return redirect("core:view_enrollments")


@login_required
def getAllPendingEnrollmentsJS(request):
    enrolmentList = list(
        ChildEnrollment.objects.filter(
            is_active=True,  # Add this filter for is_active
            status=1,
        )
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value("-"), F("child__child_last_name")
            ),
            normal_package_name=Concat(
                F("normal_package__package_code"),
                Value("-"),
                F("normal_package__package_name"),
            ),
            holiday_package_name=Concat(
                F("holiday_package__package_code"),
                Value("-"),
                F("holiday_package__package_name"),
            ),
            branch_name=Concat(
                F("branch__branch_code"), Value("-"), F("branch__branch_name")
            ),
            center_name=Concat(
                F("center__daycare_code"), Value("-"), F("center__daycare_name")
            ),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
        )
        .values(
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
def deleteEnrollments(request, pk):
    try:
        objEnrollment = get_object_or_404(ChildEnrollment, pk=pk)

        if objEnrollment is not None:
            objEnrollment.is_active = False
            objEnrollment.user_updated = request.user.username
            objEnrollment.save()

    except Exception as e:
        messages.error(request, e)

    return JsonResponse("Sucess", safe=False)


@login_required
def getAllEnrollmentsForApproval(request):
    return render(request, "../templates/enrollmentlist.html")


@login_required
@transaction.atomic
def approveEnrollment(request):
    if request.GET.get("id") is not None:
        objEnrollment = ChildEnrollment.objects.get(pk=request.GET.get("id"))
        objEnrollment.status = "Approved"
        objEnrollment.user_updated = request.user.username
        objEnrollment.date_updated = datetime.now()
        objEnrollment.save()

        objChild = objEnrollment.child
        objChild.enrollement_approved = True
        objChild.is_enrolled = True
        objChild.save()

    return JsonResponse("Enrollment approved", safe=False)


@login_required
@transaction.atomic
def rejectEnrollment(request):
    if request.GET.get("id") is not None:
        objEnrollment = ChildEnrollment.objects.get(pk=request.GET.get("id"))
        objEnrollment.status = "Rejected"
        objEnrollment.user_updated = request.user.username
        objEnrollment.date_updated = datetime.now()

        objChild = objEnrollment.child
        objChild.is_enrolled = False
        objChild.enrollement_approved = False
        objChild.save()

        objEnrollment.save()

    return JsonResponse("Enrollment rejected", safe=False)


@login_required
def getCheckIns(request):
    enrollment_form = CreateCheckInForm()

    return render(
        request,
        "../templates/checkin.html",
        {
            "form": enrollment_form,
            "UserName": request.user.username,
        },
    )


@login_required
def getAllAttendanceJS(request):
    attendanceList = list(
        AttendanceLog.objects.filter(is_active=True)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
        )
        .values(
            "id",
            "child_name",
            "date_logged",
            "time_logged",
            "is_active",
        )
    )
    return JsonResponse(attendanceList, safe=False)


@login_required
def saveAttendance(request):
    if request.method == "POST":
        if request.POST.get("child") is not None:
            objChild = Child.objects.get(
                admission_number=request.POST.get("child"), is_active=True
            )

            if objChild is not None:
                try:
                    form = CreateCheckInForm(request.POST)
                    if form.is_valid():
                        objAttendance = form.save(commit=False)
                        if objChild.admission_date <= objAttendance.date_logged:
                            objAttendance.user_created = request.user.username
                            objAttendance.child = objChild
                            objAttendance.save()
                            messages.success(request, " Attendance record saved.")
                        else:
                            messages.error(
                                request,
                                " Attendence date is invalid. Child was not enrolled on that day.",
                            )
                    else:
                        messages.error(request, form.errors)
                except Exception as e:
                    messages.error(request, e)
            return redirect("core:view_check_ins")


@login_required
def autoAttendanceRecorder(request, admission_no):
    if request.method == "POST":
        if admission_no is not None:
            objChild = Child.objects.get(admission_number=admission_no, is_active=True)
            if objChild is not None:
                try:
                    objAttendance = AttendanceLog()
                    objAttendance.date_logged = datetime.now().date
                    objAttendance.time_logged = datetime.now().time
                    objAttendance.date_created = datetime.now()
                    objAttendance.user_created = "Scanned by the USER"
                    objAttendance.child = objChild
                    objAttendance.save()
                    messages.success(request, "Attendance record saved.")
                except Exception as e:
                    messages.error(request, e)


@login_required
def getMissingAttendanceRecords(request, context=None):
    list = None
    searchForm = SearchForm()
    if context is not None:
        list = context
    return render(
        request,
        "../templates/reports/missingtime.html",
        {
            "list": list,
            "form": searchForm,
            "UserName": request.user.username,
        },
    )


@login_required
def processMissingAttendanceRecords(request):
    # Initialize a dictionary to hold dates with missing or incomplete attendance
    incomplete_attendance_dates = list()
    from_Date = None
    if request.method == "POST":
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")

        # Dictionary to hold dates with missing or incomplete attendance != ''
        if from_date == "":
            # if dates are not provided, assign dates for a period of 30 days
            from_date = datetime.today() + timedelta(days=-30)
            from_Date = from_date.date()
        else:
            from_Date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if to_date == "":
            to_date = datetime.today().date()
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        attendenceList = AttendanceLog.objects.filter(
            date_logged__range=(from_Date, to_date)
        )

        childList = Child.objects.filter(
            is_active=True, enrollement_approved=True, is_enrolled=True
        )

        # Create a list of all dates within the range
        date_range = [
            from_Date + timedelta(days=x) for x in range((to_date - from_Date).days + 1)
        ]

        # Iterate through each child  in the enrollments
        for child in childList:
            # Iterate through each date in the range
            for single_date in date_range:
                # Filter attendance records for each date
                daily_attendance_records = AttendanceLog.objects.filter(
                    date_logged=single_date, child=child.id
                )
                # Check if the attendance records for the day are less than 2
                if daily_attendance_records.count() < 2:
                    # Add this date and records to the dictionary
                    incomplete_attendance_dates.append(daily_attendance_records)

    return getMissingAttendanceRecords(request, incomplete_attendance_dates)


@login_required
def loadAttendanceReports(request):
    return render(request, "../templates/reports/attendancereport.html")


@login_required
def attendanceReportsJS(request):
    # This method will be used to do the search and return the attendance records according to parameters
    if request.method == "POST":
        if pk is not None:
            objAttendanceList = AttendanceLog.objects.get(
                child=pk, is_active=True
            ).values()

    return JsonResponse(objAttendanceList, safe=False)
