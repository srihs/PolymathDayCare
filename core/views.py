import csv
import datetime
import json
import os
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat
from django.http import *
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .forms import (
    AttendanceReportForm,
    ChildSearchForm,
    CreateBranchForm,
    CreateCenterChangeRequestForm,
    CreateCheckInForm,
    CreateChildForm,
    CreateDayCareForm,
    CreateDiscountForm,
    CreateEnrollmentForm,
    CreateExtraChargesForm,
    CreateExtraHoursUpTo530Form,
    CreateFixedPackagesForm,
    CreateFlexPackagesForm,
    CreateOtherhHolidayForm,
    CreatePackageChangeRequestForm,
    # CreateHolidayTypesForm,
    CreatePackageTypeForm,
    CreatePolymathHolidayForm,
    CreatePublicHolidayForm,
    GenerateInvoiceForm,
    SearchForm,
    UpdateBranchForm,
    UpdateChildForm,
    UpdateDayCareForm,
    UpdateExtraChargesForm,
    UpdateExtraHoursUpTo530Form,
    UpdateOtherHolidayForm,
    # UpdateHolidayTypesForm,
    UpdatePackageTypeForm,
    UpdatePolymathHolidayForm,
    UpdatePublicHolidayForm,
)
from .models import (
    AttendanceLog,
    Branch,
    CenterChangerequest,
    Child,
    ChildEnrollment,
    ChildPackageMapping,
    DayCare,
    Discount,
    ExtraChargesHistory,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    FixedPackage,
    FlexPackages,
    Holiday,
    Invoice,
    PackageChangerequest,
    # HolidayType,
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


def generateQR(admission_no, child_first_name, child_last_name):
    text = child_first_name + " " + child_last_name + " -" + admission_no
    qr_directory = os.path.join(settings.MEDIA_ROOT, "qr")
    # Create the 'qr' directory if it doesn't exist
    try:
        os.makedirs(qr_directory, exist_ok=True)
    except Exception:
        messages.error(request, "Error creating 'qr' directory: {e}")

    # Save the QR code image to the 'qr' directory
    file_name = admission_no + "- " + child_first_name + " " + child_last_name + ".png"
    file_path = os.path.join(qr_directory, file_name)

    # Create a QR Code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(settings.PROD_URL + settings.QR_METHOD_NAME + admission_no)
    qr.make(fit=True)

    # Generate QR code image
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Convert to RGB
    qr_img = qr_img.convert("RGB")

    # Create a new image to hold the QR code and text
    img_with_text = Image.new("RGB", (qr_img.size[0], qr_img.size[1] + 50), "white")
    img_with_text.paste(qr_img, (0, 0))

    # Draw the text below the QR code
    draw = ImageDraw.Draw(img_with_text)
    font = ImageFont.load_default()  # Default font

    # Use the textbbox method to get dimensions
    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]

    # Center the text
    draw.text(
        ((img_with_text.size[0] - text_width) // 2, qr_img.size[1] + 10),
        text,
        fill="black",
        font=font,
    )

    try:
        img_with_text.save(file_path)
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
        nextId += 2
    except:
        nextId = 2  # if the next ID is null define the record as the first
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
            fathers_contact_number = request.POST.get("fathers_contact_number").strip()
            fathers_whatsapp_number = request.POST.get("fathers_whatsapp_number")
            mothers_name = request.POST.get("mothers_name")
            mothers_contact_number = request.POST.get("mothers_contact_number").strip()
            mothers_whatsapp_number = request.POST.get(
                "mothers_whatsapp_number"
            ).strip()
            resident_contact_number = request.POST.get(
                "resident_contact_number"
            ).strip()
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
                    objChild.child_first_name = child_first_name
                    objChild.child_last_name = child_last_name
                    objChild.fathers_contact_number = int(fathers_contact_number)
                    objChild.fathers_whatsapp_number = int(fathers_whatsapp_number)
                    objChild.mothers_contact_number = int(mothers_contact_number)
                    objChild.mothers_whatsapp_number = int(mothers_whatsapp_number)
                    objChild.resident_contact_number = int(resident_contact_number)
                    objChild.address_line1 = address_line1
                    objChild.address_line2 = address_line2
                    objChild.address_line3 = address_line3
                    objChild.email_address = email_address
                    objChild.is_polymath_student = is_polymath_student
                    objChild.user_updated = request.user.username
                    objChild.is_active = is_active
                    if objChild.qr_code == None:
                        objChild.qr_code = generateQR(
                            admission_number,
                            objChild.child_first_name,
                            objChild.child_last_name,
                        )
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
            qr_code=generateQR(admission_number, child_first_name, child_last_name),
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
                objChild.leave_date = datetime.now()
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
def getFixedPackages(request):
    if request.method == "GET":
        try:
            # trying to retrive the next primaryKey
            nextId = FixedPackage.objects.all().count()
            nextId += 1
            packageTypeCount = PackageType.objects.all().count()
            extraChargesCount = ExtraHoursAfter530.objects.all().count()
            # additionalChargesUpto530 = ExtraHoursUpTo530.objects.filter(is_active=True)
            # additionalChargesAfter530 = ExtraHoursAfter530.objects.filter(
            #     is_active=True
            # )
            if packageTypeCount == 0:
                messages.error(request, "Package Types are not defined.")
            if extraChargesCount == 0:
                messages.error(request, "Extra charges are not defined.")
        except:
            nextId = 1  # if the next ID is null define the record as the first
        package_form = CreateFixedPackagesForm(
            initial={"package_code": "FIP00" + str(nextId)}
        )
    return render(
        request,
        "../templates/fixedpackages.html",
        {
            "form": package_form,
            # "additionalChargesUpto530": additionalChargesUpto530,
            # "additionalChargesAfter530": additionalChargesAfter530,
            "UserName": request.user.username,
        },
    )


@login_required
def getFixedPackagesJs(request):
    if request.method == "GET":
        packageList = list(
            FixedPackage.objects.all().values(
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


@login_required
@transaction.atomic
def saveFixedPackage(request):
    extrChargesUpTo530 = None
    extrChargesUpTo530 = None
    is_holiday_package = False
    if request.method == "POST":
        form = CreateFixedPackagesForm(request.POST)
        if form.is_valid():
            objPackage = form.save(commit=False)
            objPackageType = PackageType.objects.get(
                pk=request.POST.get("package_type")
            )
            if not objPackageType.is_holiday_package:
                is_holiday_package = True
            objPackage.package_type = objPackageType
            objPackage.is_holiday_package = is_holiday_package
            objPackage.user_created = request.user.username
            objPackage.save()
            extrChargesAfter530 = ExtraHoursAfter530.objects.filter(
                package_type=objPackageType
            )
            if not is_holiday_package:
                if objPackage.to_time < time(
                    17, 30
                ):  # should replace with the cutoff time
                    extrChargesUpTo530 = ExtraHoursUpTo530.objects.all()
            if extrChargesAfter530 is not None:
                for rateAfter530 in extrChargesAfter530:
                    if rateAfter530.to_time > objPackage.to_time:
                        objMapping = PackageExtraHoursMapping()
                        objMapping.fixed_package = objPackage
                        objMapping.extra_hours_after_530 = rateAfter530
                        objMapping.save()
            if extrChargesUpTo530 is not None:
                for rateBefore530 in extrChargesUpTo530:
                    objMapping = PackageExtraHoursMapping()
                    objMapping.fixed_package = objPackage
                    objMapping.extra_hours_upto_530 = rateBefore530
                    objMapping.save()
            messages.success(request, "Package details saved.")
        else:
            messages.error(request, form.errors)
    else:
        messages.error(request, "Something went wrong")
    return redirect("core:view_fixed_packages")


@login_required
def getFlexPackages(request):
    if request.method == "GET":
        try:
            # trying to retrive the next primaryKey
            nextId = FlexPackages.objects.all().count()
            nextId += 1
            packageTypeCount = PackageType.objects.all().count()
            extraChargesCount = ExtraHoursAfter530.objects.all().count()
            if packageTypeCount == 0:
                messages.error(request, "Package Types are not defined.")
            if extraChargesCount == 0:
                messages.error(request, "Extra charges are not defined.")
        except:
            nextId = 1  # if the next ID is null define the record as the first
        package_form = CreateFlexPackagesForm(
            initial={"package_code": "FLP00" + str(nextId)}
        )
    return render(
        request,
        "../templates/flexpackages.html",
        {
            "form": package_form,
            # "additionalChargesUpto530": additionalChargesUpto530,
            # "additionalChargesAfter530": additionalChargesAfter530,
            "UserName": request.user.username,
        },
    )


@login_required
def getflexPackagesJs(request):
    if request.method == "GET":
        packageList = list(
            FlexPackages.objects.all().values(
                "id",
                "package_type",
                "package_code",
                "package_name",
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


@login_required
@transaction.atomic
def saveFlexPackage(request):
    extrChargesUpTo530 = None
    extrChargesUpTo530 = None
    if request.method == "POST":
        form = CreateFlexPackagesForm(request.POST)
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
            extrChargesUpTo530 = ExtraHoursUpTo530.objects.all()
            if extrChargesAfter530 is not None:
                for rateAfter530 in extrChargesAfter530:
                    objMapping = PackageExtraHoursMapping()
                    objMapping.flex_package = objPackage
                    objMapping.extra_hours_after_530 = rateAfter530
                    objMapping.save()
            if extrChargesUpTo530 is not None:
                for rateBefore530 in extrChargesUpTo530:
                    objMapping = PackageExtraHoursMapping()
                    objMapping.flex_package = objPackage
                    objMapping.extra_hours_upto_530 = rateBefore530
                    objMapping.save()
            messages.success(request, "Package details saved.")
        else:
            messages.error(request, form.errors)
    else:
        messages.error(request, "Something went wrong")
    return redirect("core:view_flex_packages")


@login_required
def getPacakageExtrahoursUpto530JS(request):
    extraHoursUpto530List = []
    if request.GET.get("id") and request.GET.get("packageTerm") == "1":
        extraHoursList = list(
            PackageExtraHoursMapping.objects.filter(
                fixed_package=request.GET.get("id")
            ).values(
                "id",
                "extra_hours_upto_530",
            )
        )
    else:
        extraHoursList = list(
            PackageExtraHoursMapping.objects.filter(
                flex_package=request.GET.get("id")
            ).values(
                "id",
                "extra_hours_upto_530",
            )
        )
    for i, n in enumerate(extraHoursList):
        if n["extra_hours_upto_530"]:
            objExtraHoursUpto530 = ExtraHoursUpTo530.objects.filter(
                pk=extraHoursList[i]["extra_hours_upto_530"]
            ).first()
            extraHoursUpto530List.append(
                {
                    "hour_number": objExtraHoursUpto530.hour_number,
                    "extra_rate": objExtraHoursUpto530.extra_rate,
                    "effective_from": objExtraHoursUpto530.effective_from,
                    "effective_to": objExtraHoursUpto530.effective_to,
                }
            )
    return JsonResponse(extraHoursUpto530List, safe=False)


@login_required
def getPacakageExtrahoursAfter530JS(request):
    extraHoursAfter530List = []
    if request.GET.get("id") and request.GET.get("packageTerm") == "1":
        extraHoursList = list(
            PackageExtraHoursMapping.objects.filter(
                fixed_package=request.GET.get("id")
            ).values(
                "id",
                "extra_hours_after_530",
            )
        )
    else:
        extraHoursList = list(
            PackageExtraHoursMapping.objects.filter(
                flex_package=request.GET.get("id")
            ).values(
                "id",
                "extra_hours_after_530",
            )
        )
    for i, n in enumerate(extraHoursList):
        if n["extra_hours_after_530"]:
            objExtraHoursAfter530 = ExtraHoursAfter530.objects.filter(
                pk=extraHoursList[i]["extra_hours_after_530"]
            ).first()
            extraHoursAfter530List.append(
                {
                    "from_time": objExtraHoursAfter530.from_time,
                    "to_time": objExtraHoursAfter530.to_time,
                    "extra_rate": objExtraHoursAfter530.extra_rate,
                    "effective_from": objExtraHoursAfter530.effective_from,
                    "effective_to": objExtraHoursAfter530.effective_to,
                }
            )
    return JsonResponse(extraHoursAfter530List, safe=False)


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
    # Subqueries to get the package names from ChildPackageMapping
    normal_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "normal_package__package_name"
        )[:1]
    )
    flex_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "flex_package__package_name"
        )[:1]
    )
    holiday_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "holiday_package__package_name"
        )[:1]
    )

    # Annotate the packages based on availability
    enrolmentList = list(
        ChildEnrollment.objects.filter(status="Pending Approval", is_active=True)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
            branch_name=F("branch__branch_name"),
            center_name=F("center__daycare_name"),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
            normal_package_name=normal_package_subquery,
            flex_package_name=flex_package_subquery,
            holiday_package=holiday_package_subquery,
            package_name=Case(
                When(normal_package_name__isnull=False, then=F("normal_package_name")),
                When(flex_package_name__isnull=False, then=F("flex_package_name")),
                default=F("holiday_package"),
                output_field=CharField(),
            ),
        )
        .values(
            "id",
            "enrollment_code",
            "enrollment_date",
            "child_name",
            "branch_name",
            "center_name",
            "discount_name",
            "status",
            "is_active",
            "package_name",
            "holiday_package",
        )
    )
    return JsonResponse(enrolmentList, safe=False)


@login_required
def getEnrollmentsForApprovalJS(request):
    # Subqueries to get the package names from ChildPackageMapping
    normal_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "normal_package__package_name"
        )[:1]
    )
    flex_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "flex_package__package_name"
        )[:1]
    )
    holiday_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "holiday_package__package_name"
        )[:1]
    )

    # Annotate the packages based on availability
    enrolmentList = list(
        ChildEnrollment.objects.filter(status="Pending Approval", is_active=True)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
            branch_name=F("branch__branch_name"),
            center_name=F("center__daycare_name"),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
            normal_package_name=normal_package_subquery,
            flex_package_name=flex_package_subquery,
            holiday_package=holiday_package_subquery,
            package_name=Case(
                When(normal_package_name__isnull=False, then=F("normal_package_name")),
                When(flex_package_name__isnull=False, then=F("flex_package_name")),
                default=F("holiday_package"),
                output_field=CharField(),
            ),
        )
        .values(
            "id",
            "enrollment_code",
            "enrollment_date",
            "child_name",
            "branch_name",
            "center_name",
            "discount_name",
            "status",
            "is_active",
            "package_name",
            "holiday_package",
        )
    )
    return JsonResponse(enrolmentList, safe=False)


@login_required
@transaction.atomic
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
        flex_package = request.POST.get("flex_package")
        recipt_number = request.POST.get("recipt_number")
        is_active = request.POST.get("is_active")

        try:
            with transaction.atomic():
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
                        objEnrollment.child = Child.objects.get(
                            pk=child, is_active=True
                        )
                        objEnrollment.recipt_number = recipt_number
                        objChild = objEnrollment.child
                        objChild.is_enrolled = True
                        objChild.save()
                        objEnrollment.branch = Branch.objects.get(
                            pk=branch, is_active=True
                        )
                        objEnrollment.center = DayCare.objects.get(
                            daycare_code=dayCare, is_active=True
                        )
                        if discount is not None and discount != "":
                            objEnrollment.discount = Discount.objects.get(
                                pk=discount, is_active=True
                            )
                        objEnrollment.save()

                        objPackageMapping = ChildPackageMapping()
                        objPackageMapping.child = Child.objects.get(
                            pk=child, is_active=True
                        )
                        if holiday_package:
                            objPackageMapping.holiday_package = (
                                FixedPackage.objects.get(pk=holiday_package)
                            )

                        if normal_package:
                            objPackageMapping.normal_package = FixedPackage.objects.get(
                                pk=normal_package
                            )

                        if flex_package:
                            objPackageMapping.flex_package = FlexPackages.objects.get(
                                pk=flex_package
                            )
                        objPackageMapping.effective_from = datetime.now()
                        objPackageMapping.is_active = False
                        objPackageMapping.save()
                        messages.success(request, "Enrollment details saved.")
        except Exception as e:
            messages.error(request, e)
        return redirect("core:view_enrollments")


@login_required
def getAllPendingEnrollmentsJS(request):
    # Subqueries to get the package names from ChildPackageMapping
    normal_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "normal_package__package_name"
        )[:1]
    )
    flex_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "flex_package__package_name"
        )[:1]
    )
    holiday_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "holiday_package__package_name"
        )[:1]
    )

    # Annotate the packages based on availability
    enrolmentList = list(
        ChildEnrollment.objects.filter(status="Pending Approval", is_active=True)
        .annotate(
            child_name=Concat(
                F("child__child_first_name"), Value(" "), F("child__child_last_name")
            ),
            branch_name=F("branch__branch_name"),
            center_name=F("center__daycare_name"),
            discount_name=Concat(
                F("discount__discount_code"), Value("-"), F("discount__discount_name")
            ),
            normal_package_name=normal_package_subquery,
            flex_package_name=flex_package_subquery,
            holiday_package=holiday_package_subquery,
            package_name=Case(
                When(normal_package_name__isnull=False, then=F("normal_package_name")),
                When(flex_package_name__isnull=False, then=F("flex_package_name")),
                default=F("holiday_package"),
                output_field=CharField(),
            ),
        )
        .values(
            "id",
            "enrollment_code",
            "enrollment_date",
            "child_name",
            "branch_name",
            "center_name",
            "discount_name",
            "status",
            "is_active",
            "package_name",
            "holiday_package",
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
        objChildMapping = ChildPackageMapping.objects.get(pk=request.GET.get("id"))
        objChildMapping.is_active = True
        objChildMapping.save()

        # Generate enrollment forms automatically
        generate_enrollment_forms(objChild.id)

    return JsonResponse("Enrollment approved", safe=False)


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

        objChildMapping = ChildPackageMapping.objects.get(child=objChild)
        objChildMapping.is_active = True
        objChildMapping.save()

        # Generate enrollment forms
        generate_enrollment_forms(objChild.id)

    return JsonResponse("Enrollment approved", safe=False)


def generate_enrollment_forms(child_id):
    """
    Generate all three enrollment forms on one A4 page using ReportLab
    """
    try:
        # Get child and enrollment data (same as before)
        child = Child.objects.get(pk=child_id)
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        # If no approved enrollment, get the most recent one
        if not enrollment:
            enrollment = (
                ChildEnrollment.objects.filter(child=child, is_active=True)
                .order_by("-date_created")
                .first()
            )

        if not enrollment:
            print(f"No enrollment found for child {child.admission_number}")
            return None

        # Get package information
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        package_name = "N/A"
        if package_mapping:
            if package_mapping.normal_package:
                package_name = package_mapping.normal_package.package_name
            elif package_mapping.flex_package:
                package_name = package_mapping.flex_package.package_name
            elif package_mapping.holiday_package:
                package_name = package_mapping.holiday_package.package_name

        # Create PDF
        pdf_filename = f"enrollment_forms_{child.admission_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(settings.MEDIA_ROOT, "enrollment_forms", pdf_filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        # Create PDF with ReportLab - Single Page
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4

        # Data for the forms
        data = {
            "child_name": f"{child.child_first_name} {child.child_last_name}",
            "date_of_birth": child.date_of_birth.strftime("%d.%m.%Y")
            if child.date_of_birth
            else "N/A",
            "date_of_admission": enrollment.enrollment_date.strftime("%d.%m.%Y"),
            "admission_no": child.admission_number,
            "receipt_no": enrollment.recipt_number or "N/A",
            "fathers_name": child.fathers_name,
            "mothers_name": child.mothers_name,
            "fathers_contact": child.fathers_contact_number or "N/A",
            "mothers_contact": child.mothers_contact_number or "N/A",
            "fathers_whatsapp": child.fathers_whatsapp_number or "N/A",
            "mothers_whatsapp": child.mothers_whatsapp_number or "N/A",
            "package_name": package_name,
            "center_display": f"({enrollment.center.daycare_code} - {enrollment.center.daycare_name})",
        }

        # Draw all three forms on one page
        draw_all_forms_single_page(c, data)

        c.save()
        print(f"Enrollment forms saved: {pdf_path}")
        return pdf_path

    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def draw_all_forms_single_page(c, data):
    """Draw all three forms on a single A4 page"""
    width, height = A4

    # Calculate form dimensions (divide page into 3 sections)
    form_height = (height - 60) / 3  # 60 for margins
    margin = 20

    # Form 1: Parent Copy (Top)
    y_start_1 = height - 30
    draw_single_form(
        c, data, "Parent", y_start_1, form_height, width, is_office_copy=False
    )

    # Form 2: Day Care Copy (Middle)
    y_start_2 = y_start_1 - form_height
    draw_single_form(
        c, data, "Office", y_start_2, form_height, width, is_office_copy=False
    )

    # Form 3: Office Copy (Bottom)
    y_start_3 = y_start_2 - form_height
    draw_single_form(
        c, data, "Office Copy", y_start_3, form_height, width, is_office_copy=True
    )


def draw_single_form(
    c, data, from_type, y_start, form_height, width, is_office_copy=False
):
    """Draw a single form with improved alignment"""

    # Draw border
    c.rect(20, y_start - form_height, width - 40, form_height - 10, stroke=1, fill=0)

    # Current Y position
    y = y_start - 30

    # Header
    c.setFont("Helvetica-Bold", 14)
    text = "POLYMATH COLLEGE"
    text_width = c.stringWidth(text, "Helvetica-Bold", 14)
    c.drawString((width - text_width) / 2, y, text)
    y -= 25

    # Office Copy label (only for office copy)
    if is_office_copy:
        c.setFont("Helvetica-Bold", 12)
        text = "Office Copy"
        text_width = c.stringWidth(text, "Helvetica-Bold", 12)
        c.drawString((width - text_width) / 2, y, text)
        y -= 20

    # To/From section (not for office copy)
    if not is_office_copy:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(30, y, "To")
        c.drawString(80, y, f"Day Care Division {data['center_display']}")
        y -= 15
        c.drawString(30, y, "From")
        c.drawString(80, y, from_type)
        y -= 20

    # Title
    c.setFont("Helvetica-Bold", 11)
    title = "New Admission - Day Care Division"
    title_width = c.stringWidth(title, "Helvetica-Bold", 11)
    c.drawString((width - title_width) / 2, y, title)
    y -= 15

    # Center code (only for office copy)
    if is_office_copy:
        c.setFont("Helvetica", 9)
        center_text = data["center_display"]
        center_width = c.stringWidth(center_text, "Helvetica", 9)
        c.drawString((width - center_width) / 2, y, center_text)
        y -= 20
    else:
        y -= 10

    # Form fields
    c.setFont("Helvetica-Bold", 9)
    line_height = 12

    # Basic info
    c.drawString(30, y, "Name of the Child")
    c.drawString(140, y, data["child_name"])
    y -= line_height

    c.drawString(30, y, "Date of Birth")
    c.drawString(140, y, data["date_of_birth"])
    y -= line_height

    c.drawString(30, y, "Date of Admission")
    c.drawString(140, y, data["date_of_admission"])
    y -= line_height

    c.drawString(30, y, "Admission No")
    c.drawString(140, y, data["admission_no"])
    y -= line_height

    c.drawString(30, y, "Receipt No")
    c.drawString(140, y, data["receipt_no"])
    y -= line_height + 5

    # Contact information with right alignment
    c.drawString(30, y, "Father's Name")
    c.drawString(140, y, data["fathers_name"])
    c.drawRightString(width - 30, y, f"Contact Num: {data['fathers_contact']}")
    y -= line_height

    c.drawString(30, y, "Mother's Name")
    c.drawString(140, y, data["mothers_name"])
    c.drawRightString(width - 30, y, f"Contact Num: {data['mothers_contact']}")
    y -= line_height

    # WhatsApp number (right aligned)
    c.drawRightString(width - 30, y, f"Whatsapp Num: {data['mothers_whatsapp']}")
    y -= line_height + 5

    # Package
    c.drawString(30, y, "Package")
    c.drawString(140, y, data["package_name"])
    y -= line_height + 10

    # Signature line
    c.drawString(30, y, "Signature")
    c.line(90, y, 250, y)  # Signature line


# This function for downloading forms
@login_required
def download_enrollment_forms(request, enrollment_id):
    """
    Download enrollment forms by enrollment_id
    """
    try:
        enrollment = ChildEnrollment.objects.get(pk=enrollment_id)
        child = enrollment.child

        # Look for existing PDF file
        forms_directory = os.path.join(settings.MEDIA_ROOT, "enrollment_forms")
        pdf_path = None

        if os.path.exists(forms_directory):
            for filename in os.listdir(forms_directory):
                if filename.startswith(f"enrollment_forms_{child.admission_number}_"):
                    pdf_path = os.path.join(forms_directory, filename)
                    break

        # If no file found, generate new one
        if not pdf_path or not os.path.exists(pdf_path):
            pdf_path = generate_enrollment_forms(child.id)

        # Serve the file
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type="application/pdf")
                filename = f"enrollment_forms_{child.admission_number}.pdf"
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
        else:
            return HttpResponse("Error: Could not generate PDF", status=404)

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


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
                admission_number=request.POST.get("child"),
                is_active=True,
                enrollement_approved=True,  # to make sure the child is enrolled
            )
            if objChild is not None:
                try:
                    form = CreateCheckInForm(request.POST)
                    if form.is_valid():
                        objAttendance = form.save(commit=False)

                        if objChild.admission_date <= objAttendance.date_logged:
                            objEnrollment = ChildEnrollment.objects.filter(
                                child=objChild.id
                            ).first()
                            if objEnrollment is not None:
                                objAttendance.branch = objEnrollment.branch
                                objAttendance.day_care = objEnrollment.center
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


def autoAttendanceRecorder(request, admission_no):
    if admission_no is not None:
        objChild = Child.objects.get(admission_number=admission_no, is_active=True)

        if objChild is not None:
            try:
                if objChild.is_enrolled:
                    objAttendance = AttendanceLog()
                    objAttendance.date_logged = datetime.now().date()
                    objAttendance.time_logged = datetime.now().time()
                    objAttendance.date_created = datetime.now()
                    objAttendance.user_created = "Scanned by the USER"
                    objAttendance.child = objChild
                    objAttendance.save()
                else:
                    messages.error(request, "Child is not enrolled")
            except Exception as e:
                messages.error(request, e)
        else:
            messages.error(request, "Child not found")
    return render(
        request,
        "../templates/suceess.html",
        {"child": objChild, "time": objAttendance.time_logged},
    )


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
def processMissingAttendanceRecordsJS(request):
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    from_Date = (
        datetime.strptime(from_date, "%Y-%m-%d").date()
        if from_date
        else (datetime.today() - timedelta(days=30)).date()
    )
    to_date = (
        datetime.strptime(to_date, "%Y-%m-%d").date()
        if to_date
        else datetime.today().date()
    )

    active_children = Child.objects.filter(
        is_active=True, enrollement_approved=True, is_enrolled=True
    ).values_list("id", flat=True)

    attendance_records = AttendanceLog.objects.filter(
        date_logged__range=(from_Date, to_date), child_id__in=active_children
    ).values_list("child_id", "date_logged", "time_logged")

    attendance_dict = {}
    for child_id, date_logged, time_logged in attendance_records:
        attendance_dict.setdefault((child_id, date_logged), []).append(time_logged)

    cutoff_time = time(15, 0)  # 3:00 PM
    incomplete_attendance_dates = []

    for (child_id, date_logged), time_logs in attendance_dict.items():
        if len(time_logs) == 1:
            single_time = time_logs[0]
            formatted_time = single_time.strftime("%H:%M")
            if single_time > cutoff_time:
                # Logged time is OUT → IN is missing
                in_time = "Missing"
                out_time = formatted_time
                missing_record = "IN"
            else:
                # Logged time is IN → OUT is missing
                in_time = formatted_time
                out_time = "Missing"
                missing_record = "OUT"

            child = Child.objects.get(id=child_id)

            incomplete_attendance_dates.append(
                {
                    "child_name": f"{child.admission_number} - {child.child_first_name} {child.child_last_name}",
                    "date_logged": date_logged,
                    "in_time": in_time,
                    "out_time": out_time,
                    "missing_record": missing_record,
                }
            )

    return JsonResponse(incomplete_attendance_dates, safe=False)


@login_required
def getAttendanceReports(request):
    attendenceform = AttendanceReportForm()
    return render(
        request,
        "../templates/reports/attendancereport.html",
        {"form": attendenceform, "UserName": request.user.username},
    )


@login_required
def attendanceReportsJS(request):
    # This method will be used to do the search and return the attendance records according to parameters
    if request.method == "GET":
        childId = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")

        # Prepare filters for AttendanceLogs
        filters = Q()
        if childId:
            filters &= Q(child__admission_number=childId)

        # Only apply date filtering if values are not None or empty
        if from_date and to_date:
            filters &= Q(date_logged__range=[str(from_date), str(to_date)])
        elif from_date:
            filters &= Q(date_logged__gte=str(from_date))
        elif to_date:
            filters &= Q(date_logged__lte=str(to_date))

        # Fetch the attendance logs grouped by child and date
        attendance_logs = list(
            AttendanceLog.objects.filter(filters)
            .values("child", "date_logged")  # Group by child and date
            .annotate(
                child_name=Concat(
                    F("child__child_first_name"),
                    Value(" "),
                    F("child__child_last_name"),
                ),
                admission_number=F("child__admission_number"),
                log_count=Count("id"),  # Count logs for the day
                in_time=Min("time_logged"),  # First log of the day (IN time)
                out_time=Case(
                    When(
                        log_count=1, then=Value(None)
                    ),  # If only 1 log, set out_time to None
                    default=Max(
                        "time_logged"
                    ),  # Otherwise, set to last log of the day (OUT time)
                ),
            )
            .values(  # Structuring output
                "admission_number",
                "child_name",
                "date_logged",
                "in_time",  # Initially, the first log is considered "in_time"
                "out_time",  # Initially, the last log is considered "out_time"
                "log_count",  # Include log_count here to use it later in the code
            )
        )

        # Now modify the records based on the scenario you described
        for log in attendance_logs:
            # If there is only one log, we check the time
            if log["log_count"] == 1:
                in_time = log["in_time"]
                # Check if the in_time is after 4:00 PM (16:00:00)
                if (
                    in_time
                    and in_time > datetime.strptime("16:00:00", "%H:%M:%S").time()
                ):
                    # Set the in_time to None and treat this as an out_time
                    log["in_time"] = None
                    log["out_time"] = in_time
                else:
                    # If it's before 4:00 PM, we keep it as the in_time and set out_time to None
                    log["out_time"] = None

    return JsonResponse(attendance_logs, safe=False)


@login_required
def getPublicHolidays(request):
    holidayform = CreatePublicHolidayForm()
    return render(
        request,
        "../templates/publicholidays.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getPublicHolidaysJS(request):
    holidayList = list(
        Holiday.objects.filter(is_active=True, is_public_holiday=True).values(
            "id",
            "title",
            "start_date",
            "end_date",
            "no_of_days",
            "weekdays_count",
            "weekends_count",
        )
    )
    return JsonResponse(holidayList, safe=False)


@login_required
def getPublicHolidayID(request, pk):
    try:
        form = None
        objHoliday = get_object_or_404(Holiday, pk=pk)
        if objHoliday is not None:
            form = UpdatePublicHolidayForm(instance=objHoliday)
    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/publicholidayupdate.html", {"form": form}
    )


@login_required
def savePublicHoliday(request):
    try:
        title = request.POST.get("title")
        id = request.POST.get("id")

        start_date = datetime.strptime(
            request.POST.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.POST.get("end_date"), "%Y-%m-%d").date()

        if request.method == "POST":
            form = CreatePublicHolidayForm(request.POST)
            if form.is_valid():
                objHoliday = form.save(commit=False)
                if request.POST.get("id") is not None:
                    objHoliday = Holiday.objects.get(pk=request.POST.get("id"))
                    if objHoliday is not None:
                        user = User.objects.get(username=request.user.username)
                        if user.groups.filter(name="Data Entry").exists():
                            messages.error(
                                request,
                                "You are not authorized to performe this operation.",
                            )
                        else:
                            if start_date > end_date:
                                raise Exception(
                                    "End date "
                                    + "("
                                    + str(end_date)
                                    + ")"
                                    + " cannot be older than the start date "
                                    + "("
                                    + str(start_date)
                                    + ")"
                                    + ".",
                                )

                            objHoliday.title = title
                            objHoliday.is_active = True
                            objHoliday.start_date = start_date
                            objHoliday.end_date = end_date
                            objHoliday.user_updated = request.user.username
                            objHoliday.date_updated = datetime.now()
                            objHoliday.is_public_holiday = True
                            objHoliday.save()
                            messages.success(request, "Public holiday details updated.")
                else:
                    if objHoliday.start_date > objHoliday.end_date:
                        raise Exception(
                            "End date "
                            + "("
                            + str(objHoliday.end_date)
                            + ")"
                            + " cannot be older than the start date "
                            + "("
                            + str(objHoliday.start_date)
                            + ")"
                            + ".",
                        )

                    objHoliday.is_active = True
                    objHoliday.is_public_holiday = True
                    objHoliday.user_created = request.user.username
                    objHoliday.save()
                    messages.success(request, "Public holiday saved.")
            else:
                messages.error(request, form.errors)
    except Exception as e:
        messages.error(request, e)
    return redirect("core:public_holidays")


@login_required
def getPolymathHolidays(request):
    holidayform = CreatePolymathHolidayForm()
    return render(
        request,
        "../templates/polymathholidays.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getPolymathHolidaysJS(request):
    holidayList = list(
        Holiday.objects.filter(is_active=True, is_polymath_holiday=True).values(
            "id",
            "title",
            "start_date",
            "end_date",
            "no_of_days",
            "weekdays_count",
            "weekends_count",
        )
    )
    return JsonResponse(holidayList, safe=False)


@login_required
def savePolymathHoliday(request):
    try:
        title = request.POST.get("title")
        id = request.POST.get("id")

        start_date = datetime.strptime(
            request.POST.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.POST.get("end_date"), "%Y-%m-%d").date()

        if request.method == "POST":
            form = CreatePublicHolidayForm(request.POST)
            if form.is_valid():
                objHoliday = form.save(commit=False)
                if request.POST.get("id") is not None:
                    objHoliday = Holiday.objects.get(pk=request.POST.get("id"))
                    if objHoliday is not None:
                        user = User.objects.get(username=request.user.username)
                        if user.groups.filter(name="Data Entry").exists():
                            messages.error(
                                request,
                                "You are not authorized to performe this operation.",
                            )
                        else:
                            if start_date > end_date:
                                raise Exception(
                                    "End date "
                                    + "("
                                    + str(end_date)
                                    + ")"
                                    + " cannot be older than the start date "
                                    + "("
                                    + str(start_date)
                                    + ")"
                                    + ".",
                                )

                            objHoliday.title = title
                            objHoliday.is_active = True
                            objHoliday.start_date = start_date
                            objHoliday.end_date = end_date
                            objHoliday.user_updated = request.user.username
                            objHoliday.date_updated = datetime.now()
                            objHoliday.is_polymath_holiday = True
                            objHoliday.save()
                            messages.success(
                                request, "Polymath holiday details updated."
                            )
                else:
                    if objHoliday.start_date > objHoliday.end_date:
                        raise Exception(
                            "End date "
                            + "("
                            + str(objHoliday.end_date)
                            + ")"
                            + " cannot be older than the start date "
                            + "("
                            + str(objHoliday.start_date)
                            + ")"
                            + ".",
                        )

                    objHoliday.is_active = True
                    objHoliday.user_created = request.user.username
                    objHoliday.is_polymath_holiday = True
                    objHoliday.save()
                    messages.success(request, "Polymath holiday saved.")
            else:
                messages.error(request, form.errors)
    except Exception as e:
        messages.error(request, e)
    return redirect("core:polymath_holidays")


@login_required
def getPolymathHolidayID(request, pk):
    try:
        form = None
        objHoliday = get_object_or_404(Holiday, pk=pk)
        if objHoliday is not None:
            form = UpdatePolymathHolidayForm(instance=objHoliday)
    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/polymathholidayupdate.html", {"form": form}
    )


@login_required
def getOtherHolidays(request):
    holidayform = CreateOtherhHolidayForm()
    return render(
        request,
        "../templates/otherholiday.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getOtherHolidaysJS(request):
    holidayList = list(
        Holiday.objects.filter(is_active=True, is_other_school_holiday=True).values(
            "id",
            "title",
            "start_date",
            "end_date",
            "no_of_days",
            "weekdays_count",
            "weekends_count",
        )
    )
    return JsonResponse(holidayList, safe=False)


@login_required
def saveOtherHoliday(request):
    try:
        title = request.POST.get("title")
        id = request.POST.get("id")

        start_date = datetime.strptime(
            request.POST.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.POST.get("end_date"), "%Y-%m-%d").date()

        if request.method == "POST":
            form = CreatePublicHolidayForm(request.POST)
            if form.is_valid():
                objHoliday = form.save(commit=False)
                if request.POST.get("id") is not None:
                    objHoliday = Holiday.objects.get(pk=request.POST.get("id"))
                    if objHoliday is not None:
                        user = User.objects.get(username=request.user.username)
                        if user.groups.filter(name="Data Entry").exists():
                            messages.error(
                                request,
                                "You are not authorized to performe this operation.",
                            )
                        else:
                            if start_date > end_date:
                                raise Exception(
                                    "End date "
                                    + "("
                                    + str(end_date)
                                    + ")"
                                    + " cannot be older than the start date "
                                    + "("
                                    + str(start_date)
                                    + ")"
                                    + ".",
                                )

                            objHoliday.title = title
                            objHoliday.is_active = True
                            objHoliday.start_date = start_date
                            objHoliday.end_date = end_date
                            objHoliday.user_updated = request.user.username
                            objHoliday.date_updated = datetime.now()
                            objHoliday.is_other_school_holiday = True
                            objHoliday.save()
                            messages.success(request, "Other holiday details updated.")
                else:
                    if objHoliday.start_date > objHoliday.end_date:
                        raise Exception(
                            "End date "
                            + "("
                            + str(objHoliday.end_date)
                            + ")"
                            + " cannot be older than the start date "
                            + "("
                            + str(objHoliday.start_date)
                            + ")"
                            + ".",
                        )

                    objHoliday.is_active = True
                    objHoliday.user_created = request.user.username
                    objHoliday.is_other_school_holiday = True
                    objHoliday.save()
                    messages.success(request, "Other holiday saved.")
            else:
                messages.error(request, form.errors)
    except Exception as e:
        messages.error(request, e)
    return redirect("core:other_holidays")


@login_required
def getOtherHolidayID(request, pk):
    try:
        form = None
        objHoliday = get_object_or_404(Holiday, pk=pk)
        if objHoliday is not None:
            form = UpdateOtherHolidayForm(instance=objHoliday)
    except Exception as e:
        messages.error(request, e)
    return render(
        request, "../templates/partials/otherholidayupdate.html", {"form": form}
    )


def nullify_empty(value, is_numeric=False, is_date=False):
    if value in [None, ""]:
        return None
    if is_numeric:
        # Ensure the value is numeric or convert it to `None`
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    if is_date:
        # Attempt to parse the date; return `None` if invalid
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    return value


@login_required
def upload_csv(request):
    if request.method == "GET":
        return render(request, "../templates/utils/dataimporter.html")

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")

        if not csv_file:
            messages.error(request, "No file was uploaded.")
            return render(request, "../templates/utils/dataimporter.html")

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "This is not a CSV file.")
            return render(request, "../templates/utils/dataimporter.html")

        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(
                request, "You are not authorized to performe this operation."
            )
        else:
            file_data = csv_file.read().decode("utf-8").splitlines()
            reader = csv.reader(file_data)

            # Skip the header if your CSV file has one
            next(reader, None)

            for row in reader:
                # Ensure there are exactly 8 columns
                if len(row) < 8:
                    messages.error(
                        request,
                        "CSV file format is incorrect. Each row must have 8 columns.",
                    )
                    return render(request, "../templates/utils/dataimporter.html")

                (
                    admission_number,
                    child_first_name,
                    child_last_name,
                    date_of_birth,
                    fathers_name,
                    fathers_contact_number,
                    fathers_whatsapp_number,
                    mothers_name,
                    mothers_contact_number,
                    mothers_whatsapp_number,
                    resident_contact_number,
                    address_line1,
                    address_line2,
                    address_line3,
                    email_address,
                    is_polymath_student,
                    admission_date,
                    leave_date,
                ) = row

                # Convert dates from string to date format
                date_of_birth = date_of_birth or None
                leave_date = leave_date or None

                # Update or create a Child record
                Child.objects.update_or_create(
                    admission_number=admission_number,
                    defaults={
                        "child_first_name": nullify_empty(child_first_name),
                        "child_last_name": nullify_empty(child_last_name) or " ",
                        "admission_number": admission_number,
                        "date_of_birth": nullify_empty(date_of_birth, is_date=True),
                        "leave_date": nullify_empty(leave_date, is_date=True),
                        "fathers_name": nullify_empty(fathers_name) or " ",
                        "fathers_contact_number": nullify_empty(
                            fathers_contact_number, is_numeric=True
                        ),
                        "fathers_whatsapp_number": nullify_empty(
                            fathers_whatsapp_number, is_numeric=True
                        ),
                        "mothers_name": nullify_empty(mothers_name) or " ",
                        "mothers_contact_number": nullify_empty(
                            mothers_contact_number, is_numeric=True
                        ),
                        "mothers_whatsapp_number": nullify_empty(
                            mothers_whatsapp_number, is_numeric=True
                        ),
                        "resident_contact_number": nullify_empty(
                            resident_contact_number, is_numeric=True
                        ),
                        "address_line1": nullify_empty(address_line1) or " ",
                        "address_line2": nullify_empty(address_line2) or " ",
                        "address_line3": nullify_empty(address_line3) or " ",
                        "email_address": nullify_empty(email_address) or " ",
                        "is_polymath_student": bool(is_polymath_student),
                        "admission_date": nullify_empty(admission_date, is_date=True),
                        "qr_code": generateQR(
                            admission_number, child_first_name, child_last_name
                        ),
                    },
                )

            messages.success(
                request, "CSV file has been uploaded and processed successfully."
            )
    return render(request, "../templates/utils/dataimporter.html")


def download_qr_files(request):
    try:
        # Path to the folder containing the files
        folder_path = os.path.join(settings.MEDIA_ROOT, "qr")

        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Path to the temporary ZIP file
        temp_zip_path = os.path.join(temp_dir, "qr_files.zip")

        # Create a ZIP file
        shutil.make_archive(temp_zip_path.replace(".zip", ""), "zip", folder_path)

        # Open the ZIP file and return it as a response
        with open(temp_zip_path, "rb") as zip_file:
            response = HttpResponse(zip_file.read(), content_type="application/zip")
            response["Content-Disposition"] = "attachment; filename=qr_files.zip"
            return response

    except Exception as e:
        messages.error(request, e)

    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)


@login_required
def getPackageChange(request):
    requestform = CreatePackageChangeRequestForm()
    return render(
        request,
        "../templates/packagechange.html",
        {"form": requestform, "UserName": request.user.username},
    )


@login_required
def getPackagesByChildIdJS(request):
    packageList = []
    packageText = None
    isFixed = False
    isHoliday = False
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        package = ChildPackageMapping.objects.get(child=id, is_active=True)
        if package is not None:
            if package.normal_package is not None:
                objPackage = FixedPackage.objects.filter(
                    pk=package.normal_package.id
                ).first()
                if objPackage is not None:
                    packageText = (
                        objPackage.package_code + " - " + objPackage.package_name
                    )
                    isFixed = True
                    id = objPackage.id
                    packageList.append([isFixed, packageText, id, isHoliday])
            if package.flex_package is not None:
                objPackage = FlexPackages.objects.filter(
                    pk=package.flex_package.id
                ).first()
                if objPackage is not None:
                    packageText = (
                        objPackage.package_code + " - " + objPackage.package_name
                    )
                isFixed = False
                id = objPackage.id
                packageList.append([isFixed, packageText, id, isHoliday])
            if package.holiday_package is not None:
                objHolidayPackage = FixedPackage.objects.filter(
                    pk=package.holiday_package.id
                ).first()
                if objHolidayPackage is not None:
                    packageText = (
                        objHolidayPackage.package_code
                        + " - "
                        + objHolidayPackage.package_name
                    )
                isFixed = False
                id = objHolidayPackage.id
                isHoliday = True
                packageList.append([isFixed, packageText, id, isHoliday])
            response_json = json.dumps(packageList)  # Serialize to JSON string
    return JsonResponse(response_json, safe=False)


@login_required
def savePackageRequest(request):
    try:
        if request.method == "POST":
            user = User.objects.get(username=request.user.username)
            if user.groups.filter(name="Data Entry").exists():
                messages.error(
                    request,
                    "You are not authorized to performe this operation.",
                )
                return
            form = CreatePackageChangeRequestForm(request.POST)
            if form.is_valid():
                objPackageChangeRequest = form.save(commit=False)

                if (
                    request.POST.get("old_fixed_package") is not None
                    and request.POST.get("old_fixed_package") != ""
                ):
                    objOldFixedPcakage = FixedPackage.objects.filter(
                        pk=request.POST.get("old_fixed_package")
                    ).first()

                    if objOldFixedPcakage is not None:
                        if (
                            objPackageChangeRequest.new_fixed_package
                            == objPackageChangeRequest.old_fixed_package
                        ):
                            messages.error(
                                request,
                                "The selected new package cannot be the same as the old package.",
                            )
                            return
                    objPackageChangeRequest.old_fixed_package = objOldFixedPcakage
                if (
                    request.POST.get("old_flexed_package") is not None
                    and request.POST.get("old_flexed_package") != ""
                ):
                    objOldFlexPackage = FlexPackages.objects.filter(
                        pk=request.POST.get("old_flexed_package")
                    ).filter()
                    if objOldFlexPackage is not None:
                        if (
                            objPackageChangeRequest.new_flexed_package
                            == objPackageChangeRequest.old_flexed_package
                        ):
                            return messages.error(
                                request,
                                "The selected new package cannot be the same as the old package.",
                            )
                        objPackageChangeRequest.old_flexed_package = objOldFlexPackage
                objPackageChangeRequest.user_created = request.user.username
                # checking if the new package is selected
                if (
                    objPackageChangeRequest.new_fixed_package is None
                    and objPackageChangeRequest.new_flexed_package is None
                ):
                    return messages.error(
                        request,
                        "Please select either a new fixed package or a new flex package.",
                    )
                elif (
                    objPackageChangeRequest.new_fixed_package is not None
                    and objPackageChangeRequest.new_flexed_package is not None
                ):
                    return messages.error(
                        request,
                        "You can only select one package: either a new fixed package or a new flex package.",
                    )
                if request.POST.get("old_holiday_package") is not None:
                    objHolidayPackage = FixedPackage.objects.filter(
                        pk=request.POST.get("old_holiday_package")
                    ).first()
                    if objHolidayPackage is not None:
                        objPackageChangeRequest.old_holiday_package = objHolidayPackage
                objPackageChangeRequest.save()
                messages.success(request, "Package change request saved.")
            else:
                messages.error(request, form.errors)
    except Exception as e:
        messages.error(request, e)
    finally:
        return redirect("core:getPackageChange")


@login_required
def getPackageChangeRequestsJS(request):
    packageChangeRequestList = None
    try:
        # Retrieve the package change requests
        packageChangeRequestList = list(
            PackageChangerequest.objects.filter(
                is_active=True,
                status="Pending Approval",  # Match the status field name
            )
            .annotate(
                # Concatenating child code and name
                child_info=Concat(
                    F("child__admission_number"),  # Assuming `child_code` field exists
                    Value(" - "),
                    F("child__child_first_name"),
                    Value(" "),
                    F("child__child_last_name"),
                ),
                # Annotate old package as the non-null value between old_fixed and old_flexed packages
                old_package=Coalesce(
                    F("old_fixed_package__package_name"),
                    F("old_flexed_package__package_name"),
                ),
                # Annotate new package as the non-null value between new_fixed and new_flexed packages
                new_package=Coalesce(
                    F("new_fixed_package__package_name"),
                    F("new_flexed_package__package_name"),
                ),
                # Annotate old holiday package
                old_holiday_package_name=F("old_holiday_package__package_name"),
                # Annotate new holiday package
                new_holiday_package_name=F("new_holiday_package__package_name"),
            )
            .values(
                "id",  # ID of the package change request
                "child_info",
                "old_package",  # Old package (either fixed or flexed)
                "new_package",  # New package (either fixed or flexed)
                "old_holiday_package_name",  # Old Holiday Package
                "new_holiday_package_name",  # New Holiday Package
                "date_requested",  # Date requested
                "reason_for_request",  # Reason(s) for change
                "user_created",  # Reason(s) for change
                "effective_date",
            )
        )

    except Exception as e:
        messages.error(request, e)

    finally:
        return JsonResponse(packageChangeRequestList, safe=False)


@login_required
def getPackageChangeApproval(request):
    return render(
        request,
        "../templates/packagechangeslist.html",
        {"UserName": request.user.username},
    )


@login_required
@transaction.atomic
def approvePackageChange(request):
    status = None
    try:
        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(
                request,
                "You are not authorized to performe this operation.",
            )
        elif request.GET.get("id") is not None:
            objPackageChangeRequest = PackageChangerequest.objects.get(
                pk=request.GET.get("id")
            )

            with transaction.atomic():
                objPackageChangeRequest.status = "Approved"
                objPackageChangeRequest.user_updated = request.user.username
                objPackageChangeRequest.date_updated = datetime.now()
                objPackageChangeRequest.save()

                # Changing the package update the old mapping effective date
                objChildPackageMapping = ChildPackageMapping.objects.get(
                    child_id=objPackageChangeRequest.child.id, is_active=True
                )
                if objChildPackageMapping:
                    objChildPackageMapping.effective_to = (
                        objPackageChangeRequest.effective_date
                    )
                    objChildPackageMapping.user_updated = request.user.username
                    objChildPackageMapping.is_active = False
                    objChildPackageMapping.save()

                else:
                    messages.error(
                        request,
                        "No package mappings",
                    )
                # Adding the new mapping
                objChildPackageMapping = ChildPackageMapping()
                objChildPackageMapping.child = objPackageChangeRequest.child
                objChildPackageMapping.normal_package = (
                    objPackageChangeRequest.new_fixed_package
                )
                objChildPackageMapping.flex_package = (
                    objPackageChangeRequest.new_flexed_package
                )
                if objPackageChangeRequest.new_holiday_package:
                    objChildPackageMapping.holiday_package = (
                        objPackageChangeRequest.new_holiday_package
                    )
                else:
                    objChildPackageMapping.holiday_package = (
                        objPackageChangeRequest.old_holiday_package
                    )
                objChildPackageMapping.effective_from = (
                    objPackageChangeRequest.effective_date
                )
                objChildPackageMapping.user_updated = request.user.username
                objChildPackageMapping.save()
                status = "Approved"
        else:
            messages.error(request, "Package request not found")
            status = "Not Found"

    except Exception as e:
        messages.error(request, e)

    finally:
        return JsonResponse(status, safe=False)


@login_required
def getCenterChange(request):
    requestform = CreateCenterChangeRequestForm()
    return render(
        request,
        "../templates/centerchange.html",
        {"form": requestform, "UserName": request.user.username},
    )


@login_required
def getCenterChangeRequestsJS(request):
    centerChangeRequestList = None
    try:
        # Retrieve the package change requests
        centerChangeRequestList = list(
            CenterChangerequest.objects.filter(
                is_active=True,
                status="Pending Approval",  # Match the status field name
            )
            .annotate(
                # Concatenating child code and name
                child_info=Concat(
                    F("child__admission_number"),  # Assuming `child_code` field exists
                    Value(" - "),
                    F("child__child_first_name"),
                    Value(" "),
                    F("child__child_last_name"),
                ),
                # Annotate old package as the non-null value between old_fixed and old_flexed packages
                old_center=Coalesce(
                    F("old_center__daycare_code"),
                    F("old_center__daycare_name"),
                ),
                # Annotate new package as the non-null value between new_fixed and new_flexed packages
                new_center=Coalesce(
                    F("new_center__daycare_code"),
                    F("new_center__daycare_name"),
                ),
                # Annotate old holiday package
                old_Branch=F("old_Branch__branch_name"),
                # Annotate new holiday package
                new_Branch=F("new_Branch__branch_name"),
            )
            .values(
                "id",  # ID of the package change request
                "child_info",
                "old_center",
                "new_center",
                "old_Branch",
                "new_Branch",
                "date_requested",  # Date requested
                "reason_for_request",  # Reason(s) for change
                "user_created",  # Reason(s) for change
                "effective_date",
            )
        )

    except Exception as e:
        messages.error(request, e)

    finally:
        return JsonResponse(centerChangeRequestList, safe=False)


@login_required
def getChildrenList(request):
    form = ChildSearchForm()
    return render(
        request,
        "../templates/childrenlist.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getChildrenDetails(request):
    form = ChildSearchForm()
    return render(
        request,
        "../templates/childdet.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getAllChildDetailsByIdJS(request, pk):
    child_data = None

    try:
        if pk is not None:
            child = get_object_or_404(Child, pk=pk)

            # Retrieve enrollment details
            enrollments = ChildEnrollment.objects.get(child=child.id, is_active=True)
            if enrollments == None:
                # Retrieve package mappings
                package_mappings = ChildPackageMapping.objects.filter(
                    child=child.id, is_active=True
                )

            # Retrieve package change requests
            package_changes = PackageChangerequest.objects.filter(
                child=child, is_active=True
            )

            # Retrieve attendance logs for the current month
            current_month = datetime.now().month
            current_year = datetime.now().year
            attendance_logs = AttendanceLog.objects.filter(
                child=child,
                date_logged__month=current_month,
                date_logged__year=current_year,
            )

            # Retrieve invoices for the current month
            invoices = Invoice.objects.filter(child=child)

            # Prepare the data to return
            child_data = {
                "child": {
                    "admission_number": child.admission_number,
                    "first_name": child.child_first_name,
                    "last_name": child.child_last_name,
                    "date_of_birth": child.date_of_birth,
                    "fathers_name": child.fathers_name,
                    "mothers_name": child.mothers_name,
                    "address": f"{child.address_line1}, {child.address_line2}, {child.address_line3}",
                    "email": child.email_address,
                    "admission_date": child.admission_date,
                    "is_enrolled": child.is_enrolled,
                    "child_image": child.child_image,
                    # Add more fields as needed
                },
                "enrollments": [
                    {
                        "enrollment_code": enrollment.enrollment_code,
                        "enrollment_date": enrollment.enrollment_date,
                        "status": enrollment.status,
                        "branch": enrollment.branch.id,
                        "center": enrollment.center.id,
                    }
                    for enrollment in enrollments
                ],
                "package_mappings": [
                    {
                        "normal_package": mapping.normal_package.id
                        if mapping.normal_package
                        else None,
                        "holiday_package": mapping.holiday_package.id
                        if mapping.holiday_package
                        else None,
                        "flex_package": mapping.flex_package.id
                        if mapping.flex_package
                        else None,
                        "effective_from": mapping.effective_from,
                        "effective_to": mapping.effective_to,
                    }
                    for mapping in package_mappings
                ],
                "package_change_requests": [
                    {
                        "old_fixed_package": change.old_fixed_package.id
                        if change.old_fixed_package
                        else None,
                        "new_fixed_package": change.new_fixed_package.id
                        if change.new_fixed_package
                        else None,
                        "date_requested": change.date_requested,
                        "status": change.status,
                        "reason_for_request": change.reason_for_request,
                    }
                    for change in package_changes
                ],
                "attendance_logs": [
                    {
                        "date_logged": attendance.date_logged,
                        "time_logged": attendance.time_logged,
                        "branch": attendance.branch.id,
                        "day_care": attendance.day_care.id,
                    }
                    for attendance in attendance_logs
                ],
                "invoices": [
                    {
                        "invoice_no": invoice.invoice_no,
                        "invoice_date": invoice.invoice_date,
                        "amount": invoice.amount,
                        "paid_amount": invoice.paid_amount,
                        "balance_amount": invoice.balance_amount,
                        "receipt_no": invoice.receipt_no,
                    }
                    for invoice in invoices
                ],
            }
    except Exception as e:
        messages.error(request, e)

    return JsonResponse(child_data, safe=False)


@login_required
def getInvoice(request):
    form = GenerateInvoiceForm()
    return render(
        request,
        "../templates/invoice.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def generateInvoiceEligibilityJS(request):
    try:
        # Get parameters from the request
        child_id = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")

        # If dates are not provided, default to last month's first and last date
        if not from_date or not to_date:
            today = datetime.today()
            first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(
                day=1
            )
            last_day_last_month = today.replace(day=1) - timedelta(days=1)

            from_date = first_day_last_month.date()
            to_date = last_day_last_month.date()
        else:
            # Parse the provided dates
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Create a date range to query attendance logs
        date_range = Q(date_logged__range=(from_date, to_date))

        # Filter attendance records based on the child_id and date range
        attendance_logs = AttendanceLog.objects.filter(date_range)

        if child_id:
            attendance_logs = attendance_logs.filter(child=child_id)

        # Group attendance logs by child_id and date_logged
        attendance_dict = {}
        for log in attendance_logs:
            child_id = log.child_id
            date_logged = log.date_logged
            if child_id not in attendance_dict:
                attendance_dict[child_id] = {}
            if date_logged not in attendance_dict[child_id]:
                attendance_dict[child_id][date_logged] = []
            attendance_dict[child_id][date_logged].append(log.time_logged)

        # List to store children with status
        children_status = []

        # Iterate through each child and check attendance
        for child_id, attendance_dates in attendance_dict.items():
            child = Child.objects.get(id=child_id)
            has_missing_records = False
            missing_dates = []

            for date_logged, time_logs in attendance_dates.items():
                if len(time_logs) < 2:  # Check for missing IN or OUT logs
                    has_missing_records = True
                    missing_dates.append(str(date_logged))

            if has_missing_records:
                children_status.append(
                    {
                        "child_id": child.id,
                        "child_name": f"{child.admission_number} - {child.child_first_name} {child.child_last_name}",
                        "status": "Missing Records",
                        "missing_dates": missing_dates,
                    }
                )
            else:
                children_status.append(
                    {
                        "child_id": child.id,
                        "child_name": f"{child.admission_number} - {child.child_first_name} {child.child_last_name}",
                        "status": "Eligible for Invoice",
                        "from_date": from_date,
                        "to_date": to_date,
                    }
                )
        print(children_status)
        # Return response with the combined list
        return JsonResponse(
            {
                "children_status": children_status,
            }
        )

    except Exception as e:
        # Log the error and return a response
        messages.error(request, f"Error generating invoice: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def generateInvoiceJS(request):
    try:
        child_id = request.GET.get("child_id")
        from_date_str = request.GET.get("from_date")
        to_date_str = request.GET.get("to_date")

        if not all([child_id, from_date_str, to_date_str]):
            return JsonResponse({"error": "Missing parameters"}, status=400)

        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

        total_invoice = Decimal("0.00")

        # Get child's package mapping for the period
        package_mapping = ChildPackageMapping.objects.filter(
            child_id=child_id, is_active=True
        ).first()

        if not package_mapping:
            return JsonResponse({"error": "No package mapping found for the child."})

        is_flex = package_mapping.flex_package is not None
        is_holiday = package_mapping.is_holiday_package

        package = (
            package_mapping.flex_package
            if is_flex
            else (
                package_mapping.holiday_package
                if is_holiday
                else package_mapping.normal_package
            )
        )

        if not package:
            return JsonResponse({"error": "No valid package assigned."}, status=404)

        expected_days = package.no_days_months or 0
        package_total = package.package_total or Decimal("0.00")

        # Attendance logs in date range
        attendance_logs = AttendanceLog.objects.filter(
            child_id=child_id, date_logged__range=(from_date, to_date)
        ).order_by("date_logged", "time_logged")

        # Holidays in this range
        holidays = set(
            Holiday.objects.filter(
                start_date__lte=to_date, end_date__gte=from_date
            ).values_list("start_date", flat=True)
        )

        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        present_days = 0
        holiday_attendance = 0

        extra_hour_mapping = PackageExtraHoursMapping.objects.filter(
            fixed_package=package if not is_flex else None,
            flex_package=package if is_flex else None,
        ).first()

        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))
            first_log = logs_sorted[0]
            last_log = logs_sorted[-1]

            present_days += 1
            is_holiday = log_date in holidays

            # Extra hours calculation
            log_time_out = last_log.time_logged or time(0, 0)
            extra_slots = ExtraHoursAfter530.objects.filter(
                package_type=package.package_type,
                from_time__lte=log_time_out,
                to_time__gte=log_time_out,
                effective_from__lte=log_date,
            ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

            for slot in extra_slots:
                total_invoice += slot.extra_rate

            # Holiday attendance charge
            if is_holiday and package_mapping.holiday_package:
                holiday_attendance += 1
                daily_holiday_rate = (
                    package_mapping.holiday_package.package_total
                    / Decimal(expected_days or 1)
                )
                total_invoice += daily_holiday_rate

        # Adjust package fee if attendance is less than 50%
        if expected_days > 0 and (present_days / expected_days) < 0.5:
            package_total = package_total / 2

        total_invoice += package_total

        return JsonResponse(
            {
                "child_id": child_id,
                "from_date": str(from_date),
                "to_date": str(to_date),
                "present_days": present_days,
                "holiday_attendance_days": holiday_attendance,
                "base_package_charge": float(package_total),
                "total_invoice": float(total_invoice),
            }
        )

    except Exception as e:
        # Log the error and return a response
        messages.error(request, f"Error generating invoice: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
