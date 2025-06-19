import calendar
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
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

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
    RecordPaymentForm,
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
    # HolidayType,
    InvoiceMemo,
    PackageChangerequest,
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
    children = Child.objects.filter(is_active=True, is_enrolled=True).order_by(
        "admission_number"
    )
    form = GenerateInvoiceForm()
    return render(
        request,
        "../templates/invoice.html",
        {
            "form": form,
            "UserName": request.user.username,
            "children": children,
        },
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


def calculate_detailed_invoice(
    child, package_mapping, enrollment, from_date, to_date, month, year
):
    """
    Calculate detailed invoice data for memo generation
    Based on your existing generateInvoiceJS logic but with more details
    """
    try:
        total_invoice = Decimal("0.00")

        # Determine package type and get package details
        is_flex = package_mapping.flex_package is not None
        is_normal = package_mapping.normal_package is not None
        is_holiday = package_mapping.holiday_package is not None

        package = (
            package_mapping.flex_package
            if is_flex
            else (
                package_mapping.normal_package
                if is_normal  # ✅ Uses normal flag for normal!
                else None  # ✅ No primary package found
            )
        )

        if not package:
            raise Exception("No valid package assigned.")

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # Get attendance logs in date range
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(from_date, to_date)
        ).order_by("date_logged", "time_logged")

        # Get holidays in this range
        holidays = set(
            Holiday.objects.filter(
                start_date__lte=to_date, end_date__gte=from_date
            ).values_list("start_date", flat=True)
        )

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        present_days = 0
        holiday_attendance_days = 0
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")

        # Process each attendance day
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance
                present_days += 1
                first_log = logs_sorted[0]
                last_log = logs_sorted[-1]

                is_holiday_day = log_date in holidays

                # Calculate extra hours charges
                log_time_out = last_log.time_logged or time(0, 0)
                extra_slots = ExtraHoursAfter530.objects.filter(
                    package_type=package.package_type,
                    from_time__lte=log_time_out,
                    to_time__gte=log_time_out,
                    effective_from__lte=log_date,
                ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

                for slot in extra_slots:
                    extra_hours_charge += slot.extra_rate

                # Holiday attendance charge
                if is_holiday_day and package_mapping.holiday_package:
                    holiday_attendance_days += 1
                    daily_holiday_rate = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days)
                    )
                    holiday_charge += daily_holiday_rate

        # Calculate attendance percentage
        attendance_percentage = (
            (present_days / expected_days * 100) if expected_days > 0 else 0
        )

        # Apply half charge if attendance is less than 50%
        is_half_charge = attendance_percentage < 50
        base_package_charge = package_total / 2 if is_half_charge else package_total

        # Calculate subtotal
        subtotal = base_package_charge + extra_hours_charge + holiday_charge

        # Apply discount if any
        discount_amount = Decimal("0.00")
        if enrollment.discount and enrollment.discount.status == "Approved":
            discount_amount = subtotal * (enrollment.discount.discount_rate / 100)

        final_total = subtotal - discount_amount

        return {
            "child_id": child.id,
            "package_name": package.package_name,
            "package_total": float(package_total),
            "expected_days": expected_days,
            "present_days": present_days,
            "attendance_percentage": round(attendance_percentage, 2),
            "is_half_charge": is_half_charge,
            "base_package_charge": float(base_package_charge),
            "extra_hours_charge": float(extra_hours_charge),
            "holiday_attendance_days": holiday_attendance_days,
            "holiday_charge": float(holiday_charge),
            "subtotal": float(subtotal),
            "discount_amount": float(discount_amount),
            "final_total": float(final_total),
            "total_invoice": float(final_total),  # For compatibility with existing code
        }

    except Exception as e:
        raise Exception(f"Error calculating invoice details: {str(e)}")


@login_required
def getInvoiceMemos(request):
    """Display invoice memo management page"""
    from datetime import datetime

    try:
        # Get children for dropdown
        children = Child.objects.filter(is_active=True, is_enrolled=True).order_by(
            "admission_number"
        )

        # Generate year range (current year and 2 previous years)
        current_year = datetime.now().year
        year_range = [current_year - 2, current_year - 1, current_year]

        context = {
            "children": children,
            "year_range": year_range,
            "UserName": request.user.username,
        }

        return render(request, "invoice.html", context)

    except Exception as e:
        print(f"Error in getInvoiceMemos: {e}")
        return render(
            request,
            "invoice.html",
            context,
        )


@login_required
@transaction.atomic
def generateAndSaveInvoiceMemo(request):
    """Generate and save invoice memo with 3-month data"""
    try:
        if request.method == "POST":
            child_id = request.POST.get("child")
            month = request.POST.get("month")
            year = request.POST.get("year")

            if not all([child_id, month, year]):
                messages.error(request, "Missing required parameters")
                return redirect("core:view_invoice_memos")

            # Check if memo already exists for this month
            existing_memo = InvoiceMemo.objects.filter(
                child_id=child_id, year=int(year), month=int(month)
            ).first()

            if existing_memo:
                messages.error(
                    request,
                    f"Invoice memo already exists for {calendar.month_name[int(month)]} {year}",
                )
                return redirect("core:view_invoice_memos")

            # Generate memo code
            try:
                nextId = InvoiceMemo.objects.all().count() + 1
            except:
                nextId = 1
            memo_code = f"MO{nextId:03d}"

            # Get child details
            child = Child.objects.get(id=child_id)

            # Get package mapping and enrollment
            package_mapping = ChildPackageMapping.objects.filter(
                child_id=child_id, is_active=True
            ).first()

            enrollment = ChildEnrollment.objects.filter(
                child=child, status="Approved", is_active=True
            ).first()

            if not package_mapping or not enrollment:
                messages.error(
                    request, "No package mapping or enrollment found for the child."
                )
                return redirect("core:view_invoice_memos")

            # Calculate 3-month data using existing function
            three_month_data = calculate_three_month_invoice_data(child, month, year)

            # Get current month data for backward compatibility
            current_month_data = calculate_current_month_charges(
                child, package_mapping, enrollment, int(month), int(year)
            )

            # Helper function to convert Decimal to float for JSON storage
            def decimal_to_float(value):
                if isinstance(value, Decimal):
                    return float(value)
                return value

            # Save invoice memo with 3-month summary
            with transaction.atomic():
                memo = InvoiceMemo.objects.create(
                    # Basic info
                    memo_date=datetime.now().date(),
                    memo_code=memo_code,
                    child=child,
                    year=int(year),
                    month=int(month),
                    # Current month details (for backward compatibility)
                    package_name=current_month_data["package_name"],
                    package_base_fee=current_month_data["package_base_fee"],
                    days_attended=current_month_data["days_attended"],
                    expected_days=current_month_data["expected_days"],
                    attendance_percentage=current_month_data["attendance_percentage"],
                    is_half_charge_applied=current_month_data["is_half_charge"],
                    current_month_package_fee=current_month_data["package_fee"],
                    extra_hours_charge=current_month_data["extra_charges"],
                    holiday_attendance_days=current_month_data.get(
                        "holiday_attendance_days", 0
                    ),
                    holiday_charge=current_month_data["holiday_charges"],
                    discount_applied=current_month_data["discount"],
                    # Month totals
                    month_total_charge=current_month_data["total_charge"],
                    total_payments_received=Decimal("0.00"),
                    month_net_balance=current_month_data["total_charge"],
                    # NEW: 3-month summary
                    total_outstanding=three_month_data["summary"]["total_outstanding"],
                    grand_total=three_month_data["summary"]["grand_total"],
                    # Status and details
                    status="GENERATED",
                    branch_name=enrollment.branch.branch_name,
                    center_name=enrollment.center.daycare_name,
                    notes=f"Invoice generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    # Audit fields
                    user_created=request.user.username,
                )

                # Create 3 detail records - one for each month
                from .models import InvoiceMemoDetail

                # Month 1 - Outstanding/Credits
                try:
                    month1_month_num = 1
                    if three_month_data["month1"]["name"]:
                        month1_month_num = list(calendar.month_name).index(
                            three_month_data["month1"]["name"]
                        )
                except:
                    month1_month_num = 1

                detail1 = InvoiceMemoDetail.objects.create(
                    memo=memo,
                    month_sequence=1,
                    month=month1_month_num,
                    year=three_month_data["month1"]["year"] or int(year),
                    month_name=three_month_data["month1"]["name"] or "Unknown",
                    month_type="OUTSTANDING",
                    charge_amount=three_month_data["month1"]["charge"],
                    payment_amount=three_month_data["month1"]["payments"],
                    balance_amount=three_month_data["month1"]["balance"],
                    calculation_details={
                        "status": three_month_data["month1"]["status"],
                        "credit": decimal_to_float(
                            three_month_data["month1"]["credit"]
                        ),
                    },
                    user_created=request.user.username,
                )

                # Month 2 - Calculated with attendance
                try:
                    month2_month_num = int(month)
                    if three_month_data["month2"]["name"]:
                        month2_month_num = list(calendar.month_name).index(
                            three_month_data["month2"]["name"]
                        )
                except:
                    month2_month_num = int(month)

                detail2 = InvoiceMemoDetail.objects.create(
                    memo=memo,
                    month_sequence=2,
                    month=month2_month_num,
                    year=three_month_data["month2"]["year"] or int(year),
                    month_name=three_month_data["month2"]["name"]
                    or calendar.month_name[int(month)],
                    month_type="CALCULATED",
                    charge_amount=three_month_data["month2"]["charge"],
                    payment_amount=three_month_data["month2"]["payments"],
                    balance_amount=three_month_data["month2"]["balance"],
                    calculation_details={
                        "package_name": three_month_data["month2"]["package_name"],
                        "package_fee": decimal_to_float(
                            three_month_data["month2"]["package_fee"]
                        ),
                        "extra_charges": decimal_to_float(
                            three_month_data["month2"]["extra_charges"]
                        ),
                        "holiday_charges": decimal_to_float(
                            three_month_data["month2"]["holiday_charges"]
                        ),
                        "discount": decimal_to_float(
                            three_month_data["month2"]["discount"]
                        ),
                        "days_attended": three_month_data["month2"]["days_attended"],
                        "expected_days": three_month_data["month2"]["expected_days"],
                        "attendance_percentage": decimal_to_float(
                            three_month_data["month2"]["attendance_percentage"]
                        ),
                        "is_half_charge": three_month_data["month2"]["is_half_charge"],
                    },
                    user_created=request.user.username,
                )

                # Month 3 - Advance payment
                try:
                    month3_month_num = int(month) + 1
                    if month3_month_num > 12:
                        month3_month_num = 1
                    if three_month_data["month3"]["name"]:
                        month3_month_num = list(calendar.month_name).index(
                            three_month_data["month3"]["name"]
                        )
                except:
                    month3_month_num = int(month) + 1
                    if month3_month_num > 12:
                        month3_month_num = 1

                detail3 = InvoiceMemoDetail.objects.create(
                    memo=memo,
                    month_sequence=3,
                    month=month3_month_num,
                    year=three_month_data["month3"]["year"] or int(year),
                    month_name=three_month_data["month3"]["name"]
                    or calendar.month_name[month3_month_num],
                    month_type="ADVANCE",
                    charge_amount=three_month_data["month3"]["charge"],
                    payment_amount=three_month_data["month3"]["payments"],
                    balance_amount=three_month_data["month3"]["balance"],
                    calculation_details={
                        "package_name": three_month_data["month3"]["package_name"],
                        "package_fee": decimal_to_float(
                            three_month_data["month3"]["package_fee"]
                        ),
                        "extra_charges": decimal_to_float(
                            three_month_data["month3"]["extra_charges"]
                        ),
                        "holiday_charges": decimal_to_float(
                            three_month_data["month3"]["holiday_charges"]
                        ),
                        "discount": decimal_to_float(
                            three_month_data["month3"]["discount"]
                        ),
                        "expected_days": three_month_data["month3"]["expected_days"],
                    },
                    user_created=request.user.username,
                )

            messages.success(
                request,
                f"Invoice memo {memo.memo_code} generated successfully for {calendar.month_name[int(month)]} {year}",
            )

    except Exception as e:
        import traceback

        print(f"DEBUG: Exception occurred: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        messages.error(request, f"Error generating invoice memo: {str(e)}")

    return redirect("core:view_invoice_memos")


@login_required
def getInvoiceMemoByID(request, pk):
    """Get detailed invoice memo with 3-month data for display"""
    try:
        memo = get_object_or_404(InvoiceMemo, pk=pk)

        # Get the 3 detail records
        details = memo.details.all().order_by("month_sequence")

        if details.count() == 3:
            # New format - return 3-month data from stored details
            month1_detail = details[0]  # Outstanding
            month2_detail = details[1]  # Calculated
            month3_detail = details[2]  # Advance

            memo_data = {
                # Basic memo info
                "id": memo.id,
                "memo_code": memo.memo_code,
                "memo_date": memo.memo_date.strftime("%Y-%m-%d"),
                "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                "child_admission": memo.child.admission_number,
                "year": memo.year,
                "status": memo.status,
                "branch_name": memo.branch_name,
                "center_name": memo.center_name,
                "notes": memo.notes or "",
                # 3-month breakdown
                "month1": {
                    "name": month1_detail.month_name,
                    "year": month1_detail.year,
                    "type": month1_detail.month_type,
                    "charge": float(month1_detail.charge_amount),
                    "payments": float(month1_detail.payment_amount),
                    "balance": float(month1_detail.balance_amount),
                    "details": month1_detail.calculation_details,
                },
                "month2": {
                    "name": month2_detail.month_name,
                    "year": month2_detail.year,
                    "type": month2_detail.month_type,
                    "charge": float(month2_detail.charge_amount),
                    "payments": float(month2_detail.payment_amount),
                    "balance": float(month2_detail.balance_amount),
                    "details": month2_detail.calculation_details,
                },
                "month3": {
                    "name": month3_detail.month_name,
                    "year": month3_detail.year,
                    "type": month3_detail.month_type,
                    "charge": float(month3_detail.charge_amount),
                    "payments": float(month3_detail.payment_amount),
                    "balance": float(month3_detail.balance_amount),
                    "details": month3_detail.calculation_details,
                },
                # Summary
                "summary": {
                    "total_outstanding": float(memo.total_outstanding),
                    "grand_total": float(memo.grand_total),
                },
                # Flag to indicate this is 3-month data
                "is_three_month_format": True,
            }

        else:
            # Fallback for old single-month format (backward compatibility)
            memo_data = {
                # Basic memo info
                "id": memo.id,
                "memo_code": memo.memo_code,
                "memo_date": memo.memo_date.strftime("%Y-%m-%d"),
                "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                "child_admission": memo.child.admission_number,
                "month_name": memo.get_month_name(),
                "year": memo.year,
                "status": memo.status,
                # Single month data (old format)
                "package_name": memo.package_name,
                "days_attended": memo.days_attended,
                "expected_days": memo.expected_days,
                "attendance_percentage": float(memo.attendance_percentage),
                "is_half_charge_applied": memo.is_half_charge_applied,
                "current_month_fee": float(memo.current_month_package_fee),
                "extra_hours_charge": float(memo.extra_hours_charge),
                "holiday_charge": float(memo.holiday_charge),
                "holiday_attendance_days": memo.holiday_attendance_days,
                "discount_applied": float(memo.discount_applied),
                "month_total_charge": float(memo.month_total_charge),
                "total_payments_received": float(memo.total_payments_received),
                "month_net_balance": float(memo.month_net_balance),
                "branch_name": memo.branch_name,
                "center_name": memo.center_name,
                "notes": memo.notes or "",
                # Flag to indicate this is old single-month format
                "is_three_month_format": False,
            }

        return JsonResponse(memo_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def deleteInvoiceMemo(request, pk):
    """Delete (deactivate) invoice memo"""
    try:
        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(request, "You are not authorized to perform this operation.")
        else:
            memo = get_object_or_404(InvoiceMemo, pk=pk)
            memo.is_active = False
            memo.user_updated = request.user.username
            memo.save()
        return JsonResponse("Success", safe=False)
    except Exception as e:
        messages.error(request, e)
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def previewInvoiceMemo(request):
    """Preview invoice memo calculations before generating"""
    try:
        child_id = request.GET.get("child")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Check if memo already exists
        existing_memo = InvoiceMemo.objects.filter(
            child_id=child_id, year=int(year), month=int(month)
        ).first()

        if existing_memo:
            return JsonResponse(
                {
                    "error": f"Invoice memo already exists for {calendar.month_name[int(month)]} {year}",
                    "existing_memo_code": existing_memo.memo_code,
                },
                status=400,
            )

        # Get the date range for the month
        first_day = datetime(int(year), int(month), 1).date()
        last_day = datetime(
            int(year), int(month), calendar.monthrange(int(year), int(month))[1]
        ).date()

        # Get child details
        child = Child.objects.get(id=child_id)

        # Get package mapping for the period
        package_mapping = ChildPackageMapping.objects.filter(
            child_id=child_id, is_active=True
        ).first()

        if not package_mapping:
            return JsonResponse(
                {"error": "No package mapping found for the child."}, status=400
            )

        # Get enrollment details
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not enrollment:
            return JsonResponse(
                {"error": "No enrollment found for the child."}, status=400
            )

        # Calculate invoice memo data
        memo_calculation = calculate_detailed_invoice(
            child, package_mapping, enrollment, first_day, last_day, month, year
        )

        # Get previous month's data
        previous_month = int(month) - 1 if int(month) > 1 else 12
        previous_year = int(year) if int(month) > 1 else int(year) - 1

        previous_memo = InvoiceMemo.objects.filter(
            child=child, year=previous_year, month=previous_month
        ).first()

        # Calculate previous month details
        previous_outstanding = Decimal("0.00")
        previous_payment = Decimal("0.00")
        previous_receipt = ""

        if previous_memo:
            previous_outstanding = previous_memo.total_amount
            previous_payment = previous_memo.current_month_payment_amount
            previous_receipt = previous_memo.current_month_payment_receipt or ""

        remaining_balance = previous_outstanding - previous_payment

        # Prepare preview data
        preview_data = {
            "child_name": f"{child.child_first_name} {child.child_last_name}",
            "child_admission": child.admission_number,
            "month_name": calendar.month_name[int(month)],
            "year": year,
            "package_name": memo_calculation["package_name"],
            "days_attended": memo_calculation["present_days"],
            "expected_days": memo_calculation["expected_days"],
            "attendance_percentage": memo_calculation["attendance_percentage"],
            "is_half_charge": memo_calculation["is_half_charge"],
            # Previous month details
            "previous_month_name": calendar.month_name[previous_month],
            "previous_outstanding": float(previous_outstanding),
            "previous_payment": float(previous_payment),
            "previous_receipt": previous_receipt,
            "remaining_balance": float(remaining_balance),
            # Current month charges
            "base_package_charge": memo_calculation["base_package_charge"],
            "extra_hours_charge": memo_calculation["extra_hours_charge"],
            "holiday_charge": memo_calculation["holiday_charge"],
            "holiday_attendance_days": memo_calculation["holiday_attendance_days"],
            # Totals
            "subtotal": memo_calculation["subtotal"],
            "discount_amount": memo_calculation["discount_amount"],
            "current_month_total": memo_calculation["final_total"],
            "grand_total": memo_calculation["final_total"] + float(remaining_balance),
            # Branch and center details
            "branch_name": enrollment.branch.branch_name,
            "center_name": enrollment.center.daycare_name,
        }

        return JsonResponse({"success": True, "preview": preview_data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def calculate_three_month_display_data(child, current_month, current_year):
    """
    Calculate 3-month invoice display data dynamically
    Logic: Get stored memos for previous months and calculate current month
    """
    try:
        import calendar
        from decimal import Decimal

        current_month_int = int(current_month)
        current_year_int = int(current_year)

        # Calculate previous months
        if current_month_int > 1:
            previous_month = current_month_int - 1
            previous_year = current_year_int
        else:
            previous_month = 12
            previous_year = current_year_int - 1

        if previous_month > 1:
            month_before_previous = previous_month - 1
            month_before_previous_year = previous_year
        else:
            month_before_previous = 12
            month_before_previous_year = previous_year - 1

        # Get month names
        current_month_name = calendar.month_name[current_month_int]
        previous_month_name = calendar.month_name[previous_month]
        month_before_previous_name = calendar.month_name[month_before_previous]

        # Get stored data for previous months
        month_before_previous_memo = InvoiceMemo.objects.filter(
            child=child,
            month=month_before_previous,
            year=month_before_previous_year,
            is_active=True,
        ).first()

        previous_month_memo = InvoiceMemo.objects.filter(
            child=child, month=previous_month, year=previous_year, is_active=True
        ).first()

        # Calculate outstanding amounts
        total_outstanding = Decimal("0.00")

        if (
            month_before_previous_memo
            and month_before_previous_memo.month_net_balance > 0
        ):
            total_outstanding += month_before_previous_memo.month_net_balance

        if previous_month_memo and previous_month_memo.month_net_balance > 0:
            total_outstanding += previous_month_memo.month_net_balance

        # Calculate current month
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not package_mapping or not enrollment:
            raise Exception("No package mapping or enrollment found")

        current_month_data = calculate_current_month_charges(
            child, package_mapping, enrollment, current_month_int, current_year_int
        )

        # Prepare display data
        display_data = {
            "month_before_previous": {
                "name": month_before_previous_name,
                "year": month_before_previous_year,
                "charge": month_before_previous_memo.month_total_charge
                if month_before_previous_memo
                else Decimal("0.00"),
                "payments": month_before_previous_memo.total_payments_received
                if month_before_previous_memo
                else Decimal("0.00"),
                "balance": month_before_previous_memo.month_net_balance
                if month_before_previous_memo
                else Decimal("0.00"),
                "status": month_before_previous_memo.status
                if month_before_previous_memo
                else "No Record",
            },
            "previous_month": {
                "name": previous_month_name,
                "year": previous_year,
                "charge": previous_month_memo.month_total_charge
                if previous_month_memo
                else Decimal("0.00"),
                "payments": previous_month_memo.total_payments_received
                if previous_month_memo
                else Decimal("0.00"),
                "balance": previous_month_memo.month_net_balance
                if previous_month_memo
                else Decimal("0.00"),
                "status": previous_month_memo.status
                if previous_month_memo
                else "No Record",
                "package_fee": previous_month_memo.current_month_package_fee
                if previous_month_memo
                else Decimal("0.00"),
                "extra_charges": previous_month_memo.extra_hours_charge
                if previous_month_memo
                else Decimal("0.00"),
                "holiday_charges": previous_month_memo.holiday_charge
                if previous_month_memo
                else Decimal("0.00"),
                "days_attended": previous_month_memo.days_attended
                if previous_month_memo
                else 0,
                "expected_days": previous_month_memo.expected_days
                if previous_month_memo
                else 22,
                "attendance_percentage": previous_month_memo.attendance_percentage
                if previous_month_memo
                else 0,
            },
            "current_month": {
                "name": current_month_name,
                "year": current_year_int,
                "package_name": current_month_data["package_name"],
                "package_fee": current_month_data["package_fee"],
                "extra_charges": current_month_data["extra_charges"],
                "holiday_charges": current_month_data["holiday_charges"],
                "discount": current_month_data["discount"],
                "total_charge": current_month_data["total_charge"],
                "days_attended": current_month_data["days_attended"],
                "expected_days": current_month_data["expected_days"],
                "attendance_percentage": current_month_data["attendance_percentage"],
                "is_half_charge": current_month_data["is_half_charge"],
            },
            "summary": {
                "total_outstanding": total_outstanding,
                "current_month_charge": current_month_data["total_charge"],
                "grand_total": total_outstanding + current_month_data["total_charge"],
            },
        }

        return display_data

    except Exception as e:
        raise Exception(f"Error calculating 3-month display: {str(e)}")


def calculate_current_month_charges(child, package_mapping, enrollment, month, year):
    """Calculate current month charges (fresh calculation)"""
    try:
        import calendar
        from collections import defaultdict
        from datetime import datetime, time

        from django.db.models import Q

        # For current month, calculate up to today or end of month
        today = datetime.now().date()
        first_day = datetime(year, month, 1).date()

        if today.year == year and today.month == month:
            last_day = today
        else:
            last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # Get package details
        is_flex = package_mapping.flex_package is not None
        package = (
            package_mapping.flex_package if is_flex else package_mapping.normal_package
        )

        if not package:
            raise Exception("No valid package assigned.")

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # Get attendance logs
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day)
        ).order_by("date_logged", "time_logged")

        # Get holidays
        holidays = set(
            Holiday.objects.filter(
                start_date__lte=last_day, end_date__gte=first_day
            ).values_list("start_date", flat=True)
        )

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        present_days = 0
        holiday_attendance_days = 0
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")

        # Process each attendance day
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance (in and out)
                present_days += 1
                last_log = logs_sorted[-1]

                is_holiday_day = log_date in holidays

                # Calculate extra hours charges
                log_time_out = last_log.time_logged or time(0, 0)
                extra_slots = ExtraHoursAfter530.objects.filter(
                    package_type=package.package_type,
                    from_time__lte=log_time_out,
                    to_time__gte=log_time_out,
                    effective_from__lte=log_date,
                ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

                for slot in extra_slots:
                    extra_hours_charge += slot.extra_rate

                # Holiday attendance charge
                if is_holiday_day and package_mapping.holiday_package:
                    holiday_attendance_days += 1
                    daily_holiday_rate = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days)
                    )
                    holiday_charge += daily_holiday_rate

        # Calculate attendance percentage
        attendance_percentage = (
            (present_days / expected_days * 100) if expected_days > 0 else 0
        )

        # Apply attendance-based charging rules
        is_half_charge = False

        if attendance_percentage == 0:
            package_fee = Decimal("0.00")  # No attendance = no charge
        elif attendance_percentage < 50:
            package_fee = package_total / 2  # Less than 50% = half charge
            is_half_charge = True
        else:
            package_fee = package_total  # 50% or more = full charge

        # Calculate subtotal
        subtotal = package_fee + extra_hours_charge + holiday_charge

        # Apply discount
        discount_amount = Decimal("0.00")
        if enrollment.discount and enrollment.discount.status == "Approved":
            discount_amount = subtotal * (enrollment.discount.discount_rate / 100)

        total_charge = subtotal - discount_amount

        return {
            "package_name": package.package_name,
            "package_base_fee": package_total,
            "days_attended": present_days,
            "expected_days": expected_days,
            "attendance_percentage": round(attendance_percentage, 2),
            "is_half_charge": is_half_charge,
            "package_fee": package_fee,
            "extra_charges": extra_hours_charge,
            "holiday_attendance_days": holiday_attendance_days,
            "holiday_charges": holiday_charge,
            "discount": discount_amount,
            "total_charge": total_charge,
        }

    except Exception as e:
        raise Exception(f"Error calculating current month charges: {str(e)}")


def apply_payment_settlement(child, payment_amount, receipt_number=None):
    """Apply payment to outstanding invoices using FIFO (oldest first)"""
    try:
        from decimal import Decimal

        remaining_payment = Decimal(str(payment_amount))
        settlement_breakdown = []

        # Get all outstanding memos (oldest first)
        outstanding_memos = InvoiceMemo.objects.filter(
            child=child, month_net_balance__gt=0, is_active=True
        ).order_by("year", "month")

        for memo in outstanding_memos:
            if remaining_payment <= 0:
                break

            outstanding_amount = memo.month_net_balance

            if remaining_payment >= outstanding_amount:
                # Payment covers full outstanding amount
                payment_applied = outstanding_amount
                remaining_payment -= outstanding_amount

                memo.add_payment(payment_applied, receipt_number)

                settlement_breakdown.append(
                    {
                        "memo_id": memo.id,
                        "month": memo.get_month_name(),
                        "year": memo.year,
                        "original_outstanding": float(outstanding_amount),
                        "payment_applied": float(payment_applied),
                        "remaining_balance": 0.00,
                        "status": "PAID",
                    }
                )

            else:
                # Payment partially covers outstanding amount
                payment_applied = remaining_payment

                memo.add_payment(payment_applied, receipt_number)

                settlement_breakdown.append(
                    {
                        "memo_id": memo.id,
                        "month": memo.get_month_name(),
                        "year": memo.year,
                        "original_outstanding": float(outstanding_amount),
                        "payment_applied": float(payment_applied),
                        "remaining_balance": float(
                            outstanding_amount - payment_applied
                        ),
                        "status": "PARTIAL",
                    }
                )

                remaining_payment = Decimal("0.00")

        return {
            "total_payment": float(payment_amount),
            "payment_applied": float(Decimal(str(payment_amount)) - remaining_payment),
            "excess_payment": float(remaining_payment),
            "settlement_breakdown": settlement_breakdown,
        }

    except Exception as e:
        raise Exception(f"Error applying payment settlement: {str(e)}")


@login_required
def previewThreeMonthInvoice(request):
    """Preview 3-month invoice display (dynamic calculation)"""
    try:
        child_id = request.GET.get("child")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)

        # Calculate 3-month display data
        display_data = calculate_three_month_display_data(child, month, year)

        # Format response for frontend
        response_data = {
            "success": True,
            "child_name": f"{child.child_first_name} {child.child_last_name}",
            "child_admission": child.admission_number,
            # Month before previous
            "month_before_previous": {
                "name": display_data["month_before_previous"]["name"],
                "year": display_data["month_before_previous"]["year"],
                "charge": float(display_data["month_before_previous"]["charge"]),
                "payments": float(display_data["month_before_previous"]["payments"]),
                "balance": float(display_data["month_before_previous"]["balance"]),
                "status": display_data["month_before_previous"]["status"],
            },
            # Previous month
            "previous_month": {
                "name": display_data["previous_month"]["name"],
                "year": display_data["previous_month"]["year"],
                "charge": float(display_data["previous_month"]["charge"]),
                "payments": float(display_data["previous_month"]["payments"]),
                "balance": float(display_data["previous_month"]["balance"]),
                "status": display_data["previous_month"]["status"],
                "package_fee": float(display_data["previous_month"]["package_fee"]),
                "extra_charges": float(display_data["previous_month"]["extra_charges"]),
                "holiday_charges": float(
                    display_data["previous_month"]["holiday_charges"]
                ),
                "days_attended": display_data["previous_month"]["days_attended"],
                "attendance_percentage": float(
                    display_data["previous_month"]["attendance_percentage"]
                ),
            },
            # Current month
            "current_month": {
                "name": display_data["current_month"]["name"],
                "year": display_data["current_month"]["year"],
                "package_name": display_data["current_month"]["package_name"],
                "package_fee": float(display_data["current_month"]["package_fee"]),
                "extra_charges": float(display_data["current_month"]["extra_charges"]),
                "holiday_charges": float(
                    display_data["current_month"]["holiday_charges"]
                ),
                "discount": float(display_data["current_month"]["discount"]),
                "total_charge": float(display_data["current_month"]["total_charge"]),
                "days_attended": display_data["current_month"]["days_attended"],
                "attendance_percentage": float(
                    display_data["current_month"]["attendance_percentage"]
                ),
                "is_half_charge": display_data["current_month"]["is_half_charge"],
            },
            # Summary
            "summary": {
                "total_outstanding": float(
                    display_data["summary"]["total_outstanding"]
                ),
                "current_month_charge": float(
                    display_data["summary"]["current_month_charge"]
                ),
                "grand_total": float(display_data["summary"]["grand_total"]),
            },
        }

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def recordPayment(request):
    """Record payment against child's outstanding invoices"""
    try:
        if request.method == "POST":
            memo_number = request.POST.get("memo_number")
            payment_amount = request.POST.get("payment_amount")
            receipt_number = request.POST.get("receipt_number")
            payment_date = request.POST.get("payment_date")
            payment_method = request.POST.get("payment_method", "CASH")
            notes = request.POST.get("notes", "")

            if not all([memo_number, payment_amount]):
                messages.error(request, "Missing required parameters")
                return redirect("core:get_record_payment")

            memo = InvoiceMemo.objects.get(memo_code=memo_number)
            child = memo.child

            # Apply payment settlement (FIFO - oldest first)
            settlement_result = apply_payment_settlement(
                child, payment_amount, receipt_number
            )

            # Create payment transaction record for each settled memo
            if settlement_result["payment_applied"] > 0:
                payment_date_obj = (
                    datetime.strptime(payment_date, "%Y-%m-%d").date()
                    if payment_date
                    else datetime.now().date()
                )

                for settlement in settlement_result["settlement_breakdown"]:
                    memo = InvoiceMemo.objects.get(id=settlement["memo_id"])
                    PaymentTransaction.objects.create(
                        memo=memo,
                        amount=Decimal(str(settlement["payment_applied"])),
                        receipt_number=receipt_number,
                        payment_date=payment_date_obj,
                        payment_method=payment_method,
                        notes=f"{notes}. Settlement for {settlement['month']} {settlement['year']}",
                        user_created=request.user.username,
                    )

            # Create detailed success message
            settlement_message = (
                f"Payment of Rs.{payment_amount} applied successfully:\n"
            )
            for settlement in settlement_result["settlement_breakdown"]:
                settlement_message += f"• {settlement['month']} {settlement['year']}: Rs.{settlement['payment_applied']} ({settlement['status']})\n"

            if settlement_result["excess_payment"] > 0:
                settlement_message += f"• Excess payment: Rs.{settlement_result['excess_payment']} (will be credited to future invoices)"

            messages.success(request, settlement_message)

    except Exception as e:
        messages.error(request, f"Error recording payment: {str(e)}")

    return redirect("core:get_record_payment")


@login_required
def getChildOutstandingSummary(request):
    """Get outstanding summary for a child across all months"""
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # Get all outstanding memos
        outstanding_memos = InvoiceMemo.objects.filter(
            child=child, month_net_balance__gt=0, is_active=True
        ).order_by("year", "month")

        total_outstanding = Decimal("0.00")
        memo_breakdown = []

        for memo in outstanding_memos:
            total_outstanding += memo.month_net_balance
            memo_breakdown.append(
                {
                    "memo_id": memo.id,
                    "memo_code": memo.memo_code,
                    "month": memo.get_month_name(),
                    "year": memo.year,
                    "charge": float(memo.month_total_charge),
                    "payments": float(memo.total_payments_received),
                    "balance": float(memo.month_net_balance),
                    "status": memo.status,
                }
            )

        summary_data = {
            "child_name": f"{child.child_first_name} {child.child_last_name}",
            "child_admission": child.admission_number,
            "total_outstanding": float(total_outstanding),
            "outstanding_memos": memo_breakdown,
            "memo_count": len(memo_breakdown),
        }

        return JsonResponse(summary_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_record_payment(request):
    """Display record payment page"""
    form = RecordPaymentForm()
    context = {
        "form": form,
        "UserName": request.user.username,
    }
    return render(request, "record_payment.html", context)


@login_required
def getInvoiceMemosJS(request):
    """Return invoice memos data as JSON for DataTable with 3-month support"""
    try:
        print("=== DEBUG: getInvoiceMemosJS called ===")

        # Get all invoice memos - using correct field names
        memos = (
            InvoiceMemo.objects.select_related("child")
            .filter(is_active=True)
            .order_by("-date_created")
        )

        print(f"DEBUG: Found {memos.count()} memos")

        memo_data = []

        for memo in memos:
            try:
                # Get month name safely
                month_name = (
                    calendar.month_name[memo.month]
                    if memo.month and 1 <= memo.month <= 12
                    else "Unknown"
                )

                # Check if this memo has 3-month detail records
                details = memo.details.all().order_by("month_sequence")

                if details.count() == 3:
                    # NEW FORMAT: Return 3-month data
                    month1_detail = details[0]  # Outstanding
                    month2_detail = details[1]  # Calculated
                    month3_detail = details[2]  # Advance

                    # Build month_breakdown step by step to avoid dict issues
                    month1_data = {
                        "name": str(month1_detail.month_name),
                        "year": int(month1_detail.year),
                        "type": str(month1_detail.month_type),
                        "charge": float(month1_detail.charge_amount),
                        "payments": float(month1_detail.payment_amount),
                        "balance": float(month1_detail.balance_amount),
                    }

                    month2_data = {
                        "name": str(month2_detail.month_name),
                        "year": int(month2_detail.year),
                        "type": str(month2_detail.month_type),
                        "charge": float(month2_detail.charge_amount),
                        "payments": float(month2_detail.payment_amount),
                        "balance": float(month2_detail.balance_amount),
                    }

                    month3_data = {
                        "name": str(month3_detail.month_name),
                        "year": int(month3_detail.year),
                        "type": str(month3_detail.month_type),
                        "charge": float(month3_detail.charge_amount),
                        "payments": float(month3_detail.payment_amount),
                        "balance": float(month3_detail.balance_amount),
                    }

                    memo_item = {
                        "id": memo.id,
                        "memo_code": memo.memo_code or f"MEMO-{memo.id}",
                        "child_admission": memo.child.admission_number
                        if memo.child
                        else "N/A",
                        "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}"
                        if memo.child
                        else "N/A",
                        "month": memo.month or 0,
                        "year": memo.year or 0,
                        "month_name": f"{month2_detail.month_name} {month2_detail.year}",
                        "month_charge": float(memo.grand_total or 0),
                        "payments_received": float(memo.total_payments_received or 0),
                        "month_balance": float(memo.grand_total or 0)
                        - float(memo.total_payments_received or 0),
                        "total_outstanding": float(memo.total_outstanding or 0),
                        "grand_total": float(memo.grand_total or 0),
                        "status": memo.status or "GENERATED",
                        "created_at": memo.date_created.strftime("%Y-%m-%d")
                        if memo.date_created
                        else "",
                        "is_three_month_format": True,
                    }

                    # Add month_breakdown separately to avoid dict issues
                    memo_item["month_breakdown"] = {
                        "month1": month1_data,
                        "month2": month2_data,
                        "month3": month3_data,
                    }
                else:
                    # OLD FORMAT: Single month data (backward compatibility)
                    memo_item = {
                        "id": memo.id,
                        "memo_code": memo.memo_code or f"MEMO-{memo.id}",
                        "child_admission": memo.child.admission_number
                        if memo.child
                        else "N/A",
                        "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}"
                        if memo.child
                        else "N/A",
                        "month": memo.month or 0,
                        "year": memo.year or 0,
                        "month_name": str(month_name),
                        "month_charge": float(memo.month_total_charge or 0),
                        "payments_received": float(memo.total_payments_received or 0),
                        "month_balance": float(memo.month_net_balance or 0),
                        "total_outstanding": 0.00,
                        "grand_total": float(memo.month_total_charge or 0),
                        "status": memo.status or "GENERATED",
                        "created_at": memo.date_created.strftime("%Y-%m-%d")
                        if memo.date_created
                        else "",
                        "is_three_month_format": False,
                    }

                memo_data.append(memo_item)

            except Exception as e:
                print(f"DEBUG: Error processing memo {memo.id}: {e}")
                continue

        print(f"DEBUG: Returning {len(memo_data)} memo records")

        return JsonResponse(memo_data, safe=False)

    except Exception as e:
        print(f"ERROR in getInvoiceMemosJS: {e}")
        import traceback

        traceback.print_exc()

        return JsonResponse({"error": str(e), "data": []}, status=500)


def calculate_three_month_invoice_data(child, target_month, target_year):
    """
    Calculate 3-month invoice data:
    - Month 1 (2 months before target): Outstanding/Credits only
    - Month 2 (1 month before target): Full calculation with attendance
    - Month 3 (target month): Full package amount without attendance logic

    Example: If generating for May, show April dues/credits + May calculated + June full amount
    """
    try:
        import calendar
        from decimal import Decimal

        target_month_int = int(target_month)
        target_year_int = int(target_year)

        # Calculate the three months
        # Month 1: 2 months before target (April if target is May)
        if target_month_int > 2:
            month1 = target_month_int - 2
            year1 = target_year_int
        elif target_month_int == 2:
            month1 = 12
            year1 = target_year_int - 1
        else:  # target_month_int == 1
            month1 = 11
            year1 = target_year_int - 1

        # Month 2: 1 month before target (May if target is June)
        if target_month_int > 1:
            month2 = target_month_int - 1
            year2 = target_year_int
        else:
            month2 = 12
            year2 = target_year_int - 1

        # Month 3: Target month (June if target is June)
        month3 = target_month_int
        year3 = target_year_int

        # Get month names
        month1_name = calendar.month_name[month1]
        month2_name = calendar.month_name[month2]
        month3_name = calendar.month_name[month3]

        # Get child details
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not package_mapping or not enrollment:
            raise Exception("No package mapping or enrollment found")

        # Get package details
        is_flex = package_mapping.flex_package is not None
        package = (
            package_mapping.flex_package if is_flex else package_mapping.normal_package
        )

        if not package:
            raise Exception("No valid package assigned")

        # Month 1: Check for existing memo or calculate outstanding/credits
        month1_data = get_month_outstanding_credits(child, month1, year1)

        # Month 2: Full calculation with attendance rules
        month2_data = calculate_month_with_attendance(
            child, package_mapping, enrollment, month2, year2
        )

        # Month 3: Full package amount without attendance logic
        month3_data = calculate_month_full_package(
            child, package_mapping, enrollment, month3, year3
        )

        # Calculate summary
        total_outstanding = month1_data["balance"]
        current_month_charge = month2_data["total_charge"]
        next_month_charge = month3_data["total_charge"]
        grand_total = total_outstanding + current_month_charge + next_month_charge

        return {
            "child_name": f"{child.child_first_name} {child.child_last_name}",
            "child_admission": child.admission_number,
            "month1": {
                "name": month1_name,
                "year": year1,
                "charge": month1_data["charge"],
                "payments": month1_data["payments"],
                "balance": month1_data["balance"],
                "credit": month1_data["credit"],
                "status": month1_data["status"],
            },
            "month2": {
                "name": month2_name,
                "year": year2,
                "package_name": month2_data["package_name"],
                "charge": month2_data["total_charge"],
                "package_fee": month2_data["package_fee"],
                "extra_charges": month2_data["extra_charges"],
                "holiday_charges": month2_data["holiday_charges"],
                "discount": month2_data["discount"],
                "days_attended": month2_data["days_attended"],
                "expected_days": month2_data["expected_days"],
                "attendance_percentage": month2_data["attendance_percentage"],
                "is_half_charge": month2_data["is_half_charge"],
                "payments": Decimal("0.00"),  # No payments yet for this month
                "balance": month2_data["total_charge"],
            },
            "month3": {
                "name": month3_name,
                "year": year3,
                "package_name": month3_data["package_name"],
                "charge": month3_data["total_charge"],
                "package_fee": month3_data["package_fee"],
                "extra_charges": month3_data["extra_charges"],
                "holiday_charges": month3_data["holiday_charges"],
                "discount": month3_data["discount"],
                "expected_days": month3_data["expected_days"],
                "payments": Decimal("0.00"),  # No payments yet for this month
                "balance": month3_data["total_charge"],
            },
            "summary": {
                "total_outstanding": total_outstanding,
                "current_month_charge": current_month_charge,
                "next_month_charge": next_month_charge,
                "grand_total": grand_total,
            },
        }

    except Exception as e:
        raise Exception(f"Error calculating 3-month invoice: {str(e)}")


def get_month_outstanding_credits(child, month, year):
    """Get outstanding balance or credits for a specific month"""
    try:
        from decimal import Decimal

        # Check if there's an existing memo for this month
        existing_memo = InvoiceMemo.objects.filter(
            child=child, month=month, year=year, is_active=True
        ).first()

        if existing_memo:
            return {
                "charge": existing_memo.month_total_charge,
                "payments": existing_memo.total_payments_received,
                "balance": existing_memo.month_net_balance,
                "credit": max(
                    Decimal("0.00"), -existing_memo.month_net_balance
                ),  # Credits are negative balances
                "status": existing_memo.status,
            }
        else:
            # No record exists for this month
            return {
                "charge": Decimal("0.00"),
                "payments": Decimal("0.00"),
                "balance": Decimal("0.00"),
                "credit": Decimal("0.00"),
                "status": "No Record",
            }

    except Exception:
        return {
            "charge": Decimal("0.00"),
            "payments": Decimal("0.00"),
            "balance": Decimal("0.00"),
            "credit": Decimal("0.00"),
            "status": "Error",
        }


def calculate_month_with_attendance(child, package_mapping, enrollment, month, year):
    """Calculate month charges with full attendance logic"""
    try:
        import calendar
        from collections import defaultdict
        from datetime import datetime, time
        from decimal import Decimal

        from django.db.models import Q

        # Get the date range for the month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # Get package details
        is_flex = package_mapping.flex_package is not None
        package = (
            package_mapping.flex_package if is_flex else package_mapping.normal_package
        )

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # Get attendance logs for the month
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day)
        ).order_by("date_logged", "time_logged")

        # Get holidays in this month
        holidays = set(
            Holiday.objects.filter(
                start_date__lte=last_day, end_date__gte=first_day
            ).values_list("start_date", flat=True)
        )

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        present_days = 0
        holiday_attendance_days = 0
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")

        # Process each attendance day
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance (in and out)
                present_days += 1
                last_log = logs_sorted[-1]

                is_holiday_day = log_date in holidays

                # Calculate extra hours charges
                log_time_out = last_log.time_logged or time(0, 0)
                extra_slots = ExtraHoursAfter530.objects.filter(
                    package_type=package.package_type,
                    from_time__lte=log_time_out,
                    to_time__gte=log_time_out,
                    effective_from__lte=log_date,
                ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

                for slot in extra_slots:
                    extra_hours_charge += slot.extra_rate

                # Holiday attendance charge
                if is_holiday_day and package_mapping.holiday_package:
                    holiday_attendance_days += 1
                    daily_holiday_rate = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days)
                    )
                    holiday_charge += daily_holiday_rate

        # Calculate attendance percentage
        attendance_percentage = (
            (present_days / expected_days * 100) if expected_days > 0 else 0
        )

        # Apply attendance-based charging rules
        is_half_charge = False

        if attendance_percentage == 0:
            package_fee = Decimal("0.00")  # No attendance = no charge
        elif attendance_percentage < 50:
            package_fee = package_total / 2  # Less than 50% = half charge
            is_half_charge = True
        else:
            package_fee = package_total  # 50% or more = full charge

        # Calculate subtotal
        subtotal = package_fee + extra_hours_charge + holiday_charge

        # Apply discount
        discount_amount = Decimal("0.00")
        if enrollment.discount and enrollment.discount.status == "Approved":
            discount_amount = subtotal * (enrollment.discount.discount_rate / 100)

        total_charge = subtotal - discount_amount

        return {
            "package_name": package.package_name,
            "package_base_fee": package_total,
            "days_attended": present_days,
            "expected_days": expected_days,
            "attendance_percentage": round(attendance_percentage, 2),
            "is_half_charge": is_half_charge,
            "package_fee": package_fee,
            "extra_charges": extra_hours_charge,
            "holiday_attendance_days": holiday_attendance_days,
            "holiday_charges": holiday_charge,
            "discount": discount_amount,
            "total_charge": total_charge,
        }

    except Exception as e:
        raise Exception(f"Error calculating month with attendance: {str(e)}")


def calculate_month_full_package(child, package_mapping, enrollment, month, year):
    """Calculate month charges with full package amount (no attendance logic)"""
    try:
        from decimal import Decimal

        # Get package details
        is_flex = package_mapping.flex_package is not None
        package = (
            package_mapping.flex_package if is_flex else package_mapping.normal_package
        )

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # For future months, charge full package amount
        package_fee = package_total

        # No extra hours or holiday charges for future months
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")

        # Calculate subtotal
        subtotal = package_fee + extra_hours_charge + holiday_charge

        # Apply discount
        discount_amount = Decimal("0.00")
        if enrollment.discount and enrollment.discount.status == "Approved":
            discount_amount = subtotal * (enrollment.discount.discount_rate / 100)

        total_charge = subtotal - discount_amount

        return {
            "package_name": package.package_name,
            "package_base_fee": package_total,
            "expected_days": expected_days,
            "package_fee": package_fee,
            "extra_charges": extra_hours_charge,
            "holiday_attendance_days": 0,
            "holiday_charges": holiday_charge,
            "discount": discount_amount,
            "total_charge": total_charge,
        }

    except Exception as e:
        raise Exception(f"Error calculating full package month: {str(e)}")


@login_required
def previewThreeMonthInvoiceUpdated(request):
    """Updated 3-month invoice preview with proper month calculations"""
    try:
        child_id = request.GET.get("child")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)

        # Check if memo already exists for this month
        existing_memo = InvoiceMemo.objects.filter(
            child_id=child_id, year=int(year), month=int(month)
        ).first()

        if existing_memo:
            return JsonResponse(
                {
                    "error": f"Invoice memo already exists for {calendar.month_name[int(month)]} {year}",
                    "existing_memo_code": existing_memo.memo_code,
                },
                status=400,
            )

        # Calculate 3-month data
        three_month_data = calculate_three_month_invoice_data(child, month, year)

        return JsonResponse({"success": True, **three_month_data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Helper function to safely get values from dictionaries/objects
def safe_get(obj, path, default_value=0):
    keys = path.split(".")
    result = obj
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            result = getattr(result, key, None)
        if result is None:
            # Attempt to convert default_value to Decimal if it's a numeric context
            if isinstance(default_value, (int, float)):
                return Decimal(default_value)
            return default_value

    # If the result itself is a number, ensure it's Decimal for consistency
    if isinstance(result, (int, float)):
        return Decimal(result)

    # If it's a string, try converting to Decimal if it looks like a number
    if isinstance(result, str):
        try:
            # Handle potential comma as decimal separator in string, or just clean it
            # This is a defensive check, as DecimalField should already be Decimal
            clean_result = result.replace(
                ",", ""
            )  # Remove thousands comma if present in string
            if "." in clean_result:  # Check for decimal point
                return Decimal(clean_result)
            elif clean_result.isdigit():  # Check if it's an integer string
                return Decimal(clean_result)
        except Exception:
            pass  # Fallback to original string if conversion fails

    return result if result is not None else default_value


# Helper for decimal formatting
def format_currency(value):
    if value is None:
        value = Decimal(0)
    # Ensure value is Decimal before formatting
    try:
        value = Decimal(value)
    except Exception:
        value = Decimal(0)  # Fallback if conversion fails
    return f"{value:,.2f}"


# Function to draw wrapped text
def draw_wrapped_text(
    canvas_obj,
    text,
    x,
    y,
    max_width,
    font_name,
    font_size,
    line_height,
    alignment="left",
):
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.fontName = font_name
    style.fontSize = font_size
    style.leading = line_height

    if alignment == "center":
        style.alignment = TA_CENTER
    elif alignment == "right":
        style.alignment = TA_RIGHT
    else:
        style.alignment = TA_LEFT

    # Create a Paragraph object
    p = Paragraph(text, style)

    # Wrap the text to the max_width. The height is adjusted by wrapOn.
    width, height = p.wrapOn(
        canvas_obj, max_width, 1000
    )  # 1000 is a dummy height, it will calculate actual needed height

    # Draw the paragraph at the calculated position.
    # We subtract height from y to draw downwards from the top of the paragraph area.
    p.drawOn(canvas_obj, x, y - height)

    # Return the actual height used by the paragraph for precise y_position adjustments
    return height


@login_required
def generate_invoice_pdf(request, memo_id):
    try:
        invoice_memo = get_object_or_404(InvoiceMemo, id=memo_id)
        # Get details and order them for consistent processing
        details = invoice_memo.details.order_by("month_sequence")

        # Initialize overall financial sums from InvoiceMemoDetail
        overall_grand_total = Decimal(0)
        overall_payments_received = Decimal(0)

        # invoice_data dictionary will be populated with aggregated data
        invoice_data = {
            "memo_code": invoice_memo.memo_code,
            "memo_date": invoice_memo.date_created.strftime("%d %B %Y"),
            "child_name": f"{invoice_memo.child.child_first_name} {invoice_memo.child.child_last_name}",
            "child_admission": invoice_memo.child.admission_number,
            "month_details": [],  # To store processed details
            "summary": {
                "total_outstanding": Decimal(0),
                "current_month_charge": Decimal(0),
                "next_month_charge": Decimal(0),
                "grand_total": Decimal(0),  # Will be calculated
            },
            "payment_status": "PENDING",  # Default status
        }

        # Populate month_details and summary, and accumulate overall totals
        for detail in details:
            calc_details = detail.calculation_details or {}

            # Accumulate overall totals from InvoiceMemoDetail
            overall_grand_total += detail.charge_amount
            overall_payments_received += detail.payment_amount

            month_data = {
                "month_sequence": detail.month_sequence,
                "name": detail.month_name,
                "year": detail.year,
                "type": detail.month_type,
                "charge": detail.charge_amount,
                "payment_amount": detail.payment_amount,
                "balance_amount": detail.balance_amount,  # This is balance for *this specific month's transaction*
                **calc_details,
            }
            invoice_data["month_details"].append(month_data)

            if detail.month_sequence == 1:  # Outstanding/Credits
                invoice_data["month1"] = {
                    "name": detail.month_name,
                    "year": detail.year,
                    "type": detail.month_type,
                    "charge": safe_get(calc_details, "charge", Decimal(0)),
                    "payments": safe_get(calc_details, "payments", Decimal(0)),
                    "balance": detail.balance_amount,
                    "credit": safe_get(calc_details, "credit", Decimal(0)),
                    "status": safe_get(calc_details, "status", "No Record"),
                }
                invoice_data["summary"]["total_outstanding"] = detail.balance_amount

            elif detail.month_sequence == 2:  # Current calculated month
                invoice_data["month2"] = {
                    "name": detail.month_name,
                    "year": detail.year,
                    "type": detail.month_type,
                    "package_name": safe_get(calc_details, "package_name", "N/A"),
                    "charge": detail.charge_amount,
                    "package_fee": safe_get(calc_details, "package_fee", Decimal(0)),
                    "extra_charges": safe_get(
                        calc_details, "extra_charges", Decimal(0)
                    ),
                    "holiday_charges": safe_get(
                        calc_details, "holiday_charges", Decimal(0)
                    ),
                    "discount": safe_get(calc_details, "discount", Decimal(0)),
                    "days_attended": safe_get(calc_details, "days_attended", 0),
                    "expected_days": safe_get(calc_details, "expected_days", 0),
                    "attendance_percentage": safe_get(
                        calc_details, "attendance_percentage", 0
                    ),
                    "is_half_charge": safe_get(calc_details, "is_half_charge", False),
                    "payments": safe_get(calc_details, "payments", Decimal(0)),
                    "balance": detail.balance_amount,
                }
                invoice_data["summary"]["current_month_charge"] = detail.charge_amount

            elif detail.month_sequence == 3:  # Advance
                invoice_data["month3"] = {
                    "name": detail.month_name,
                    "year": detail.year,
                    "type": detail.month_type,
                    "package_name": safe_get(calc_details, "package_name", "N/A"),
                    "charge": detail.charge_amount,
                    "package_fee": safe_get(calc_details, "package_fee", Decimal(0)),
                    "extra_charges": safe_get(
                        calc_details, "extra_charges", Decimal(0)
                    ),
                    "holiday_charges": safe_get(
                        calc_details, "holiday_charges", Decimal(0)
                    ),
                    "discount": safe_get(calc_details, "discount", Decimal(0)),
                    "payments": safe_get(calc_details, "payments", Decimal(0)),
                    "balance": detail.balance_amount,
                }
                invoice_data["summary"]["next_month_charge"] = detail.charge_amount

        # Final calculation of overall invoice amounts
        invoice_data["grand_total"] = overall_grand_total
        invoice_data["payments_received"] = overall_payments_received
        invoice_data["balance_amount"] = (
            overall_grand_total - overall_payments_received
        )  # Overall balance for the memo

        # Determine overall payment status based on derived totals
        if invoice_data["balance_amount"] <= 0:
            if invoice_data["payments_received"] >= invoice_data["grand_total"]:
                invoice_data["payment_status"] = "FULLY_PAID"
            else:  # balance is negative or zero with credit
                invoice_data["payment_status"] = "HAS_CREDIT"
        elif invoice_data["payments_received"] > 0:
            invoice_data["payment_status"] = "PARTIAL_PAID"
        else:
            invoice_data["payment_status"] = "PENDING"

        # Create the HttpResponse object with the appropriate PDF headers.
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice_memo_{invoice_data["memo_code"]}.pdf"'
        )

        # Create the PDF object, using the response object as its file.
        p = canvas.Canvas(response, pagesize=A4)
        width, height = A4  # A4 is 595.27 x 841.89 points (approx 210 x 297 mm)

        # Set up fonts and colors - all black by default
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.black)

        # Define margins
        left_margin = 0.8 * inch
        right_margin = width - 0.8 * inch
        top_margin = height - 0.8 * inch
        bottom_margin = 0.8 * inch

        # --- Header ---
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(width / 2.0, top_margin - 0.5 * inch, "POLYMATH COLLEGE")
        p.setFont("Helvetica", 9)
        p.drawCentredString(
            width / 2.0,
            top_margin - 0.7 * inch,
            "No 452/3 High Level Road, Nawinna, Maharagama",
        )
        p.drawCentredString(
            width / 2.0, top_margin - 0.85 * inch, "PV 63200 | Phone 0112802554"
        )
        p.setFont("Helvetica-Bold", 14)
        p.drawCentredString(
            width / 2.0, top_margin - 1.2 * inch, "KIDS DIVISION - MEMO"
        )

        # Invoice Info Bar (no color background, just lines and text)
        p.setFont("Helvetica-Bold", 10)
        p.line(
            left_margin, top_margin - 1.5 * inch, right_margin, top_margin - 1.5 * inch
        )  # Top line
        p.drawString(
            left_margin + 0.1 * inch,
            top_margin - 1.4 * inch,
            f"Memo Code: {invoice_data['memo_code']}",
        )
        p.drawRightString(
            right_margin - 0.1 * inch,
            top_margin - 1.4 * inch,
            f"Generated: {invoice_data['memo_date']}",
        )
        p.line(
            left_margin, top_margin - 1.7 * inch, right_margin, top_margin - 1.7 * inch
        )  # Bottom line
        p.setFillColor(
            colors.black
        )  # Ensure color is black after any potential previous color changes

        y_position = top_margin - 2.0 * inch

        # --- Child Information ---
        p.setFont("Helvetica", 10)
        p.drawString(left_margin, y_position, f"Name: {invoice_data['child_name']}")
        p.drawString(
            width / 2.0, y_position, f"Child ID: {invoice_data['child_admission']}"
        )
        y_position -= 0.25 * inch
        p.drawString(
            left_margin,
            y_position,
            f"Package: {safe_get(invoice_data, 'month2.package_name', 'N/A')}",
        )
        y_position -= 0.4 * inch  # Space after child info

        # --- Invoice Table Header ---
        p.setFont("Helvetica-Bold", 10)
        p.line(left_margin, y_position, right_margin, y_position)
        p.drawString(left_margin + 0.1 * inch, y_position - 0.2 * inch, "Description")
        p.drawRightString(
            right_margin - 0.1 * inch, y_position - 0.2 * inch, "Amount (Rs.)"
        )
        y_position -= 0.3 * inch
        p.line(left_margin, y_position, right_margin, y_position)

        # --- Table Content ---
        p.setFont("Helvetica", 9)
        line_height = 0.2 * inch  # Approximately 14.4 points for 9pt font

        # Month 1 (Outstanding/Credits)
        month1 = invoice_data.get("month1", {})
        if month1:
            # Removed background color for section header
            p.setFont("Helvetica-Bold", 9)
            p.drawString(
                left_margin + 0.1 * inch,
                y_position - line_height,
                f"{month1['name']} {month1['year']} Details:",
            )
            y_position -= line_height * 1.2
            p.setFont("Helvetica", 9)

            if month1.get("status") != "No Record":
                if safe_get(month1, "charge") > 0:
                    p.drawString(
                        left_margin + 0.3 * inch,
                        y_position - line_height,
                        "Month Charges",
                    )
                    p.drawRightString(
                        right_margin - 0.1 * inch,
                        y_position - line_height,
                        format_currency(month1.get("charge")),
                    )
                    y_position -= line_height

                if safe_get(month1, "payments") > 0:
                    p.drawString(
                        left_margin + 0.3 * inch,
                        y_position - line_height,
                        "Payments Received",
                    )
                    p.drawRightString(
                        right_margin - 0.1 * inch,
                        y_position - line_height,
                        f"({format_currency(month1.get('payments'))})",
                    )
                    y_position -= line_height

                if safe_get(month1, "balance") > 0:
                    p.setFont("Helvetica-Bold", 9)
                    # No red color for outstanding
                    p.drawString(
                        left_margin + 0.3 * inch,
                        y_position - line_height,
                        f"Outstanding as at {month1['name']} {month1['year']}",
                    )
                    p.drawRightString(
                        right_margin - 0.1 * inch,
                        y_position - line_height,
                        format_currency(month1.get("balance")),
                    )
                    p.setFont("Helvetica", 9)  # Reset font after bold
                    y_position -= line_height
                elif safe_get(month1, "credit") > 0:
                    p.setFont("Helvetica-Bold", 9)
                    # No darkgreen color for credits
                    p.drawString(
                        left_margin + 0.3 * inch,
                        y_position - line_height,
                        f"Credit Available from {month1['name']} {month1['year']}",
                    )
                    p.drawRightString(
                        right_margin - 0.1 * inch,
                        y_position - line_height,
                        f"({format_currency(month1.get('credit'))})",
                    )
                    p.setFont("Helvetica", 9)  # Reset font after bold
                    y_position -= line_height
                elif (
                    safe_get(month1, "balance") == 0
                    and safe_get(month1, "status") != "No Record"
                ):
                    p.drawString(
                        left_margin + 0.3 * inch,
                        y_position - line_height,
                        f"Balance as at {month1['name']} {month1['year']}",
                    )
                    p.drawRightString(
                        right_margin - 0.1 * inch, y_position - line_height, "0.00"
                    )
                    y_position -= line_height
            else:
                p.drawString(
                    left_margin + 0.3 * inch,
                    y_position - line_height,
                    f"No record for {month1['name']}",
                )
                p.drawRightString(
                    right_margin - 0.1 * inch, y_position - line_height, "0.00"
                )
                y_position -= line_height

        # Check for page overflow
        if y_position < bottom_margin + 3.5 * inch:  # Leave space for total and notes
            p.showPage()
            p.setFont("Helvetica", 10)
            y_position = top_margin - inch  # Reset y_position for new page
            p.drawString(left_margin, y_position, "Continued...")
            y_position -= 0.5 * inch

        # Month 2 (Calculated)
        month2 = invoice_data.get("month2", {})
        if month2 and safe_get(month2, "charge") > 0:
            desc_text = f"Day Care Monthly fee - {month2['name']} {month2['year']} ({month2.get('days_attended', 0)}/{month2.get('expected_days', 22)} days attended)"
            if month2.get("is_half_charge"):
                desc_text += "\n(Half charge applied (attendance < 50%))"

            p.setFont("Helvetica-Bold", 9)
            # Removed background color
            p.drawString(
                left_margin + 0.1 * inch,
                y_position - line_height,
                f"{month2['name']} {month2['year']} - Calculated Charge",
            )
            y_position -= line_height * 1.5
            p.setFont("Helvetica", 9)

            # Draw wrapped text for description
            text_height = draw_wrapped_text(
                p,
                desc_text,
                left_margin + 0.3 * inch,
                y_position - 0.1 * inch,
                width / 2.0,
                "Helvetica",
                9,
                10,
            )
            p.drawRightString(
                right_margin - 0.1 * inch,
                y_position - line_height,
                format_currency(month2.get("charge")),
            )  # This draws the amount
            y_position -= (
                text_height + 0.05 * inch
            )  # Adjust y_position based on actual text height

            # Show breakdown if there are extra charges/discounts
            if (
                safe_get(month2, "extra_charges") > 0
                or safe_get(month2, "holiday_charges") > 0
                or safe_get(month2, "discount") > 0
            ):
                breakdown_text = (
                    f"Package Fee: Rs. {format_currency(month2.get('package_fee'))}"
                )
                if safe_get(month2, "extra_charges") > 0:
                    breakdown_text += f"\nExtra Hours: Rs. {format_currency(month2.get('extra_charges'))}"
                if safe_get(month2, "holiday_charges") > 0:
                    breakdown_text += f"\nHoliday Charges: Rs. {format_currency(month2.get('holiday_charges'))}"
                if safe_get(month2, "discount") > 0:
                    breakdown_text += f"\nDiscount Applied: Rs. ({format_currency(month2.get('discount'))})"

                breakdown_height = draw_wrapped_text(
                    p,
                    f"Breakdown for {month2['name']}:\n" + breakdown_text,
                    left_margin + 0.5 * inch,
                    y_position - 0.1 * inch,
                    width / 2.5,
                    "Helvetica",
                    8,
                    9,
                )
                y_position -= breakdown_height + 0.05 * inch

            if safe_get(month2, "payments") > 0:
                p.drawString(
                    left_margin + 0.3 * inch,
                    y_position - line_height,
                    "Payments Received",
                )
                p.drawRightString(
                    right_margin - 0.1 * inch,
                    y_position - line_height,
                    f"({format_currency(month2.get('payments'))})",
                )
                y_position -= line_height

            p.setFont("Helvetica-Bold", 9)
            p.drawString(
                left_margin + 0.3 * inch,
                y_position - line_height,
                f"Balance for {month2['name']} {month2['year']}",
            )
            p.drawRightString(
                right_margin - 0.1 * inch,
                y_position - line_height,
                format_currency(month2.get("balance")),
            )
            p.setFont("Helvetica", 9)
            y_position -= line_height

        # Check for page overflow
        if y_position < bottom_margin + 3.5 * inch:
            p.showPage()
            p.setFont("Helvetica", 10)
            y_position = top_margin - inch
            p.drawString(left_margin, y_position, "Continued...")
            y_position -= 0.5 * inch

        # Month 3 (Advance)
        month3 = invoice_data.get("month3", {})
        if month3 and safe_get(month3, "charge") > 0:
            p.setFont("Helvetica-Bold", 9)
            # Removed background color
            p.drawString(
                left_margin + 0.1 * inch,
                y_position - line_height,
                f"{month3['name']} {month3['year']} - Advance Payment",
            )
            y_position -= line_height * 1.2
            p.setFont("Helvetica", 9)

            # This is the line for Package Fee - June
            p.drawString(
                left_margin + 0.3 * inch,
                y_position - line_height,
                f"Package Fee - {month3['name']} {month3['year']}",
            )
            p.drawRightString(
                right_margin - 0.1 * inch,
                y_position - line_height,
                format_currency(month3.get("charge")),
            )
            y_position -= line_height  # Move down after this line

            # Show breakdown if there are extra charges/discounts
            if (
                safe_get(month3, "extra_charges") > 0
                or safe_get(month3, "holiday_charges") > 0
                or safe_get(month3, "discount") > 0
            ):
                breakdown_text = (
                    f"Package Fee: Rs. {format_currency(month3.get('package_fee'))}"
                )
                if safe_get(month3, "extra_charges") > 0:
                    breakdown_text += f"\nExtra Hours: Rs. {format_currency(month3.get('extra_charges'))}"
                if safe_get(month3, "holiday_charges") > 0:
                    breakdown_text += f"\nHoliday Charges: Rs. {format_currency(month3.get('holiday_charges'))}"
                if safe_get(month3, "discount") > 0:
                    breakdown_text += f"\nDiscount Applied: Rs. ({format_currency(month3.get('discount'))})"

                breakdown_height = draw_wrapped_text(
                    p,
                    f"Breakdown for {month3['name']}:\n" + breakdown_text,
                    left_margin + 0.5 * inch,
                    y_position - 0.1 * inch,
                    width / 2.5,
                    "Helvetica",
                    8,
                    9,
                )
                y_position -= breakdown_height + 0.05 * inch

            if safe_get(month3, "payments") > 0:
                p.drawString(
                    left_margin + 0.3 * inch,
                    y_position - line_height,
                    "Payments Received",
                )
                p.drawRightString(
                    right_margin - 0.1 * inch,
                    y_position - line_height,
                    f"({format_currency(month3.get('payments'))})",
                )
                y_position -= line_height

            p.setFont("Helvetica-Bold", 9)
            # This is the line for Balance for June
            p.drawString(
                left_margin + 0.3 * inch,
                y_position - line_height,
                f"Balance for {month3['name']} {month3['year']}",
            )
            p.drawRightString(
                right_margin - 0.1 * inch,
                y_position - line_height,
                format_currency(month3.get("balance")),
            )
            p.setFont("Helvetica", 9)
            y_position -= line_height

        # --- Total Summary ---
        y_position -= 0.2 * inch
        p.line(
            left_margin, y_position, right_margin, y_position
        )  # Top line for total box
        y_position -= 0.1 * inch
        p.setFont("Helvetica-Bold", 11)
        p.drawString(
            left_margin + 0.1 * inch, y_position - line_height, "Total Amount Due:"
        )
        p.drawRightString(
            right_margin - 0.1 * inch,
            y_position - line_height,
            f"Rs. {format_currency(invoice_data['grand_total'])}",
        )
        y_position -= line_height
        p.setFont("Helvetica", 10)
        p.drawString(
            left_margin + 0.1 * inch,
            y_position - line_height,
            "Less Payments Received:",
        )
        p.drawRightString(
            right_margin - 0.1 * inch,
            y_position - line_height,
            f"Rs. ({format_currency(invoice_data['payments_received'])})",
        )
        y_position -= line_height
        p.setFont("Helvetica-Bold", 12)
        p.drawString(
            left_margin + 0.1 * inch, y_position - line_height, "Balance to Pay:"
        )
        # No red color for balance to pay
        p.drawRightString(
            right_margin - 0.1 * inch,
            y_position - line_height,
            f"Rs. {format_currency(invoice_data['balance_amount'])}",
        )
        p.setFont("Helvetica", 10)  # Reset font after bold
        y_position -= line_height + 0.1 * inch
        p.line(
            left_margin, y_position, right_margin, y_position
        )  # Bottom line for total box

        # Payment Status
        y_position -= 0.2 * inch
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin, y_position, "Payment Status:")  # Draw the label

        # Calculate x-position for the actual status string
        status_label_width = p.stringWidth("Payment Status:", "Helvetica-Bold", 10)
        status_text_x = (
            left_margin + status_label_width + 0.1 * inch
        )  # Add a small buffer

        # No color for status text
        p.drawString(
            status_text_x,
            y_position,
            invoice_data["payment_status"].replace("_", " ").title(),
        )

        y_position -= 0.4 * inch  # More space after status

        # --- Summary Cards (Textual) ---
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin, y_position, "Summary:")
        y_position -= 0.2 * inch
        p.setFont("Helvetica", 9)
        p.drawString(
            left_margin + 0.2 * inch,
            y_position - line_height,
            f"Total Outstanding from Previous: Rs. {format_currency(invoice_data['summary']['total_outstanding'])}",
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.2 * inch,
            y_position - line_height,
            f"Current Month Charges: Rs. {format_currency(invoice_data['summary']['current_month_charge'])}",
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.2 * inch,
            y_position - line_height,
            f"Next Month Charges (Advance): Rs. {format_currency(invoice_data['summary']['next_month_charge'])}",
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.2 * inch,
            y_position - line_height,
            f"Overall Grand Total: Rs. {format_currency(invoice_data['grand_total'])}",
        )  # Use calculated grand_total
        y_position -= 0.4 * inch

        # --- Notes ---
        p.setFont("Helvetica", 9)
        notes = [
            "Please note that extra hours after 5:30 PM, public holiday charges, and extra charges are calculated separately.",
            "Any pending discounts or special considerations will be applied upon review and verification.",
            "This is an electronically generated memo and does not require a signature.",
        ]
        p.drawString(left_margin, y_position, "Notes:")
        y_position -= 0.2 * inch
        for note in notes:
            # Use draw_wrapped_text to handle multi-line notes gracefully
            note_height = draw_wrapped_text(
                p,
                f"• {note}",
                left_margin + 0.1 * inch,
                y_position - 0.1 * inch,
                width - 2 * left_margin - 0.2 * inch,
                "Helvetica",
                9,
                10,
            )
            y_position -= (
                note_height + 0.05 * inch
            )  # Adjust y_position by actual height used by wrapped text

        y_position -= 0.2 * inch
        p.drawString(left_margin, y_position, "Thank you for your prompt payment!")
        y_position -= 0.5 * inch

        # --- Bank Details ---
        p.setFont("Helvetica-Bold", 10)
        p.drawString(left_margin, y_position, "Bank Details:")
        y_position -= 0.2 * inch
        p.setFont("Helvetica", 9)
        p.drawString(
            left_margin + 0.1 * inch, y_position - line_height, "Bank Name: XYZ Bank"
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.1 * inch,
            y_position - line_height,
            "Account Name: Polymath College (Pvt) Ltd",
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.1 * inch,
            y_position - line_height,
            "Account Number: 1234567890",
        )
        y_position -= line_height
        p.drawString(
            left_margin + 0.1 * inch, y_position - line_height, "Branch: Maharagama"
        )
        y_position -= line_height

        # Finalize the PDF
        p.showPage()
        p.save()
        return response

    except InvoiceMemo.DoesNotExist:
        return HttpResponse("Invoice memo not found.", status=404)
    except Exception as e:
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)
