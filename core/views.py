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
from io import BytesIO

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
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable

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
    CreatePackageTypeForm,
    CreatePolymathHolidayForm,
    CreatePublicHolidayForm,
    ExtraHoursReportForm,
    GenerateInvoiceForm,
    # CreateHolidayTypesForm,
    LoadInvoiceMemoForm,
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
    InvoiceMemo,
    InvoiceMemoDetail,
    # HolidayType,
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
        mothers_whatsapp_number = request.POST.get("mothers_whatsapp_number").strip()
        resident_contact_number = request.POST.get("resident_contact_number").strip()
        address_line1 = request.POST.get("address_line1")
        address_line2 = request.POST.get("address_line2")
        address_line3 = request.POST.get("address_line3")
        email_address = request.POST.get("email_address")
        is_polymath_student = request.POST.get("is_polymath_student")
        admission_date = request.POST.get("admission_date")
        is_active = request.POST.get("is_active")
        child_image = request.FILES.get("child_image")

        # Convert checkbox values to boolean
        if is_polymath_student == "on":
            is_polymath_student = True
        else:
            is_polymath_student = False

        if is_active == "on":
            is_active = True
        else:
            is_active = False

        # Check user permissions
        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(request, "You are not authorized to perform this operation.")
            return redirect("core:view_child")

        try:
            # Use get_or_create to handle both creation and updates
            objChild, created = Child.objects.get_or_create(
                admission_number=admission_number,
                defaults={
                    "child_first_name": child_first_name,
                    "child_last_name": child_last_name,
                    "date_of_birth": datetime.strptime(
                        date_of_birth, "%Y-%m-%d"
                    ).date(),
                    "fathers_name": fathers_name,
                    "fathers_contact_number": fathers_contact_number,
                    "fathers_whatsapp_number": fathers_whatsapp_number,
                    "mothers_name": mothers_name,
                    "mothers_contact_number": mothers_contact_number,
                    "mothers_whatsapp_number": mothers_whatsapp_number,
                    "resident_contact_number": resident_contact_number,
                    "address_line1": address_line1,
                    "address_line2": address_line2,
                    "address_line3": address_line3,
                    "email_address": email_address,
                    "is_polymath_student": is_polymath_student,
                    "user_created": request.user.username,
                    "qr_code": generateQR(
                        admission_number, child_first_name, child_last_name
                    ),
                    "child_image": child_image,
                    "admission_date": datetime.strptime(
                        admission_date, "%Y-%m-%d"
                    ).date(),
                    "is_active": is_active,
                },
            )

            if not created:
                # Record exists, update it
                objChild.child_first_name = child_first_name
                objChild.child_last_name = child_last_name
                objChild.fathers_contact_number = fathers_contact_number
                objChild.fathers_whatsapp_number = fathers_whatsapp_number
                objChild.mothers_contact_number = mothers_contact_number
                objChild.mothers_whatsapp_number = mothers_whatsapp_number
                objChild.resident_contact_number = resident_contact_number
                objChild.address_line1 = address_line1
                objChild.address_line2 = address_line2
                objChild.address_line3 = address_line3
                objChild.email_address = email_address
                objChild.is_polymath_student = is_polymath_student
                objChild.user_updated = request.user.username
                objChild.is_active = is_active

                # Generate QR code if it doesn't exist
                if objChild.qr_code is None:
                    objChild.qr_code = generateQR(
                        admission_number,
                        objChild.child_first_name,
                        objChild.child_last_name,
                    )

                # Update image if provided
                if child_image:
                    objChild.child_image = child_image

                objChild.save()
                messages.success(request, "Child details updated.")
            else:
                # New record was created
                messages.success(request, "Child details saved.")

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

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
        return pdf_path

    except Exception:
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
    """Calculate current month charges (fresh calculation) - FIXED VERSION"""
    try:
        import calendar
        from collections import defaultdict
        from datetime import datetime, time
        from decimal import Decimal

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
        extra_hours_charge = Decimal("0.00")  # WILL BE CALCULATED WITH CORRECTED LOGIC
        holiday_charge = Decimal("0.00")

        # Get package details for extra hours calculation
        package_end_time = None
        package_type = None

        if package_mapping.normal_package:
            package_end_time = package_mapping.normal_package.to_time
            package_type = package_mapping.normal_package.package_type
        elif package_mapping.holiday_package:
            package_end_time = package_mapping.holiday_package.to_time
            package_type = package_mapping.holiday_package.package_type
        elif package_mapping.flex_package:
            package_end_time = time(17, 30)  # Default for flex
            package_type = package_mapping.flex_package.package_type

        # Process each attendance day with CORRECTED LOGIC
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance (in and out)
                present_days += 1
                last_log = logs_sorted[-1]
                time_out = last_log.time_logged

                is_holiday_day = log_date in holidays

                # ===== CORRECTED CUMULATIVE EXTRA HOURS CALCULATION =====
                if time_out and package_end_time and time_out > package_end_time:
                    day_extra_charges = Decimal("0.00")
                    cutoff_530 = time(17, 30)

                    # 1. Handle charges BEFORE 5:30 PM
                    if package_end_time < cutoff_530 and time_out > package_end_time:
                        end_time_for_before_530 = min(time_out, cutoff_530)

                        if end_time_for_before_530 > package_end_time:
                            package_end_datetime = datetime.combine(
                                log_date, package_end_time
                            )
                            before_530_datetime = datetime.combine(
                                log_date, end_time_for_before_530
                            )
                            hours_before_530 = (
                                before_530_datetime - package_end_datetime
                            ).total_seconds() / 3600

                            hour_count = int(hours_before_530)
                            if hours_before_530 % 1 > 0:
                                hour_count += 1

                            for hour_num in range(1, min(hour_count + 1, 7)):
                                rate_obj = (
                                    ExtraHoursUpTo530.objects.filter(
                                        hour_number=hour_num,
                                        effective_from__lte=log_date,
                                        is_active=True,
                                    )
                                    .filter(
                                        Q(effective_to__gte=log_date)
                                        | Q(effective_to__isnull=True)
                                    )
                                    .first()
                                )

                                if rate_obj:
                                    day_extra_charges += rate_obj.extra_rate

                    # 2. Handle charges AFTER 5:30 PM (CUMULATIVE)
                    if time_out > cutoff_530:
                        start_time_after_530 = max(package_end_time, cutoff_530)

                        # Get ALL applicable slots (CUMULATIVE - KEY FIX)
                        applicable_slots = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__gte=start_time_after_530,
                                from_time__lt=time_out,
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .order_by("from_time")
                        )

                        # Add charges for ALL applicable slots
                        for slot in applicable_slots:
                            day_extra_charges += slot.extra_rate

                        # Handle partial slot
                        partial_slot = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__lt=time_out,
                                to_time__gt=time_out,
                                from_time__gte=start_time_after_530,
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .first()
                        )

                        if partial_slot and partial_slot not in [
                            slot for slot in applicable_slots
                        ]:
                            day_extra_charges += partial_slot.extra_rate

                    extra_hours_charge += day_extra_charges

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
            "extra_charges": extra_hours_charge,  # ✅ NOW USES CORRECTED CALCULATION
            "holiday_attendance_days": holiday_attendance_days,
            "holiday_charges": holiday_charge,
            "discount": discount_amount,
            "total_charge": total_charge,
        }

    except Exception as e:
        raise Exception(f"Error calculating current month charges: {str(e)}")


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
    """Calculate month charges with full attendance logic - COMPLETE FIXED VERSION"""
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

        if not package:
            raise Exception("No valid package assigned.")

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

        # Get package details for extra hours calculation
        package_end_time = None
        package_type = None

        if package_mapping.normal_package:
            package_end_time = package_mapping.normal_package.to_time
            package_type = package_mapping.normal_package.package_type
        elif package_mapping.holiday_package:
            package_end_time = package_mapping.holiday_package.to_time
            package_type = package_mapping.holiday_package.package_type
        elif package_mapping.flex_package:
            package_end_time = time(17, 30)  # Default for flex
            package_type = package_mapping.flex_package.package_type

        # Process each attendance day with CORRECTED CUMULATIVE LOGIC
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance (in and out)
                present_days += 1
                last_log = logs_sorted[-1]
                time_out = last_log.time_logged

                is_holiday_day = log_date in holidays

                # ===== CORRECTED CUMULATIVE EXTRA HOURS CALCULATION =====
                if time_out and package_end_time and time_out > package_end_time:
                    package_end_datetime = datetime.combine(log_date, package_end_time)
                    actual_out_datetime = datetime.combine(log_date, time_out)
                    extra_time_delta = actual_out_datetime - package_end_datetime
                    extra_hours = extra_time_delta.total_seconds() / 3600

                    day_extra_charges = Decimal("0.00")
                    cutoff_530 = time(17, 30)

                    # 1. Handle charges BEFORE 5:30 PM (if package ends before 5:30)
                    if package_end_time < cutoff_530 and time_out > package_end_time:
                        # Calculate time between package end and 5:30 PM (or actual out time if earlier)
                        end_time_for_before_530 = min(time_out, cutoff_530)

                        if end_time_for_before_530 > package_end_time:
                            before_530_datetime = datetime.combine(
                                log_date, end_time_for_before_530
                            )
                            hours_before_530 = (
                                before_530_datetime - package_end_datetime
                            ).total_seconds() / 3600

                            # Calculate number of complete + partial hours
                            hour_count = int(hours_before_530)
                            if hours_before_530 % 1 > 0:  # Has partial hour
                                hour_count += 1

                            # Add charges for each hour before 5:30 PM
                            for hour_num in range(
                                1, min(hour_count + 1, 7)
                            ):  # Max 6 hours
                                rate_obj = (
                                    ExtraHoursUpTo530.objects.filter(
                                        hour_number=hour_num,
                                        effective_from__lte=log_date,
                                        is_active=True,
                                    )
                                    .filter(
                                        Q(effective_to__gte=log_date)
                                        | Q(effective_to__isnull=True)
                                    )
                                    .first()
                                )

                                if rate_obj:
                                    day_extra_charges += rate_obj.extra_rate

                    # 2. Handle charges AFTER 5:30 PM (cumulative slot-by-slot)
                    if time_out > cutoff_530:
                        # Determine start time for after-5:30 charging
                        start_time_after_530 = max(package_end_time, cutoff_530)

                        # Get ALL time slots from start_time to actual out_time
                        # This is the key fix - get ALL applicable slots, not just the final one
                        applicable_slots = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__gte=start_time_after_530,  # Slot starts after our start time
                                from_time__lt=time_out,  # Slot starts before child leaves
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .order_by("from_time")
                        )  # Order by time to ensure sequential processing

                        # Add charges for ALL applicable slots (CUMULATIVE)
                        for slot in applicable_slots:
                            day_extra_charges += slot.extra_rate

                        # Also check if child's out_time falls within any slot that starts before out_time
                        # but ends after out_time (partial slot charging)
                        partial_slot = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__lt=time_out,  # Slot starts before child leaves
                                to_time__gt=time_out,  # Slot ends after child leaves
                                from_time__gte=start_time_after_530,  # Slot is relevant to our time range
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .first()
                        )

                        # Only add partial slot if not already included in applicable_slots
                        if partial_slot and partial_slot not in [
                            slot for slot in applicable_slots
                        ]:
                            day_extra_charges += partial_slot.extra_rate

                    # Add to total extra hours charge
                    extra_hours_charge += day_extra_charges

                # Calculate holiday charges
                if is_holiday_day and package_mapping.holiday_package:
                    holiday_attendance_days += 1
                    expected_days_holiday = (
                        package_mapping.holiday_package.no_days_months or 22
                    )
                    daily_holiday_rate = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days_holiday)
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
            "extra_charges": extra_hours_charge,  # ✅ CORRECTED CUMULATIVE CALCULATION
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
    """Updated 3-month invoice preview with detailed breakdown and payment tracking"""
    try:
        child_id = request.GET.get("child")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)

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

        # Calculate enhanced 3-month data with detailed breakdown
        three_month_data = calculate_enhanced_three_month_data(child, month, year)

        return JsonResponse({"success": True, **three_month_data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def calculate_enhanced_three_month_data(child, target_month, target_year):
    """
    Enhanced 3-month calculation with detailed breakdown and payment tracking
    """
    import calendar

    target_month_int = int(target_month)
    target_year_int = int(target_year)

    # Calculate the three months
    if target_month_int > 2:
        month1 = target_month_int - 2
        year1 = target_year_int
    elif target_month_int == 2:
        month1 = 12
        year1 = target_year_int - 1
    else:  # target_month_int == 1
        month1 = 11
        year1 = target_year_int - 1

    if target_month_int > 1:
        month2 = target_month_int - 1
        year2 = target_year_int
    else:
        month2 = 12
        year2 = target_year_int - 1

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

    # Month 1: Enhanced outstanding with payment tracking
    month1_data = get_enhanced_outstanding_data(child, month1, year1)

    # Month 2: Enhanced calculation with detailed breakdown
    month2_data = calculate_enhanced_month_with_attendance(
        child, package_mapping, enrollment, month2, year2
    )

    # Month 3: Enhanced advance calculation
    month3_data = calculate_enhanced_advance_month(
        child, package_mapping, enrollment, month3, year3
    )

    # Calculate enhanced summary with payment adjustments
    total_outstanding = month1_data["balance_after_payments"]
    current_month_charge = month2_data["total_charge"]
    next_month_charge = month3_data["total_charge"]

    # Adjust for payments
    current_month_balance = (
        month2_data["total_charge"] - month2_data["payments_received"]
    )
    next_month_balance = month3_data["total_charge"] - month3_data["payments_received"]

    grand_total = total_outstanding + current_month_balance + next_month_balance

    return {
        "child_name": f"{child.child_first_name} {child.child_last_name}",
        "child_admission": child.admission_number,
        "month1": {
            "name": month1_name,
            "year": year1,
            "type": "OUTSTANDING",
            "charge": month1_data["original_charge"],
            "payments": month1_data["payments_received"],
            "balance": month1_data["balance_after_payments"],
            "status": month1_data["status"],
            "payment_details": month1_data["payment_details"],
        },
        "month2": {
            "name": month2_name,
            "year": year2,
            "type": "CALCULATED",
            "package_name": month2_data["package_name"],
            "charge": month2_data["total_charge"],
            # DETAILED BREAKDOWN
            "package_fee": month2_data["package_fee"],
            "extra_charges": month2_data["extra_charges"],
            "holiday_charges": month2_data["holiday_charges"],
            "discount": month2_data["discount"],
            "days_attended": month2_data["days_attended"],
            "expected_days": month2_data["expected_days"],
            "attendance_percentage": month2_data["attendance_percentage"],
            "is_half_charge": month2_data["is_half_charge"],
            # PAYMENT TRACKING
            "payments": month2_data["payments_received"],
            "balance": month2_data["total_charge"] - month2_data["payments_received"],
            "payment_details": month2_data["payment_details"],
            # BREAKDOWN DETAILS
            "extra_charges_breakdown": month2_data.get("extra_charges_breakdown", []),
            "holiday_charges_breakdown": month2_data.get(
                "holiday_charges_breakdown", []
            ),
            "breakdown_summary": month2_data.get("breakdown_summary", {}),
        },
        "month3": {
            "name": month3_name,
            "year": year3,
            "type": "ADVANCE",
            "package_name": month3_data["package_name"],
            "charge": month3_data["total_charge"],
            "package_fee": month3_data["package_fee"],
            "payments": month3_data["payments_received"],
            "balance": month3_data["total_charge"] - month3_data["payments_received"],
            "payment_details": month3_data["payment_details"],
            "expected_days": month3_data["expected_days"],
        },
        "summary": {
            "total_outstanding": total_outstanding,
            "current_month_charge": current_month_charge,
            "next_month_charge": next_month_charge,
            "total_payments": month1_data["payments_received"]
            + month2_data["payments_received"]
            + month3_data["payments_received"],
            "grand_total": grand_total,
        },
    }


def get_enhanced_outstanding_data(child, month, year):
    """Get outstanding data with payment tracking"""
    import json
    from decimal import Decimal

    # Check for existing memo
    existing_memo = InvoiceMemo.objects.filter(
        child=child, month=month, year=year, is_active=True
    ).first()

    if existing_memo:
        # Get payment details from existing memo
        payment_details = []
        if existing_memo.payment_receipts:
            try:
                payment_details = json.loads(existing_memo.payment_receipts)
            except:
                payment_details = []

        return {
            "original_charge": existing_memo.month_total_charge,
            "payments_received": existing_memo.total_payments_received,
            "balance_after_payments": existing_memo.month_net_balance,
            "status": existing_memo.status,
            "payment_details": payment_details,
        }
    else:
        return {
            "original_charge": Decimal("0.00"),
            "payments_received": Decimal("0.00"),
            "balance_after_payments": Decimal("0.00"),
            "status": "No Record",
            "payment_details": [],
        }


def calculate_enhanced_month_with_attendance(
    child, package_mapping, enrollment, month, year
):
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
    extra_hours_charge = Decimal("0.00")  # Will be calculated with CORRECTED logic
    holiday_charge = Decimal("0.00")

    # Get package details for extra hours calculation
    package_end_time = None
    package_type = None

    if package_mapping.normal_package:
        package_end_time = package_mapping.normal_package.to_time
        package_type = package_mapping.normal_package.package_type
    elif package_mapping.holiday_package:
        package_end_time = package_mapping.holiday_package.to_time
        package_type = package_mapping.holiday_package.package_type
    elif package_mapping.flex_package:
        package_end_time = time(17, 30)  # Default for flex
        package_type = package_mapping.flex_package.package_type

    # DETAILED BREAKDOWN LISTS
    extra_charges_breakdown = []
    holiday_charges_breakdown = []

    # Process each attendance day with CORRECTED CUMULATIVE LOGIC
    for log_date, logs in logs_by_date.items():
        logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

        if len(logs_sorted) >= 2:  # Complete attendance (in and out)
            present_days += 1
            first_log = logs_sorted[0]
            last_log = logs_sorted[-1]

            time_in = first_log.time_logged
            time_out = last_log.time_logged
            is_holiday_day = log_date in holidays

            # ===== CORRECTED CUMULATIVE EXTRA HOURS CALCULATION =====
            if time_out and package_end_time and time_out > package_end_time:
                package_end_datetime = datetime.combine(log_date, package_end_time)
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                day_extra_charges = Decimal("0.00")
                applied_rates = []

                # 1. Handle charges BEFORE 5:30 PM
                cutoff_530 = time(17, 30)
                if package_end_time < cutoff_530 and time_out > package_end_time:
                    end_time_for_before_530 = min(time_out, cutoff_530)

                    if end_time_for_before_530 > package_end_time:
                        before_530_datetime = datetime.combine(
                            log_date, end_time_for_before_530
                        )
                        hours_before_530 = (
                            before_530_datetime - package_end_datetime
                        ).total_seconds() / 3600

                        hour_count = int(hours_before_530)
                        if hours_before_530 % 1 > 0:
                            hour_count += 1

                        for hour_num in range(1, min(hour_count + 1, 7)):
                            rate_obj = (
                                ExtraHoursUpTo530.objects.filter(
                                    hour_number=hour_num,
                                    effective_from__lte=log_date,
                                    is_active=True,
                                )
                                .filter(
                                    Q(effective_to__gte=log_date)
                                    | Q(effective_to__isnull=True)
                                )
                                .first()
                            )

                            if rate_obj:
                                day_extra_charges += rate_obj.extra_rate
                                applied_rates.append(
                                    {
                                        "time_slot": f"Hour {hour_num} (before 5:30 PM)",
                                        "rate": float(rate_obj.extra_rate),
                                        "type": "Before 5:30 PM",
                                    }
                                )

                # 2. Handle charges AFTER 5:30 PM (CUMULATIVE - KEY FIX)
                if time_out > cutoff_530:
                    start_time_after_530 = max(package_end_time, cutoff_530)

                    # Get ALL applicable slots (CUMULATIVE)
                    applicable_slots = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__gte=start_time_after_530,
                            from_time__lt=time_out,
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .order_by("from_time")
                    )

                    # Add charges for ALL applicable slots
                    for slot in applicable_slots:
                        day_extra_charges += slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{slot.from_time.strftime('%H:%M')} - {slot.to_time.strftime('%H:%M')}",
                                "rate": float(slot.extra_rate),
                                "type": "After 5:30 PM",
                            }
                        )

                    # Handle partial slot
                    partial_slot = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__lt=time_out,
                            to_time__gt=time_out,
                            from_time__gte=start_time_after_530,
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .first()
                    )

                    if partial_slot and partial_slot not in [
                        slot for slot in applicable_slots
                    ]:
                        day_extra_charges += partial_slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{partial_slot.from_time.strftime('%H:%M')} - {partial_slot.to_time.strftime('%H:%M')} (partial)",
                                "rate": float(partial_slot.extra_rate),
                                "type": "After 5:30 PM (Partial)",
                            }
                        )

                if day_extra_charges > 0:
                    # Convert decimal hours to hours and minutes format
                    total_minutes = int(extra_hours * 60)
                    hours_part = total_minutes // 60
                    minutes_part = total_minutes % 60

                    if hours_part > 0:
                        extra_hours_display = f"{hours_part} hr{'s' if hours_part != 1 else ''} {minutes_part} min{'s' if minutes_part != 1 else ''}"
                    else:
                        extra_hours_display = (
                            f"{minutes_part} min{'s' if minutes_part != 1 else ''}"
                        )

                    extra_charges_breakdown.append(
                        {
                            "date": log_date.strftime("%Y-%m-%d"),
                            "time_in": time_in.strftime("%H:%M") if time_in else "N/A",
                            "time_out": time_out.strftime("%H:%M"),
                            "extra_hours": round(extra_hours, 2),
                            "extra_hours_display": extra_hours_display,
                            "charges": float(day_extra_charges),
                            "applied_rates": applied_rates,
                        }
                    )
                    extra_hours_charge += day_extra_charges

            # Holiday attendance charge with breakdown
            if is_holiday_day and package_mapping.holiday_package:
                holiday_attendance_days += 1
                expected_days_holiday = (
                    package_mapping.holiday_package.no_days_months or 22
                )
                daily_holiday_rate = (
                    package_mapping.holiday_package.package_total
                    / Decimal(expected_days_holiday)
                )
                holiday_charge += daily_holiday_rate

                holiday_obj = Holiday.objects.filter(
                    start_date__lte=log_date, end_date__gte=log_date, is_active=True
                ).first()

                holiday_charges_breakdown.append(
                    {
                        "date": log_date.strftime("%Y-%m-%d"),
                        "holiday_name": holiday_obj.title if holiday_obj else "Holiday",
                        "rate": float(daily_holiday_rate),
                    }
                )

    # Calculate attendance percentage and package fee
    attendance_percentage = (
        (present_days / expected_days * 100) if expected_days > 0 else 0
    )
    is_half_charge = False

    if attendance_percentage == 0:
        package_fee = Decimal("0.00")
    elif attendance_percentage < 50:
        package_fee = package_total / 2
        is_half_charge = True
    else:
        package_fee = package_total

    # Calculate subtotal
    subtotal = package_fee + extra_hours_charge + holiday_charge

    # Apply discount
    discount_amount = Decimal("0.00")
    if enrollment.discount and enrollment.discount.status == "Approved":
        discount_amount = subtotal * (enrollment.discount.discount_rate / 100)

    total_charge = subtotal - discount_amount

    # Check for existing payments for this month
    existing_memo = InvoiceMemo.objects.filter(
        child=child, month=month, year=year, is_active=True
    ).first()

    payments_received = Decimal("0.00")
    payment_details = []

    if existing_memo:
        payments_received = existing_memo.total_payments_received
        if existing_memo.payment_receipts:
            try:
                import json

                payment_details = json.loads(existing_memo.payment_receipts)
            except:
                payment_details = []

    return {
        "package_name": package.package_name,
        "package_base_fee": package_total,
        "days_attended": present_days,
        "expected_days": expected_days,
        "attendance_percentage": round(attendance_percentage, 2),
        "is_half_charge": is_half_charge,
        "package_fee": package_fee,
        "extra_charges": extra_hours_charge,  # ✅ NOW USES CORRECTED CUMULATIVE CALCULATION
        "holiday_attendance_days": holiday_attendance_days,
        "holiday_charges": holiday_charge,
        "discount": discount_amount,
        "total_charge": total_charge,
        "payments_received": payments_received,
        "payment_details": payment_details,
        # ENHANCED BREAKDOWN DATA
        "extra_charges_breakdown": extra_charges_breakdown,
        "holiday_charges_breakdown": holiday_charges_breakdown,
        "breakdown_summary": {
            "total_extra_instances": len(extra_charges_breakdown),
            "total_holiday_days": len(holiday_charges_breakdown),
            "average_extra_hours": round(
                sum(item["extra_hours"] for item in extra_charges_breakdown)
                / len(extra_charges_breakdown)
                if extra_charges_breakdown
                else 0,
                2,
            ),
        },
    }


def calculate_enhanced_advance_month(child, package_mapping, enrollment, month, year):
    """Enhanced advance month calculation with payment tracking"""
    import json
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

    # Apply discount
    discount_amount = Decimal("0.00")
    if enrollment.discount and enrollment.discount.status == "Approved":
        discount_amount = package_fee * (enrollment.discount.discount_rate / 100)

    total_charge = package_fee - discount_amount

    # Check for existing payments
    existing_memo = InvoiceMemo.objects.filter(
        child=child, month=month, year=year, is_active=True
    ).first()

    payments_received = Decimal("0.00")
    payment_details = []

    if existing_memo:
        payments_received = existing_memo.total_payments_received
        if existing_memo.payment_receipts:
            try:
                payment_details = json.loads(existing_memo.payment_receipts)
            except:
                payment_details = []

    return {
        "package_name": package.package_name,
        "package_base_fee": package_total,
        "expected_days": expected_days,
        "package_fee": package_fee,
        "extra_charges": Decimal("0.00"),
        "holiday_charges": Decimal("0.00"),
        "discount": discount_amount,
        "total_charge": total_charge,
        "payments_received": payments_received,
        "payment_details": payment_details,
    }


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


# Add these view functions to your views.py file


@login_required
def getExtraHoursReport(request):
    """Display extra hours report page"""
    form = ExtraHoursReportForm()
    return render(
        request,
        "../templates/reports/extrahoursreport.html",
        {"form": form, "UserName": request.user.username},
    )


# Complete implementation for views.py - Enhanced extra hours report

# Replace your simplified view with this complete production version


@login_required
def getExtraHoursReportJS(request):
    """Complete production version of extra hours report"""
    try:
        # Get parameters
        child_id = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        report_type = request.GET.get("report_type", "detailed")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")

        # Set default dates if not provided
        if not from_date or not to_date:
            today = datetime.now()
            if report_type == "monthly":
                # Default to current month
                first_day = today.replace(day=1).date()
                last_day = datetime(
                    today.year,
                    today.month,
                    calendar.monthrange(today.year, today.month)[1],
                ).date()
            else:
                # Default to last 30 days
                first_day = (today - timedelta(days=30)).date()
                last_day = today.date()
            from_date = first_day
            to_date = last_day
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Build base filters
        filters = Q(date_logged__range=(from_date, to_date))
        if child_id:
            filters &= Q(child__id=child_id)

        # Add branch/center filters through enrollment
        enrollment_filters = Q()
        if branch_id:
            enrollment_filters &= Q(branch__id=branch_id)
        if center_id:
            enrollment_filters &= Q(center__id=center_id)

        # Get children based on enrollment filters
        if enrollment_filters:
            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters, status="Approved", is_active=True
            ).values_list("child__id", flat=True)
            filters &= Q(child__id__in=enrolled_children)

        # Get attendance logs
        attendance_logs = AttendanceLog.objects.filter(filters).order_by(
            "child", "date_logged", "time_logged"
        )

        # Group by child and date
        logs_by_child_date = defaultdict(list)
        for log in attendance_logs:
            key = (log.child.id, log.date_logged)
            logs_by_child_date[key].append(log)

        extra_hours_data = []

        for (child_id_key, log_date), logs in logs_by_child_date.items():
            if len(logs) < 2:  # Need both in and out
                continue

            # Sort logs by time
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))
            first_log = logs_sorted[0]
            last_log = logs_sorted[-1]

            child = first_log.child
            time_in = first_log.time_logged
            time_out = last_log.time_logged

            # Get package mapping for this date
            package_mapping = (
                ChildPackageMapping.objects.filter(
                    child=child,
                    is_active=True,
                    effective_from__lte=log_date,
                )
                .filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))
                .first()
            )

            if not package_mapping:
                continue

            # Determine the active package and its end time
            package = None
            package_end_time = None
            package_name = "Unknown Package"
            package_type = None

            if package_mapping.normal_package:
                package = package_mapping.normal_package
                package_end_time = package.to_time
                package_name = package.package_name
                package_type = package.package_type
            elif package_mapping.holiday_package:
                package = package_mapping.holiday_package
                package_end_time = package.to_time
                package_name = f"{package.package_name} (Holiday)"
                package_type = package.package_type
            elif package_mapping.flex_package:
                # For flex packages, use standard end time or calculate based on hours
                package = package_mapping.flex_package
                package_name = f"{package.package_name} (Flex)"
                # For flex packages, assume standard end time (e.g., 5:30 PM)
                package_end_time = time(17, 30)  # 5:30 PM as default
                package_type = package.package_type

            if not package_end_time or not time_out:
                continue

            # Calculate extra hours if child stayed beyond package time
            if time_out > package_end_time:
                # Calculate extra time in hours
                package_end_datetime = datetime.combine(log_date, package_end_time)
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                # Get applicable extra hour charges
                extra_charges = Decimal("0.00")
                applied_rates = []

                # Check for extra hours after 5:30 PM charges
                extra_slots_after_530 = ExtraHoursAfter530.objects.filter(
                    package_type=package_type,
                    from_time__lte=time_out,
                    to_time__gte=time_out,
                    effective_from__lte=log_date,
                ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

                for slot in extra_slots_after_530:
                    extra_charges += slot.extra_rate
                    applied_rates.append(
                        {
                            "time_slot": f"{slot.from_time.strftime('%H:%M')} - {slot.to_time.strftime('%H:%M')}",
                            "rate": float(slot.extra_rate),
                            "type": "After 5:30 PM",
                        }
                    )

                # Check for extra hours before 5:30 PM if applicable
                cutoff_530 = time(17, 30)
                if package_end_time < cutoff_530 and time_out > cutoff_530:
                    # Calculate hours between package end and 5:30 PM
                    cutoff_datetime = datetime.combine(log_date, cutoff_530)
                    hours_before_530 = (
                        cutoff_datetime - package_end_datetime
                    ).total_seconds() / 3600

                    # Get rates for hours before 5:30 PM
                    hour_count = int(hours_before_530) + (
                        1 if hours_before_530 % 1 > 0 else 0
                    )
                    for hour_num in range(
                        1, min(hour_count + 1, 7)
                    ):  # Max 6 hours typically
                        rate_obj = (
                            ExtraHoursUpTo530.objects.filter(
                                hour_number=hour_num,
                                effective_from__lte=log_date,
                                is_active=True,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .first()
                        )

                        if rate_obj:
                            extra_charges += rate_obj.extra_rate
                            applied_rates.append(
                                {
                                    "time_slot": f"Hour {hour_num} (before 5:30 PM)",
                                    "rate": float(rate_obj.extra_rate),
                                    "type": "Before 5:30 PM",
                                }
                            )

                # Check if it's a holiday for additional charges
                is_holiday = Holiday.objects.filter(
                    start_date__lte=log_date, end_date__gte=log_date, is_active=True
                ).exists()

                holiday_charge = Decimal("0.00")
                if is_holiday and package_mapping.holiday_package:
                    # Calculate holiday charge (daily rate)
                    expected_days = package_mapping.holiday_package.no_days_months or 22
                    holiday_charge = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days)
                    )

                total_charge = extra_charges + holiday_charge

                # Get child's enrollment details for additional info
                enrollment = ChildEnrollment.objects.filter(
                    child=child, status="Approved", is_active=True
                ).first()

                extra_hours_data.append(
                    {
                        "child_admission": child.admission_number,
                        "child_name": f"{child.child_first_name} {child.child_last_name}",
                        "date": log_date.strftime("%Y-%m-%d"),
                        "day_of_week": log_date.strftime("%A"),
                        "package_name": package_name,
                        "package_end_time": package_end_time.strftime("%H:%M"),
                        "time_in": time_in.strftime("%H:%M") if time_in else "N/A",
                        "time_out": time_out.strftime("%H:%M"),
                        "extra_hours": round(extra_hours, 2),
                        "extra_charges": float(extra_charges),
                        "holiday_charge": float(holiday_charge),
                        "total_charge": float(total_charge),
                        "is_holiday": is_holiday,
                        "applied_rates": applied_rates,
                        "branch_name": enrollment.branch.branch_name
                        if enrollment
                        else "N/A",
                        "center_name": enrollment.center.daycare_name
                        if enrollment
                        else "N/A",
                        "package_type": package_type.package_type_name
                        if package_type
                        else "N/A",
                        "notes": f"Stayed {extra_hours:.2f} hours beyond package time",
                    }
                )

        # Sort by date and child name
        extra_hours_data.sort(key=lambda x: (x["date"], x["child_name"]))

        return JsonResponse(extra_hours_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getExtraHoursSummaryJS(request):
    """Generate summary of extra hours charges by child or month"""
    try:
        child_id = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        summary_type = request.GET.get("summary_type", "child")  # child or month
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")

        # Set default date range if not provided
        if not from_date or not to_date:
            today = datetime.now()
            # Default to current month
            first_day = today.replace(day=1).date()
            last_day = datetime(
                today.year, today.month, calendar.monthrange(today.year, today.month)[1]
            ).date()
            from_date = first_day
            to_date = last_day
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Build base filters
        filters = Q(date_logged__range=(from_date, to_date))
        if child_id:
            filters &= Q(child__id=child_id)

        # Add branch/center filters through enrollment
        enrollment_filters = Q()
        if branch_id:
            enrollment_filters &= Q(branch__id=branch_id)
        if center_id:
            enrollment_filters &= Q(center__id=center_id)

        # Get children based on enrollment filters
        if enrollment_filters:
            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters, status="Approved", is_active=True
            ).values_list("child__id", flat=True)
            filters &= Q(child__id__in=enrolled_children)

        # Get attendance logs grouped by child and date
        attendance_logs = AttendanceLog.objects.filter(filters).order_by(
            "child", "date_logged", "time_logged"
        )

        # Group logs by child and date
        logs_by_child_date = defaultdict(list)
        for log in attendance_logs:
            key = (log.child.id, log.date_logged)
            logs_by_child_date[key].append(log)

        # Get detailed extra hours data (reusing logic from main report)
        extra_hours_detailed = []

        for (child_id_key, log_date), logs in logs_by_child_date.items():
            if len(logs) < 2:  # Skip incomplete attendance
                continue

            # Sort logs by time
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))
            first_log = logs_sorted[0]
            last_log = logs_sorted[-1]

            child = first_log.child
            time_in = first_log.time_logged
            time_out = last_log.time_logged

            # Get package mapping
            package_mapping = (
                ChildPackageMapping.objects.filter(
                    child=child,
                    is_active=True,
                    effective_from__lte=log_date,
                )
                .filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))
                .first()
            )

            if not package_mapping:
                continue

            # Determine package and end time
            package = None
            package_end_time = None
            package_type = None

            if package_mapping.normal_package:
                package = package_mapping.normal_package
                package_end_time = package.to_time
                package_type = package.package_type
            elif package_mapping.holiday_package:
                package = package_mapping.holiday_package
                package_end_time = package.to_time
                package_type = package.package_type
            elif package_mapping.flex_package:
                package = package_mapping.flex_package
                package_end_time = time(17, 30)  # Default for flex
                package_type = package.package_type

            if not package_end_time or not time_out:
                continue

            # Calculate extra hours only if exceeded package time
            if time_out > package_end_time:
                package_end_datetime = datetime.combine(log_date, package_end_time)
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                # Calculate charges
                extra_charges = Decimal("0.00")

                # Extra hours after 5:30 PM
                extra_slots = ExtraHoursAfter530.objects.filter(
                    package_type=package_type,
                    from_time__lte=time_out,
                    to_time__gte=time_out,
                    effective_from__lte=log_date,
                ).filter(Q(effective_to__gte=log_date) | Q(effective_to__isnull=True))

                for slot in extra_slots:
                    extra_charges += slot.extra_rate

                # Extra hours before 5:30 PM
                if package_end_time < time(17, 30):
                    cutoff_530 = time(17, 30)
                    if time_out > cutoff_530:
                        cutoff_datetime = datetime.combine(log_date, cutoff_530)
                        hours_before_530 = (
                            cutoff_datetime - package_end_datetime
                        ).total_seconds() / 3600

                        hour_count = int(hours_before_530) + (
                            1 if hours_before_530 % 1 > 0 else 0
                        )
                        for hour_num in range(1, min(hour_count + 1, 7)):
                            rate_obj = (
                                ExtraHoursUpTo530.objects.filter(
                                    hour_number=hour_num,
                                    effective_from__lte=log_date,
                                    is_active=True,
                                )
                                .filter(
                                    Q(effective_to__gte=log_date)
                                    | Q(effective_to__isnull=True)
                                )
                                .first()
                            )

                            if rate_obj:
                                extra_charges += rate_obj.extra_rate

                # Holiday charges
                is_holiday = Holiday.objects.filter(
                    start_date__lte=log_date, end_date__gte=log_date, is_active=True
                ).exists()

                holiday_charge = Decimal("0.00")
                if is_holiday and package_mapping.holiday_package:
                    expected_days = package_mapping.holiday_package.no_days_months or 22
                    holiday_charge = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days)
                    )

                total_charge = extra_charges + holiday_charge

                # Store detailed data for summary processing
                extra_hours_detailed.append(
                    {
                        "child_id": child.id,
                        "child_admission": child.admission_number,
                        "child_name": f"{child.child_first_name} {child.child_last_name}",
                        "date": log_date,
                        "month_year": log_date.strftime("%Y-%m"),
                        "month_name": log_date.strftime("%B %Y"),
                        "extra_hours": round(extra_hours, 2),
                        "total_charge": float(total_charge),
                        "is_holiday": is_holiday,
                    }
                )

        # Now create summaries based on summary_type
        if summary_type == "child":
            # Group by child
            summary_data = defaultdict(
                lambda: {
                    "child_id": 0,
                    "child_admission": "",
                    "child_name": "",
                    "total_extra_hours": 0,
                    "total_charges": 0,
                    "days_count": 0,
                    "holiday_days": 0,
                    "avg_extra_hours_per_day": 0,
                    "first_occurrence": "",
                    "last_occurrence": "",
                    "peak_month": "",
                    "months_active": set(),
                }
            )

            for item in extra_hours_detailed:
                key = item["child_admission"]
                summary = summary_data[key]

                # Basic info
                summary["child_id"] = item["child_id"]
                summary["child_admission"] = item["child_admission"]
                summary["child_name"] = item["child_name"]

                # Accumulate totals
                summary["total_extra_hours"] += item["extra_hours"]
                summary["total_charges"] += item["total_charge"]
                summary["days_count"] += 1
                if item["is_holiday"]:
                    summary["holiday_days"] += 1

                # Track date range
                if (
                    not summary["first_occurrence"]
                    or item["date"]
                    < datetime.strptime(summary["first_occurrence"], "%Y-%m-%d").date()
                ):
                    summary["first_occurrence"] = item["date"].strftime("%Y-%m-%d")
                if (
                    not summary["last_occurrence"]
                    or item["date"]
                    > datetime.strptime(summary["last_occurrence"], "%Y-%m-%d").date()
                ):
                    summary["last_occurrence"] = item["date"].strftime("%Y-%m-%d")

                # Track months
                summary["months_active"].add(item["month_year"])

            # Calculate derived metrics
            for key, summary in summary_data.items():
                if summary["days_count"] > 0:
                    summary["avg_extra_hours_per_day"] = round(
                        summary["total_extra_hours"] / summary["days_count"], 2
                    )
                summary["months_count"] = len(summary["months_active"])
                summary["months_active"] = list(
                    summary["months_active"]
                )  # Convert set to list for JSON

        else:  # monthly
            # Group by month
            summary_data = defaultdict(
                lambda: {
                    "month_year": "",
                    "month_name": "",
                    "total_extra_hours": 0,
                    "total_charges": 0,
                    "children_count": 0,
                    "days_count": 0,
                    "holiday_days": 0,
                    "avg_extra_hours_per_day": 0,
                    "avg_charge_per_day": 0,
                    "unique_children": set(),
                    "top_child": "",
                    "top_child_hours": 0,
                }
            )

            for item in extra_hours_detailed:
                key = item["month_year"]
                summary = summary_data[key]

                # Basic info
                summary["month_year"] = item["month_year"]
                summary["month_name"] = item["month_name"]

                # Accumulate totals
                summary["total_extra_hours"] += item["extra_hours"]
                summary["total_charges"] += item["total_charge"]
                summary["days_count"] += 1
                if item["is_holiday"]:
                    summary["holiday_days"] += 1

                # Track unique children
                summary["unique_children"].add(item["child_name"])

                # Track top child for this month
                if item["extra_hours"] > summary["top_child_hours"]:
                    summary["top_child"] = item["child_name"]
                    summary["top_child_hours"] = item["extra_hours"]

            # Calculate derived metrics
            for key, summary in summary_data.items():
                summary["children_count"] = len(summary["unique_children"])
                if summary["days_count"] > 0:
                    summary["avg_extra_hours_per_day"] = round(
                        summary["total_extra_hours"] / summary["days_count"], 2
                    )
                    summary["avg_charge_per_day"] = round(
                        summary["total_charges"] / summary["days_count"], 2
                    )
                summary["unique_children"] = list(
                    summary["unique_children"]
                )  # Convert set to list

        # Convert defaultdict to regular dict and sort
        result_data = dict(summary_data)

        if summary_type == "child":
            # Sort by total charges descending
            sorted_items = sorted(
                result_data.items(), key=lambda x: x[1]["total_charges"], reverse=True
            )
        else:
            # Sort by month_year
            sorted_items = sorted(result_data.items(), key=lambda x: x[1]["month_year"])

        # Convert back to dict maintaining order
        result_data = {k: v for k, v in sorted_items}

        # Add overall statistics
        if extra_hours_detailed:
            overall_stats = {
                "total_records": len(extra_hours_detailed),
                "date_range": {
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                },
                "grand_totals": {
                    "total_extra_hours": sum(
                        item["extra_hours"] for item in extra_hours_detailed
                    ),
                    "total_charges": sum(
                        item["total_charge"] for item in extra_hours_detailed
                    ),
                    "unique_children": len(
                        set(item["child_id"] for item in extra_hours_detailed)
                    ),
                    "total_days": len(extra_hours_detailed),
                    "holiday_days": sum(
                        1 for item in extra_hours_detailed if item["is_holiday"]
                    ),
                },
            }

            result_data["_overall_stats"] = overall_stats

        return JsonResponse(result_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


############################################
@login_required
def getChildPackageMapping(request):
    """Display child package mapping page"""
    try:
        # Get all children for dropdown
        children = Child.objects.filter(
            is_active=True, is_enrolled=True, enrollement_approved=True
        ).order_by("admission_number")

        # Get packages for dropdowns
        normal_packages = FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=False
        ).order_by("package_code")

        holiday_packages = FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=True
        ).order_by("package_code")

        flex_packages = FlexPackages.objects.filter(is_active=True).order_by(
            "package_code"
        )

        # ADD THIS: Get approved discounts
        approved_discounts = Discount.objects.filter(
            is_active=True, status="APPROVED"
        ).order_by("discount_code")

        context = {
            "children": children,
            "normal_packages": normal_packages,
            "holiday_packages": holiday_packages,
            "flex_packages": flex_packages,
            "approved_discounts": approved_discounts,  # ADD THIS
            "UserName": request.user.username,
        }

        return render(request, "../templates/utils/missing_mappings.html", context)

    except Exception as e:
        messages.error(request, f"Error loading page: {str(e)}")
        # Try different redirect options
        try:
            return redirect("core:view_child")  # Try child view
        except:
            try:
                return redirect("/")  # Try home page
            except:
                # If all else fails, show the error on the same page
                context = {
                    "children": [],
                    "normal_packages": [],
                    "holiday_packages": [],
                    "flex_packages": [],
                    "UserName": request.user.username,
                }
                return render(
                    request, "../templates/utils/missing_mappings.html", context
                )


@login_required
def getPackageMappingsJS(request):
    """Return package mappings data as JSON for DataTable with search functionality"""
    try:
        # Get search parameters
        child_id = request.GET.get("child_id")
        status = request.GET.get("status")
        effective_date = request.GET.get("effective_date")

        # Start with base query
        mappings = ChildPackageMapping.objects.select_related(
            "child", "normal_package", "holiday_package", "flex_package", "discount"
        ).filter(child__is_active=True)

        # Apply search filters
        if child_id:
            mappings = mappings.filter(child_id=child_id)

        if status:
            is_active = status.lower() == "true"
            mappings = mappings.filter(is_active=is_active)

        if effective_date:
            from datetime import datetime

            date_obj = datetime.strptime(effective_date, "%Y-%m-%d").date()
            mappings = mappings.filter(effective_from__lte=date_obj).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=date_obj)
            )

        # Order by most recent first
        mappings = mappings.order_by("-effective_from")

        mapping_data = []

        for mapping in mappings:
            # Build child name
            child_name = f"{mapping.child.admission_number} - {mapping.child.child_first_name} {mapping.child.child_last_name}"

            # Get package details with codes and amounts
            normal_package_name = None
            normal_package_code = None
            normal_package_amount = None

            holiday_package_name = None
            holiday_package_code = None
            holiday_package_amount = None

            flex_package_name = None
            flex_package_code = None
            flex_package_amount = None

            if mapping.normal_package:
                normal_package_name = mapping.normal_package.package_name
                normal_package_code = mapping.normal_package.package_code
                normal_package_amount = float(mapping.normal_package.package_total)

            if mapping.holiday_package:
                holiday_package_name = mapping.holiday_package.package_name
                holiday_package_code = mapping.holiday_package.package_code
                holiday_package_amount = float(mapping.holiday_package.package_total)

            if mapping.flex_package:
                flex_package_name = mapping.flex_package.package_name
                flex_package_code = mapping.flex_package.package_code
                flex_package_amount = float(mapping.flex_package.package_total)

            # Format dates
            effective_from = (
                mapping.effective_from.strftime("%Y-%m-%d")
                if mapping.effective_from
                else ""
            )
            effective_to = (
                mapping.effective_to.strftime("%Y-%m-%d")
                if mapping.effective_to
                else None
            )

            # Determine main package type for better display
            main_package_type = (
                "normal"
                if normal_package_name
                else ("flex" if flex_package_name else None)
            )

            # Get discount info
            discount_info = None
            try:
                if hasattr(mapping, "discount") and mapping.discount:
                    discount_info = f"{mapping.discount.discount_code} - {mapping.discount.discount_name} ({mapping.discount.discount_rate}%)"
            except AttributeError:
                discount_info = None
            except Exception as e:
                print(f"Error getting discount info: {e}")
                discount_info = None

            mapping_data.append(
                {
                    "id": mapping.id,
                    "child_id": mapping.child.id,
                    "child_name": child_name,
                    # Normal package details
                    "normal_package_name": normal_package_name,
                    "normal_package_code": normal_package_code,
                    "normal_package_amount": normal_package_amount,
                    # Holiday package details
                    "holiday_package_name": holiday_package_name,
                    "holiday_package_code": holiday_package_code,
                    "holiday_package_amount": holiday_package_amount,
                    # Flex package details
                    "flex_package_name": flex_package_name,
                    "flex_package_code": flex_package_code,
                    "flex_package_amount": flex_package_amount,
                    # Other info
                    "discount_info": discount_info,
                    "main_package_type": main_package_type,
                    "effective_from": effective_from,
                    "effective_to": effective_to,
                    "is_active": mapping.is_active,
                }
            )

        return JsonResponse(mapping_data, safe=False)

    except Exception as e:
        print(f"Error in getPackageMappingsJS: {str(e)}")
        import traceback

        traceback.print_exc()

        return JsonResponse({"error": str(e)}, status=500)


@login_required
def checkChildPackageMapping(request):
    """Check if child already has an active package mapping"""
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # Check for active mapping
        active_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        if active_mapping:
            # Build mapping details
            packages = []

            # Main package (Normal or Flex)
            if active_mapping.normal_package:
                packages.append(
                    f"Main Package: {active_mapping.normal_package.package_name} (Normal)"
                )
            elif active_mapping.flex_package:
                packages.append(
                    f"Main Package: {active_mapping.flex_package.package_name} (Flex)"
                )

            # Holiday package
            if active_mapping.holiday_package:
                packages.append(
                    f"Holiday Package: {active_mapping.holiday_package.package_name}"
                )

            mapping_details = (
                " | ".join(packages) if packages else "No packages assigned"
            )

            # Suggest next effective date (day after current mapping ends, or tomorrow if open-ended)
            from datetime import datetime, timedelta

            if active_mapping.effective_to:
                suggested_date = (
                    active_mapping.effective_to + timedelta(days=1)
                ).strftime("%Y-%m-%d")
            else:
                suggested_date = (datetime.now().date() + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )

            return JsonResponse(
                {
                    "exists": True,
                    "mapping_id": active_mapping.id,
                    "mapping_details": mapping_details,
                    "effective_from": active_mapping.effective_from.strftime("%Y-%m-%d")
                    if active_mapping.effective_from
                    else "",
                    "effective_to": active_mapping.effective_to.strftime("%Y-%m-%d")
                    if active_mapping.effective_to
                    else None,
                    "suggested_effective_from": suggested_date,
                    "current_mapping": {
                        "packages": packages,
                        "effective_from": active_mapping.effective_from.strftime(
                            "%Y-%m-%d"
                        )
                        if active_mapping.effective_from
                        else "",
                        "effective_to": active_mapping.effective_to.strftime("%Y-%m-%d")
                        if active_mapping.effective_to
                        else None,
                        "has_main_package": bool(
                            active_mapping.normal_package or active_mapping.flex_package
                        ),
                        "has_holiday_package": bool(active_mapping.holiday_package),
                    },
                }
            )
        else:
            return JsonResponse({"exists": False})

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def savePackageMapping(request):
    """Save new package mapping with validation for 2-package structure"""
    try:
        if request.method != "POST":
            messages.error(request, "Invalid request method")
            return redirect("core:view_child_package_mapping")

        # Get form data
        child_id = request.POST.get("child")
        main_package_type = request.POST.get("main_package_type")  # 'normal' or 'flex'
        normal_package_id = request.POST.get("normal_package")
        flex_package_id = request.POST.get("flex_package")
        holiday_package_id = request.POST.get("holiday_package")
        discount_id = request.POST.get("discount")
        effective_from = request.POST.get("effective_from")
        effective_to = request.POST.get("effective_to")

        # Validation
        if not all([child_id, main_package_type, holiday_package_id, effective_from]):
            messages.error(request, "Missing required fields")
            return redirect("core:view_child_package_mapping")

        # Validate main package selection
        if main_package_type == "normal" and not normal_package_id:
            messages.error(
                request, "Normal package is required when main package type is Normal"
            )
            return redirect("core:view_child_package_mapping")

        if main_package_type == "flex" and not flex_package_id:
            messages.error(
                request, "Flex package is required when main package type is Flex"
            )
            return redirect("core:view_child_package_mapping")

        # Get child
        child = Child.objects.get(id=child_id)

        # Parse dates
        from datetime import datetime, timedelta

        effective_from_date = datetime.strptime(effective_from, "%Y-%m-%d").date()
        effective_to_date = None
        if effective_to:
            effective_to_date = datetime.strptime(effective_to, "%Y-%m-%d").date()

            # Validate date range
            if effective_to_date <= effective_from_date:
                messages.error(
                    request, "Effective To date must be after Effective From date"
                )
                return redirect("core:view_child_package_mapping")

        # Check for overlapping mappings
        overlap_query = ChildPackageMapping.objects.filter(
            child=child, is_active=True, effective_from__lte=effective_from_date
        )

        if effective_to_date:
            overlap_query = overlap_query.filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from_date)
            )
        else:
            overlap_query = overlap_query.filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from_date)
            )

        if overlap_query.exists():
            messages.error(
                request,
                "A package mapping already exists for this period. Please deactivate the existing mapping or adjust the dates.",
            )
            return redirect("core:view_child_package_mapping")

        # Create new mapping
        with transaction.atomic():
            # First, deactivate any existing active mappings for this child
            ChildPackageMapping.objects.filter(child=child, is_active=True).update(
                is_active=False,
                effective_to=effective_from_date - timedelta(days=1),
                user_updated=request.user.username,
                date_updated=datetime.now(),
            )

            # Create the new mapping
            mapping = ChildPackageMapping.objects.create(
                child=child,
                effective_from=effective_from_date,
                effective_to=effective_to_date,
                user_created=request.user.username,
                is_active=True,
            )

            # Set main package based on type
            if main_package_type == "normal":
                mapping.normal_package = FixedPackage.objects.get(id=normal_package_id)
            elif main_package_type == "flex":
                mapping.flex_package = FlexPackages.objects.get(id=flex_package_id)

            # Always set holiday package (required)
            mapping.holiday_package = FixedPackage.objects.get(id=holiday_package_id)

            if discount_id:
                mapping.discount = Discount.objects.get(id=discount_id)

            mapping.save()

        messages.success(
            request,
            f"Package mapping created successfully for {child.admission_number}",
        )
        return redirect("core:view_child_package_mapping")

    except Child.DoesNotExist:
        messages.error(request, "Child not found")
    except FixedPackage.DoesNotExist:
        messages.error(request, "Selected package not found")
    except FlexPackages.DoesNotExist:
        messages.error(request, "Selected flex package not found")
    except Exception as e:
        messages.error(request, f"Error saving package mapping: {str(e)}")

    return redirect("core:view_child_package_mapping")


@login_required
def getPackageMappingDetails(request, pk):
    """Get detailed package mapping information"""
    try:
        mapping = get_object_or_404(ChildPackageMapping, pk=pk)

        # Determine main package details
        main_package = None
        main_package_type = None

        if mapping.normal_package:
            main_package = mapping.normal_package
            main_package_type = "normal"
        elif mapping.flex_package:
            main_package = mapping.flex_package
            main_package_type = "flex"

        details = {
            "id": mapping.id,
            "child": {
                "id": mapping.child.id,
                "name": f"{mapping.child.child_first_name} {mapping.child.child_last_name}",
                "admission_number": mapping.child.admission_number,
            },
            "main_package": {
                "id": main_package.id if main_package else None,
                "name": main_package.package_name if main_package else None,
                "code": main_package.package_code if main_package else None,
                "type": main_package_type,
                "total": float(main_package.package_total) if main_package else 0,
                "from_time": main_package.from_time.strftime("%H:%M")
                if hasattr(main_package, "from_time") and main_package.from_time
                else None,
                "to_time": main_package.to_time.strftime("%H:%M")
                if hasattr(main_package, "to_time") and main_package.to_time
                else None,
                "hours": main_package.no_hours
                if hasattr(main_package, "no_hours")
                else None,
            },
            "holiday_package": {
                "id": mapping.holiday_package.id if mapping.holiday_package else None,
                "name": mapping.holiday_package.package_name
                if mapping.holiday_package
                else None,
                "code": mapping.holiday_package.package_code
                if mapping.holiday_package
                else None,
                "total": float(mapping.holiday_package.package_total)
                if mapping.holiday_package
                else 0,
            },
            "effective_from": mapping.effective_from.strftime("%Y-%m-%d")
            if mapping.effective_from
            else None,
            "effective_to": mapping.effective_to.strftime("%Y-%m-%d")
            if mapping.effective_to
            else None,
            "is_active": mapping.is_active,
            "created_by": mapping.user_created,
            "created_date": mapping.date_created.strftime("%Y-%m-%d %H:%M")
            if mapping.date_created
            else None,
            "updated_by": mapping.user_updated,
            "updated_date": mapping.date_updated.strftime("%Y-%m-%d %H:%M")
            if mapping.date_updated
            else None,
        }

        return JsonResponse(details)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getChildPackageMappingHistory(request):
    """Get complete package mapping history for a child"""
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # Get all mappings for this child (active and inactive)
        mappings = (
            ChildPackageMapping.objects.filter(child=child)
            .select_related("normal_package", "holiday_package", "flex_package")
            .order_by("-effective_from")
        )

        history_data = []

        for mapping in mappings:
            # Build package description
            packages = []

            if mapping.normal_package:
                packages.append(f"Main: {mapping.normal_package.package_name} (Normal)")
            elif mapping.flex_package:
                packages.append(f"Main: {mapping.flex_package.package_name} (Flex)")

            if mapping.holiday_package:
                packages.append(f"Holiday: {mapping.holiday_package.package_name}")

            package_details = " | ".join(packages) if packages else "No packages"

            history_data.append(
                {
                    "id": mapping.id,
                    "packages": packages,
                    "package_details": package_details,
                    "effective_from": mapping.effective_from.strftime("%Y-%m-%d")
                    if mapping.effective_from
                    else "",
                    "effective_to": mapping.effective_to.strftime("%Y-%m-%d")
                    if mapping.effective_to
                    else "Open-ended",
                    "is_active": mapping.is_active,
                    "created_by": mapping.user_created,
                    "created_date": mapping.date_created.strftime("%Y-%m-%d %H:%M")
                    if mapping.date_created
                    else "",
                    "updated_by": mapping.user_updated or "",
                    "updated_date": mapping.date_updated.strftime("%Y-%m-%d %H:%M")
                    if mapping.date_updated
                    else "",
                }
            )

        return JsonResponse(
            {
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "child_admission": child.admission_number,
                "history": history_data,
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getPackageMappingForUpdate(request, pk):
    """Get package mapping for update"""
    try:
        mapping = get_object_or_404(ChildPackageMapping, pk=pk)

        # Get all packages for dropdowns
        normal_packages = FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=False
        ).order_by("package_code")

        holiday_packages = FixedPackage.objects.filter(
            is_active=True, package_type__is_holiday_package=True
        ).order_by("package_code")

        flex_packages = FlexPackages.objects.filter(is_active=True).order_by(
            "package_code"
        )

        context = {
            "mapping": mapping,
            "normal_packages": normal_packages,
            "holiday_packages": holiday_packages,
            "flex_packages": flex_packages,
        }

        return render(
            request, "../templates/partials/package_mapping_update.html", context
        )

    except Exception as e:
        messages.error(request, f"Error loading mapping: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def updatePackageMapping(request):
    """Update existing package mapping"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=400)

        mapping_id = request.POST.get("mapping_id")
        package_type = request.POST.get("package_type")
        normal_package_id = request.POST.get("normal_package")
        holiday_package_id = request.POST.get("holiday_package")
        flex_package_id = request.POST.get("flex_package")
        additional_holiday_package_id = request.POST.get("additional_holiday_package")
        effective_from = request.POST.get("effective_from")
        effective_to = request.POST.get("effective_to")

        if not all([mapping_id, package_type, effective_from]):
            messages.error(request, "Missing required fields")
            return redirect("core:view_child_package_mapping")

        # Get mapping
        mapping = ChildPackageMapping.objects.get(id=mapping_id)

        # Parse dates
        effective_from_date = datetime.strptime(effective_from, "%Y-%m-%d").date()
        effective_to_date = None
        if effective_to:
            effective_to_date = datetime.strptime(effective_to, "%Y-%m-%d").date()

            if effective_to_date <= effective_from_date:
                messages.error(
                    request, "Effective To date must be after Effective From date"
                )
                return redirect("core:view_child_package_mapping")

        with transaction.atomic():
            # Clear existing packages
            mapping.normal_package = None
            mapping.holiday_package = None
            mapping.flex_package = None
            mapping.is_holiday_package = False

            # Update basic fields
            mapping.effective_from = effective_from_date
            mapping.effective_to = effective_to_date
            mapping.user_updated = request.user.username
            mapping.date_updated = datetime.now()

            # Set packages based on type
            if package_type == "normal" and normal_package_id:
                mapping.normal_package = FixedPackage.objects.get(id=normal_package_id)
                if additional_holiday_package_id:
                    mapping.holiday_package = FixedPackage.objects.get(
                        id=additional_holiday_package_id
                    )

            elif package_type == "holiday" and holiday_package_id:
                mapping.holiday_package = FixedPackage.objects.get(
                    id=holiday_package_id
                )
                mapping.is_holiday_package = True

            elif package_type == "flex" and flex_package_id:
                mapping.flex_package = FlexPackages.objects.get(id=flex_package_id)
                if additional_holiday_package_id:
                    mapping.holiday_package = FixedPackage.objects.get(
                        id=additional_holiday_package_id
                    )
            else:
                messages.error(request, "Invalid package selection")
                return redirect("core:view_child_package_mapping")

            mapping.save()

        messages.success(request, "Package mapping updated successfully")
        return redirect("core:view_child_package_mapping")

    except ChildPackageMapping.DoesNotExist:
        messages.error(request, "Package mapping not found")
    except Exception as e:
        messages.error(request, f"Error updating package mapping: {str(e)}")

    return redirect("core:view_child_package_mapping")


@login_required
@transaction.atomic
def deactivatePackageMapping(request, pk):
    """Deactivate package mapping"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=400)

        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            return JsonResponse(
                {"error": "You are not authorized to perform this operation."},
                status=403,
            )

        mapping = get_object_or_404(ChildPackageMapping, pk=pk)

        with transaction.atomic():
            mapping.is_active = False
            mapping.effective_to = datetime.now().date()
            mapping.user_updated = request.user.username
            mapping.date_updated = datetime.now()
            mapping.save()

        return JsonResponse(
            {"success": True, "message": "Package mapping deactivated successfully"}
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getChildPackageMappingHistory(request):
    """Get package mapping history for a child"""
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # Get all mappings for this child (active and inactive)
        mappings = (
            ChildPackageMapping.objects.filter(child=child)
            .select_related("normal_package", "holiday_package", "flex_package")
            .order_by("-effective_from")
        )

        history_data = []

        for mapping in mappings:
            packages = []
            if mapping.normal_package:
                packages.append(f"Normal: {mapping.normal_package.package_name}")
            if mapping.holiday_package:
                packages.append(f"Holiday: {mapping.holiday_package.package_name}")
            if mapping.flex_package:
                packages.append(f"Flex: {mapping.flex_package.package_name}")

            history_data.append(
                {
                    "id": mapping.id,
                    "packages": packages,
                    "package_details": " | ".join(packages),
                    "effective_from": mapping.effective_from.strftime("%Y-%m-%d")
                    if mapping.effective_from
                    else "",
                    "effective_to": mapping.effective_to.strftime("%Y-%m-%d")
                    if mapping.effective_to
                    else "Open-ended",
                    "is_active": mapping.is_active,
                    "created_by": mapping.user_created,
                    "created_date": mapping.date_created.strftime("%Y-%m-%d %H:%M")
                    if mapping.date_created
                    else "",
                    "updated_by": mapping.user_updated or "",
                    "updated_date": mapping.date_updated.strftime("%Y-%m-%d %H:%M")
                    if mapping.date_updated
                    else "",
                }
            )

        return JsonResponse(
            {
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "child_admission": child.admission_number,
                "history": history_data,
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def validatePackageMappingOverlap(request):
    """Validate if new mapping dates overlap with existing mappings"""
    try:
        child_id = request.GET.get("child_id")
        effective_from = request.GET.get("effective_from")
        effective_to = request.GET.get("effective_to")
        exclude_mapping_id = request.GET.get("exclude_mapping_id")  # For updates

        if not all([child_id, effective_from]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)
        effective_from_date = datetime.strptime(effective_from, "%Y-%m-%d").date()
        effective_to_date = None
        if effective_to:
            effective_to_date = datetime.strptime(effective_to, "%Y-%m-%d").date()

        # Check for overlapping mappings
        overlap_query = ChildPackageMapping.objects.filter(child=child, is_active=True)

        if exclude_mapping_id:
            overlap_query = overlap_query.exclude(id=exclude_mapping_id)

        # Complex overlap logic
        if effective_to_date:
            # New mapping has end date - check for any overlap
            overlap_query = overlap_query.filter(
                Q(effective_from__lte=effective_to_date)
                & (
                    Q(effective_to__gte=effective_from_date)
                    | Q(effective_to__isnull=True)
                )
            )
        else:
            # New mapping is open-ended - check if any mapping starts before our start date
            overlap_query = overlap_query.filter(
                Q(effective_to__gte=effective_from_date) | Q(effective_to__isnull=True)
            )

        overlapping_mappings = list(
            overlap_query.values(
                "id",
                "effective_from",
                "effective_to",
                "normal_package__package_name",
                "holiday_package__package_name",
                "flex_package__package_name",
            )
        )

        if overlapping_mappings:
            overlap_details = []
            for mapping in overlapping_mappings:
                packages = []
                if mapping["normal_package__package_name"]:
                    packages.append(
                        f"Normal: {mapping['normal_package__package_name']}"
                    )
                if mapping["holiday_package__package_name"]:
                    packages.append(
                        f"Holiday: {mapping['holiday_package__package_name']}"
                    )
                if mapping["flex_package__package_name"]:
                    packages.append(f"Flex: {mapping['flex_package__package_name']}")

                overlap_details.append(
                    {
                        "id": mapping["id"],
                        "packages": " | ".join(packages),
                        "effective_from": mapping["effective_from"].strftime(
                            "%Y-%m-%d"
                        ),
                        "effective_to": mapping["effective_to"].strftime("%Y-%m-%d")
                        if mapping["effective_to"]
                        else "Open-ended",
                    }
                )

            return JsonResponse(
                {
                    "overlap": True,
                    "overlapping_mappings": overlap_details,
                    "message": "Date range overlaps with existing package mappings",
                }
            )
        else:
            return JsonResponse(
                {"overlap": False, "message": "No overlapping mappings found"}
            )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


########################## Manual Memo############################################
# Add these views to your views.py file


@login_required
def getMemoDataEntry(request):
    """Display memo data entry page"""
    try:
        # Get children for dropdown
        children = Child.objects.filter(is_active=True, is_enrolled=True).order_by(
            "admission_number"
        )

        # Generate year range
        current_year = datetime.now().year
        year_range = [
            current_year - 2,
            current_year - 1,
            current_year,
            current_year + 1,
        ]

        context = {
            "children": children,
            "year_range": year_range,
            "UserName": request.user.username,
        }

        return render(request, "../templates/utils/memo_manual.html", context)

    except Exception as e:
        messages.error(request, f"Error loading page: {str(e)}")
        return redirect("core:view_invoice_memos")


@login_required
def getChildPackageDetails(request):
    """Get child's package details for auto-filling including discount info"""
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # Get active package mapping
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        if not package_mapping:
            return JsonResponse({"error": "No package mapping found"}, status=404)

        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        if not package_mapping:
            return JsonResponse({"error": "No package mapping found"}, status=404)

        # Determine which package is active
        package_name = "Unknown Package"
        package_fee = 0

        if package_mapping.normal_package:
            package_name = package_mapping.normal_package.package_name
            package_fee = float(package_mapping.normal_package.package_total)
        elif package_mapping.holiday_package:
            package_name = f"{package_mapping.holiday_package.package_name} (Holiday)"
            package_fee = float(package_mapping.holiday_package.package_total)
        elif package_mapping.flex_package:
            package_name = f"{package_mapping.flex_package.package_name} (Flex)"
            package_fee = float(package_mapping.flex_package.package_total)

        # Get discount information
        discount_rate = 0
        discount_name = ""
        if (
            package_mapping.discount
            and package_mapping.discount.is_active
            and package_mapping.discount.status == "Approved"
        ):
            discount_rate = float(package_mapping.discount.discount_rate)
            discount_name = package_mapping.discount.discount_name

        return JsonResponse(
            {
                "package_name": package_name,
                "package_fee": package_fee,
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "admission_number": child.admission_number,
                "discount_rate": discount_rate,
                "discount_name": discount_name,
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getAttendanceSummary(request):
    """Get attendance summary for a child in a specific month with enhanced details"""
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing parameters"}, status=400)

        child = Child.objects.get(id=child_id)

        # Use the helper function
        attendance_data = calculate_month_attendance_summary(
            child, int(month), int(year)
        )

        return JsonResponse(attendance_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def calculateMemoData(request):
    """Calculate memo data automatically from system data"""
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing parameters"}, status=400)

        child = Child.objects.get(id=child_id)

        # Use existing 3-month calculation function
        three_month_data = calculate_three_month_invoice_data(child, month, year)

        # Extract data for form filling
        calculated_data = {
            "outstanding_amount": float(three_month_data["month1"]["balance"]),
            "payment_settled": float(three_month_data["month1"]["payments"]),
            "package_fee": float(three_month_data["month2"]["package_fee"]),
            "extra_hours": float(three_month_data["month2"]["extra_charges"]),
            "holiday_charges": float(three_month_data["month2"]["holiday_charges"]),
            "discount_applied": float(three_month_data["month2"]["discount"]),
            "advance_payment": float(three_month_data["month3"]["package_fee"]),
            "current_payment": 0,  # No payment yet
        }

        return JsonResponse(calculated_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def saveMemoDataEntry(request):
    """Enhanced save manually entered memo data with breakdown storage"""
    try:
        if request.method != "POST":
            messages.error(request, "Invalid request method")
            return redirect("core:memo_data_entry")

        # Extract form data
        child_id = request.POST.get("child")
        month = request.POST.get("month")
        year = request.POST.get("year")

        # Outstanding (2 months ago)
        outstanding_amount = Decimal(request.POST.get("outstanding_amount") or "0")
        outstanding_payment = Decimal(request.POST.get("payment_settled") or "0")
        outstanding_receipt = request.POST.get("outstanding_receipt_number", "").strip()

        # Previous month (1 month ago)
        prev_package_fee = Decimal(request.POST.get("previous_package_fee") or "0")
        prev_extra_hours = Decimal(request.POST.get("previous_extra_hours") or "0")
        prev_holiday_charges = Decimal(
            request.POST.get("previous_holiday_charges") or "0"
        )
        prev_discount = Decimal(request.POST.get("previous_discount_applied") or "0")
        prev_payment = Decimal(request.POST.get("previous_payment") or "0")
        prev_receipt = request.POST.get("previous_receipt_number", "").strip()

        # Get attendance data for previous month
        prev_days_attended = int(request.POST.get("previous_days_attended") or "0")
        prev_expected_days = int(request.POST.get("previous_expected_days") or "22")

        # Current month
        curr_package_fee = Decimal(request.POST.get("package_fee") or "0")
        curr_extra_hours = Decimal(request.POST.get("extra_hours") or "0")
        curr_holiday_charges = Decimal(request.POST.get("holiday_charges") or "0")
        curr_discount = Decimal(request.POST.get("discount_applied") or "0")
        curr_payment = Decimal(request.POST.get("current_payment") or "0")
        curr_receipt = request.POST.get("current_receipt_number", "").strip()

        # Validation
        if not all([child_id, month, year]):
            messages.error(request, "Please fill in all required fields")
            return redirect("core:memo_data_entry")

        month_int = int(month)
        year_int = int(year)
        child = Child.objects.get(id=child_id, is_active=True)

        # Check if memo already exists
        if InvoiceMemo.objects.filter(
            child=child, memo_month=month_int, memo_year=year_int
        ).exists():
            messages.error(
                request,
                f"Memo already exists for {calendar.month_name[month_int]} {year_int}",
            )
            return redirect("core:memo_data_entry")

        # Calculate month details for detail records
        prev_month = month_int - 1 if month_int > 1 else 12
        prev_year = year_int if month_int > 1 else year_int - 1
        outstanding_month = month_int - 2 if month_int > 2 else (12 + month_int - 2)
        outstanding_year = year_int if month_int > 2 else year_int - 1

        # Generate memo code
        next_memo_id = InvoiceMemo.objects.count() + 1
        memo_code = f"MO{next_memo_id:04d}"
        while InvoiceMemo.objects.filter(memo_code=memo_code).exists():
            next_memo_id += 1
            memo_code = f"MO{next_memo_id:04d}"

        # Get child info
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not package_mapping or not enrollment:
            messages.error(request, "No active package mapping or enrollment found")
            return redirect("core:memo_data_entry")

        # Determine package name
        package_name = "Manual Entry Package"
        if package_mapping.normal_package:
            package_name = package_mapping.normal_package.package_name
        elif package_mapping.holiday_package:
            package_name = f"{package_mapping.holiday_package.package_name} (Holiday)"
        elif package_mapping.flex_package:
            package_name = f"{package_mapping.flex_package.package_name} (Flex)"

        with transaction.atomic():
            # Create main memo record
            memo = InvoiceMemo.objects.create(
                memo_date=datetime.now().date(),
                memo_code=memo_code,
                child=child,
                memo_month=month_int,
                memo_year=year_int,
                status="GENERATED",
                notes=f"Manually entered memo on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                user_created=request.user.username,
            )

            # Create Outstanding Month Detail (Month 1)
            outstanding_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=1,
                month_type="OUTSTANDING",
                actual_month=outstanding_month,
                actual_year=outstanding_year,
                month_name=calendar.month_name[outstanding_month],
                package_fee=outstanding_amount,
                extra_hours_charge=Decimal("0"),
                holiday_charges=Decimal("0"),
                discount_applied=Decimal("0"),
                payments_received=outstanding_payment,
                payment_receipts=[
                    {
                        "amount": float(outstanding_payment),
                        "receipt_number": outstanding_receipt,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "type": "outstanding_settlement",
                    }
                ]
                if outstanding_payment > 0
                else [],
                package_name="Outstanding Balance",
                notes="Outstanding balance from previous periods",
                calculation_details={
                    "manually_entered": True,
                    "original_outstanding": float(outstanding_amount),
                    "payment_settled": float(outstanding_payment),
                    "receipt_number": outstanding_receipt,
                },
                user_created=request.user.username,
            )

            # Try to get detailed breakdown if child has data for previous month
            detailed_breakdown = {}
            try:
                # Attempt to get detailed charges breakdown for previous month
                detailed_breakdown_response = getDetailedChargesBreakdown(
                    type(
                        "MockRequest",
                        (),
                        {
                            "GET": {
                                "child_id": child_id,
                                "month": str(prev_month),
                                "year": str(prev_year),
                            }
                        },
                    )()
                )

                if hasattr(detailed_breakdown_response, "content"):
                    import json

                    breakdown_data = json.loads(detailed_breakdown_response.content)
                    if breakdown_data.get("success"):
                        detailed_breakdown = {
                            "extra_hours_breakdown": breakdown_data.get(
                                "extra_hours", {}
                            ).get("breakdown", []),
                            "holiday_charges_breakdown": breakdown_data.get(
                                "holiday_charges", {}
                            ).get("breakdown", []),
                            "summary": breakdown_data.get("summary", {}),
                        }
            except Exception as e:
                print(f"Could not get detailed breakdown: {str(e)}")
                # Create summary breakdown if detailed data not available
                if prev_extra_hours > 0:
                    detailed_breakdown["extra_hours_breakdown"] = [
                        {
                            "date": f"{prev_year}-{prev_month:02d}-15",
                            "time_out": "Manual Entry",
                            "extra_hours_display": "Manual entry - detailed breakdown not available",
                            "charges": float(prev_extra_hours),
                            "type": "manual_summary",
                        }
                    ]

                if prev_holiday_charges > 0:
                    detailed_breakdown["holiday_charges_breakdown"] = [
                        {
                            "date": f"{prev_year}-{prev_month:02d}-15",
                            "holiday_name": "Manual Entry",
                            "charges": float(prev_holiday_charges),
                            "type": "manual_summary",
                        }
                    ]

            # Create Previous Month Detail (Month 2) with breakdown data
            previous_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=2,
                month_type="PREVIOUS",
                actual_month=prev_month,
                actual_year=prev_year,
                month_name=calendar.month_name[prev_month],
                package_fee=prev_package_fee,
                extra_hours_charge=prev_extra_hours,
                holiday_charges=prev_holiday_charges,
                discount_applied=prev_discount,
                payments_received=prev_payment,
                payment_receipts=[
                    {
                        "amount": float(prev_payment),
                        "receipt_number": prev_receipt,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "type": "previous_month_payment",
                    }
                ]
                if prev_payment > 0
                else [],
                package_name=package_name,
                days_attended=prev_days_attended,
                expected_days=prev_expected_days,
                attendance_percentage=round(
                    (prev_days_attended / prev_expected_days * 100), 2
                )
                if prev_expected_days > 0
                else 0,
                is_half_charge_applied=prev_days_attended < (prev_expected_days * 0.5),
                notes=f"Previous month - Package: Rs.{prev_package_fee}, Extra Hours: Rs.{prev_extra_hours}, Holiday: Rs.{prev_holiday_charges}",
                calculation_details={
                    "manually_entered": True,
                    "breakdown": {
                        "package_fee": float(prev_package_fee),
                        "extra_hours": float(prev_extra_hours),
                        "holiday_charges": float(prev_holiday_charges),
                        "discount": float(prev_discount),
                    },
                    # Store detailed breakdown if available
                    **detailed_breakdown,
                },
                user_created=request.user.username,
            )

            # Create Current Month Detail (Month 3)
            current_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=3,
                month_type="CURRENT",
                actual_month=month_int,
                actual_year=year_int,
                month_name=calendar.month_name[month_int],
                package_fee=curr_package_fee,
                extra_hours_charge=curr_extra_hours,
                holiday_charges=curr_holiday_charges,
                discount_applied=curr_discount,
                payments_received=curr_payment,
                payment_receipts=[
                    {
                        "amount": float(curr_payment),
                        "receipt_number": curr_receipt,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "type": "current_month_payment",
                    }
                ]
                if curr_payment > 0
                else [],
                package_name=package_name,
                expected_days=22,
                notes=f"Current month - Package: Rs.{curr_package_fee}, Extra Hours: Rs.{curr_extra_hours}, Holiday: Rs.{curr_holiday_charges}",
                calculation_details={
                    "manually_entered": True,
                    "breakdown": {
                        "package_fee": float(curr_package_fee),
                        "extra_hours": float(curr_extra_hours),
                        "holiday_charges": float(curr_holiday_charges),
                        "discount": float(curr_discount),
                    },
                },
                user_created=request.user.username,
            )

            # Calculate memo totals automatically using the model method
            memo.calculate_totals()
            memo.save()

        # Success message with detailed breakdown
        success_message = (
            f"Enhanced memo {memo_code} created successfully! "
            f"Outstanding: Rs.{outstanding_detail.net_balance:,.2f}, "
            f"Previous: Rs.{previous_detail.net_balance:,.2f}, "
            f"Current: Rs.{current_detail.net_balance:,.2f}, "
            f"Total Due: Rs.{memo.net_amount_due:,.2f}"
        )
        if detailed_breakdown.get("extra_hours_breakdown") or detailed_breakdown.get(
            "holiday_charges_breakdown"
        ):
            success_message += " (Detailed breakdown included)"

        messages.success(request, success_message)

        return redirect("core:memo_data_entry")

    except Exception as e:
        import traceback

        traceback.print_exc()
        messages.error(request, f"Error saving memo: {str(e)}")
        return redirect("core:memo_data_entry")


# Updated retrieval function for your redesigned models
@login_required
def getInvoiceMemoByID(request, pk):
    """Get memo data - REDESIGNED MODEL VERSION"""
    try:
        memo = get_object_or_404(InvoiceMemo, pk=pk)
        details = memo.month_details.all().order_by("month_sequence")

        if details.count() == 3:
            outstanding_detail = details[0]
            previous_detail = details[1]
            current_detail = details[2]

            memo_data = {
                "id": memo.id,
                "memo_code": memo.memo_code,
                "memo_date": memo.memo_date.strftime("%Y-%m-%d"),
                "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                "child_admission": memo.child.admission_number,
                "year": memo.memo_year,
                "status": memo.status,
                # Clean 3-month structure with DIRECT FIELD ACCESS
                "outstanding_month": {
                    "name": outstanding_detail.month_name,
                    "year": outstanding_detail.actual_year,
                    "gross_charges": float(outstanding_detail.gross_charges),
                    "payments": float(outstanding_detail.payments_received),
                    "balance": float(outstanding_detail.net_balance),
                },
                "previous_month": {
                    "name": previous_detail.month_name,
                    "year": previous_detail.actual_year,
                    "package_fee": float(previous_detail.package_fee),
                    "extra_hours": float(
                        previous_detail.extra_hours_charge
                    ),  # ✅ DIRECT ACCESS
                    "holiday_charges": float(
                        previous_detail.holiday_charges
                    ),  # ✅ DIRECT ACCESS
                    "discount": float(previous_detail.discount_applied),
                    "gross_charges": float(previous_detail.gross_charges),
                    "payments": float(previous_detail.payments_received),
                    "balance": float(previous_detail.net_balance),
                    "package_name": previous_detail.package_name,
                },
                "current_month": {
                    "name": current_detail.month_name,
                    "year": current_detail.actual_year,
                    "package_fee": float(current_detail.package_fee),
                    "extra_hours": float(
                        current_detail.extra_hours_charge
                    ),  # ✅ DIRECT ACCESS
                    "holiday_charges": float(
                        current_detail.holiday_charges
                    ),  # ✅ DIRECT ACCESS
                    "discount": float(current_detail.discount_applied),
                    "gross_charges": float(current_detail.gross_charges),
                    "payments": float(current_detail.payments_received),
                    "balance": float(current_detail.net_balance),
                    "package_name": current_detail.package_name,
                },
                # Summary totals from model
                "totals": {
                    "gross_total": float(memo.gross_total),
                    "total_payments": float(memo.total_payments),
                    "net_amount_due": float(memo.net_amount_due),
                    "total_outstanding": float(memo.total_outstanding),
                    "total_previous_month": float(memo.total_previous_month),
                    "total_current_month": float(memo.total_current_month),
                },
                "is_redesigned_format": True,
            }

        return JsonResponse(memo_data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def saveMemoDataDraft(request):
    """Save memo data as draft (auto-save functionality)"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid method"}, status=400)

        # Save draft to session or temporary table
        draft_data = {
            "child": request.POST.get("child"),
            "month": request.POST.get("month"),
            "year": request.POST.get("year"),
            "outstanding_amount": request.POST.get("outstanding_amount"),
            "payment_settled": request.POST.get("payment_settled"),
            "package_fee": request.POST.get("package_fee"),
            "extra_hours": request.POST.get("extra_hours"),
            "holiday_charges": request.POST.get("holiday_charges"),
            "discount_applied": request.POST.get("discount_applied"),
            "advance_payment": request.POST.get("advance_payment"),
            "current_payment": request.POST.get("current_payment"),
            "receipt_number": request.POST.get("receipt_number"),
            "timestamp": datetime.now().isoformat(),
        }

        # Save to session
        request.session["memo_draft"] = draft_data
        request.session.modified = True

        return JsonResponse({"success": True, "message": "Draft saved"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def calculate_month_attendance_summary(child, month, year):
    """Calculate attendance summary for a specific month"""
    import calendar
    from collections import defaultdict
    from datetime import datetime

    try:
        # Get date range for the month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # Get attendance logs for the month
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day)
        )

        # Group by date and count complete attendances (in and out)
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        days_attended = sum(1 for logs in logs_by_date.values() if len(logs) >= 2)

        # Get expected days from package
        package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        expected_days = 22  # default
        if package_mapping:
            if package_mapping.normal_package:
                expected_days = package_mapping.normal_package.no_days_months or 22
            elif package_mapping.holiday_package:
                expected_days = package_mapping.holiday_package.no_days_months or 22
            elif package_mapping.flex_package:
                expected_days = package_mapping.flex_package.no_days_months or 22

        attendance_percentage = (
            round((days_attended / expected_days * 100), 1) if expected_days > 0 else 0
        )

        return {
            "days_attended": days_attended,
            "expected_days": expected_days,
            "attendance_percentage": attendance_percentage,
        }

    except Exception:
        return {
            "days_attended": 0,
            "expected_days": 22,
            "attendance_percentage": 0,
        }


@login_required
def getDetailedChargesBreakdown(request):
    """Get detailed breakdown of extra hours and holiday charges for a specific month - CORRECTED VERSION"""
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing parameters"}, status=400)

        child = Child.objects.get(id=child_id)

        # Get date range for the month
        first_day = datetime(int(year), int(month), 1).date()
        last_day = datetime(
            int(year), int(month), calendar.monthrange(int(year), int(month))[1]
        ).date()

        # Get package mapping for this period
        package_mapping = (
            ChildPackageMapping.objects.filter(
                child=child,
                is_active=True,
                effective_from__lte=last_day,
            )
            .filter(Q(effective_to__gte=first_day) | Q(effective_to__isnull=True))
            .first()
        )

        if not package_mapping:
            return JsonResponse(
                {"error": "No package mapping found for this period"}, status=404
            )

        # Get attendance logs for the month
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day)
        ).order_by("date_logged", "time_logged")

        # Get holidays in this month
        holidays = Holiday.objects.filter(
            start_date__lte=last_day, end_date__gte=first_day, is_active=True
        ).values_list("start_date", flat=True)
        holiday_dates = set(holidays)

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        # Determine package details
        package = None
        package_end_time = None
        package_type = None

        if package_mapping.normal_package:
            package = package_mapping.normal_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.holiday_package:
            package = package_mapping.holiday_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.flex_package:
            package = package_mapping.flex_package
            package_end_time = time(17, 30)  # Default for flex
            package_type = package.package_type

        if not package_end_time or not package_type:
            return JsonResponse(
                {"error": "Could not determine package details"}, status=400
            )

        # Calculate detailed charges
        extra_hours_breakdown = []
        holiday_charges_breakdown = []
        total_extra_charges = Decimal("0.00")
        total_holiday_charges = Decimal("0.00")

        for log_date, logs in logs_by_date.items():
            if len(logs) < 2:  # Need both in and out
                continue

            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))
            time_in = logs_sorted[0].time_logged
            time_out = logs_sorted[-1].time_logged

            if not time_out or not package_end_time:
                continue

            is_holiday = log_date in holiday_dates

            # ===== CORRECTED CUMULATIVE EXTRA HOURS CALCULATION =====
            if time_out > package_end_time:
                package_end_datetime = datetime.combine(log_date, package_end_time)
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                day_extra_charges = Decimal("0.00")
                applied_rates = []

                # === CUMULATIVE CHARGING LOGIC ===
                # 1. Handle charges BEFORE 5:30 PM (if package ends before 5:30)
                cutoff_530 = time(17, 30)

                if package_end_time < cutoff_530 and time_out > package_end_time:
                    # Calculate time between package end and 5:30 PM (or actual out time if earlier)
                    end_time_for_before_530 = min(time_out, cutoff_530)

                    if end_time_for_before_530 > package_end_time:
                        before_530_datetime = datetime.combine(
                            log_date, end_time_for_before_530
                        )
                        hours_before_530 = (
                            before_530_datetime - package_end_datetime
                        ).total_seconds() / 3600

                        # Calculate number of complete + partial hours
                        hour_count = int(hours_before_530)
                        if hours_before_530 % 1 > 0:  # Has partial hour
                            hour_count += 1

                        # Add charges for each hour before 5:30 PM
                        for hour_num in range(1, min(hour_count + 1, 7)):  # Max 6 hours
                            rate_obj = (
                                ExtraHoursUpTo530.objects.filter(
                                    hour_number=hour_num,
                                    effective_from__lte=log_date,
                                    is_active=True,
                                )
                                .filter(
                                    Q(effective_to__gte=log_date)
                                    | Q(effective_to__isnull=True)
                                )
                                .first()
                            )

                            if rate_obj:
                                day_extra_charges += rate_obj.extra_rate
                                applied_rates.append(
                                    {
                                        "time_slot": f"Hour {hour_num} (before 5:30 PM)",
                                        "rate": float(rate_obj.extra_rate),
                                        "type": "Before 5:30 PM",
                                    }
                                )

                # 2. Handle charges AFTER 5:30 PM (cumulative slot-by-slot)
                if time_out > cutoff_530:
                    # Determine start time for after-5:30 charging
                    start_time_after_530 = max(package_end_time, cutoff_530)

                    # Get ALL time slots from start_time to actual out_time
                    # This is the key fix - get ALL applicable slots, not just the final one
                    applicable_slots = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__gte=start_time_after_530,  # Slot starts after our start time
                            from_time__lt=time_out,  # Slot starts before child leaves
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .order_by("from_time")
                    )  # Order by time to ensure sequential processing

                    # Add charges for ALL applicable slots (CUMULATIVE)
                    for slot in applicable_slots:
                        day_extra_charges += slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{slot.from_time.strftime('%H:%M')} - {slot.to_time.strftime('%H:%M')}",
                                "rate": float(slot.extra_rate),
                                "type": "After 5:30 PM",
                            }
                        )

                    # Also check if child's out_time falls within any slot that starts before out_time
                    # but ends after out_time (partial slot charging)
                    partial_slot = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__lt=time_out,  # Slot starts before child leaves
                            to_time__gt=time_out,  # Slot ends after child leaves
                            from_time__gte=start_time_after_530,  # Slot is relevant to our time range
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .first()
                    )

                    # Only add partial slot if not already included in applicable_slots
                    if partial_slot and partial_slot not in [
                        slot for slot in applicable_slots
                    ]:
                        day_extra_charges += partial_slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{partial_slot.from_time.strftime('%H:%M')} - {partial_slot.to_time.strftime('%H:%M')} (partial)",
                                "rate": float(partial_slot.extra_rate),
                                "type": "After 5:30 PM (Partial)",
                            }
                        )

                if day_extra_charges > 0:
                    # Convert decimal hours to hours and minutes format
                    total_minutes = int(extra_hours * 60)
                    hours_part = total_minutes // 60
                    minutes_part = total_minutes % 60

                    # Format as "X hrs Y mins" or just "Y mins" if less than 1 hour
                    if hours_part > 0:
                        extra_hours_display = f"{hours_part} hr{'s' if hours_part != 1 else ''} {minutes_part} min{'s' if minutes_part != 1 else ''}"
                    else:
                        extra_hours_display = (
                            f"{minutes_part} min{'s' if minutes_part != 1 else ''}"
                        )

                    extra_hours_breakdown.append(
                        {
                            "date": log_date.strftime("%Y-%m-%d"),
                            "day_name": log_date.strftime("%A"),
                            "time_in": time_in.strftime("%H:%M") if time_in else "N/A",
                            "time_out": time_out.strftime("%H:%M"),
                            "package_end_time": package_end_time.strftime("%H:%M"),
                            "extra_hours": round(
                                extra_hours, 2
                            ),  # Keep decimal for calculations
                            "extra_hours_display": extra_hours_display,  # Human-readable format
                            "charges": float(day_extra_charges),
                            "applied_rates": applied_rates,
                            "is_holiday": is_holiday,
                        }
                    )
                    total_extra_charges += day_extra_charges

            # Calculate holiday charges (unchanged)
            if is_holiday and package_mapping.holiday_package:
                expected_days = package_mapping.holiday_package.no_days_months or 22
                daily_holiday_rate = (
                    package_mapping.holiday_package.package_total
                    / Decimal(expected_days)
                )

                holiday_charges_breakdown.append(
                    {
                        "date": log_date.strftime("%Y-%m-%d"),
                        "day_name": log_date.strftime("%A"),
                        "holiday_package": package_mapping.holiday_package.package_name,
                        "daily_rate": float(daily_holiday_rate),
                        "charges": float(daily_holiday_rate),
                    }
                )
                total_holiday_charges += daily_holiday_rate

        # Calculate total extra hours in hours and minutes format
        total_extra_hours_decimal = sum(
            item["extra_hours"] for item in extra_hours_breakdown
        )
        total_extra_minutes = int(total_extra_hours_decimal * 60)
        total_hours_part = total_extra_minutes // 60
        total_minutes_part = total_extra_minutes % 60

        if total_hours_part > 0:
            total_extra_hours_display = f"{total_hours_part} hr{'s' if total_hours_part != 1 else ''} {total_minutes_part} min{'s' if total_minutes_part != 1 else ''}"
        else:
            total_extra_hours_display = (
                f"{total_minutes_part} min{'s' if total_minutes_part != 1 else ''}"
            )

        return JsonResponse(
            {
                "success": True,
                "month_name": calendar.month_name[int(month)],
                "year": year,
                "package_info": {
                    "name": package.package_name,
                    "end_time": package_end_time.strftime("%H:%M"),
                    "type": package_type.package_type_name,
                },
                "extra_hours": {
                    "breakdown": extra_hours_breakdown,
                    "total": float(total_extra_charges),
                    "total_hours_decimal": round(total_extra_hours_decimal, 2),
                    "total_hours_display": total_extra_hours_display,
                    "days_count": len(extra_hours_breakdown),
                },
                "holiday_charges": {
                    "breakdown": holiday_charges_breakdown,
                    "total": float(total_holiday_charges),
                    "days_count": len(holiday_charges_breakdown),
                },
                "summary": {
                    "total_extra_charges": float(total_extra_charges),
                    "total_holiday_charges": float(total_holiday_charges),
                    "combined_total": float(
                        total_extra_charges + total_holiday_charges
                    ),
                    "total_extra_hours_display": total_extra_hours_display,
                },
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getChildComprehensiveView(request):
    """Display comprehensive child view page"""
    try:
        # Get all enrolled children for dropdown
        children = Child.objects.filter(
            is_active=True, is_enrolled=True, enrollement_approved=True
        ).order_by("admission_number")

        context = {
            "children": children,
            "UserName": request.user.username,
        }

        return render(request, "../templates/childdet.html", context)

    except Exception as e:
        messages.error(request, f"Error loading page: {str(e)}")
        return redirect("core:view_child")


@login_required
def getChildComprehensiveDataJS(request):
    """Get comprehensive child data as JSON"""
    try:
        child_id = request.GET.get("child_id")
        admission_number = request.GET.get("admission_number")

        # Find child by ID or admission number
        if child_id:
            child = Child.objects.get(id=child_id, is_active=True)
        elif admission_number:
            child = Child.objects.get(admission_number=admission_number, is_active=True)
        else:
            return JsonResponse(
                {"error": "Child ID or admission number required"}, status=400
            )

        # Get enrollment information
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        # Get current package mapping
        current_package_mapping = ChildPackageMapping.objects.filter(
            child=child, is_active=True
        ).first()

        # Get package history
        package_history = ChildPackageMapping.objects.filter(child=child).order_by(
            "-effective_from"
        )[:10]

        # Get current month attendance from 1st to today (weekdays only)
        import calendar
        from collections import defaultdict
        from datetime import date, datetime, time, timedelta

        current_date = datetime.now().date()
        current_month = current_date.month
        current_year = current_date.year
        first_day_of_month = date(current_year, current_month, 1)

        # Get all attendance logs for current month
        current_month_attendance_logs = AttendanceLog.objects.filter(
            child=child,
            date_logged__gte=first_day_of_month,
            date_logged__lte=current_date,
        ).order_by("date_logged", "time_logged")

        # Group attendance by date
        attendance_by_date = defaultdict(list)
        for log in current_month_attendance_logs:
            attendance_by_date[log.date_logged].append(log)

        # Create complete attendance record for each weekday of the month
        complete_month_attendance = []
        current_day = first_day_of_month

        while current_day <= current_date:
            # Only include weekdays (Monday=0 to Friday=4)
            if current_day.weekday() < 5:
                logs_for_day = attendance_by_date.get(current_day, [])

                if logs_for_day:
                    # Sort logs by time for this date
                    sorted_logs = sorted(
                        logs_for_day, key=lambda x: x.time_logged or time(0, 0)
                    )

                    first_log = sorted_logs[0]  # IN time
                    last_log = (
                        sorted_logs[-1] if len(sorted_logs) > 1 else None
                    )  # OUT time

                    attendance_record = {
                        "date": current_day.strftime("%Y-%m-%d"),
                        "day_name": current_day.strftime("%A"),
                        "in_time": first_log.time_logged.strftime("%H:%M")
                        if first_log.time_logged
                        else None,
                        "out_time": last_log.time_logged.strftime("%H:%M")
                        if last_log and last_log.time_logged
                        else None,
                        "complete_attendance": len(sorted_logs) >= 2,
                        "total_logs": len(sorted_logs),
                        "is_present": True,
                    }
                else:
                    # No attendance for this day
                    attendance_record = {
                        "date": current_day.strftime("%Y-%m-%d"),
                        "day_name": current_day.strftime("%A"),
                        "in_time": None,
                        "out_time": None,
                        "complete_attendance": False,
                        "total_logs": 0,
                        "is_present": False,
                    }

                complete_month_attendance.append(attendance_record)

            current_day += timedelta(days=1)

        # Reverse to show most recent first
        complete_month_attendance.reverse()

        # Calculate attendance stats
        total_weekdays = len(complete_month_attendance)
        days_attended = len(
            [
                record
                for record in complete_month_attendance
                if record["complete_attendance"]
            ]
        )
        attendance_percentage = (
            (days_attended / total_weekdays * 100) if total_weekdays > 0 else 0
        )

        # Get recent invoice memos (last 6 months)
        recent_invoices = InvoiceMemo.objects.filter(
            child=child, is_active=True
        ).order_by("-year", "-month")[:6]

        # Get outstanding payments
        outstanding_invoices = InvoiceMemo.objects.filter(
            child=child, month_net_balance__gt=0, is_active=True
        ).order_by("year", "month")

        # Get pending requests
        pending_package_changes = PackageChangerequest.objects.filter(
            child=child, status="Pending Approval", is_active=True
        )

        pending_center_changes = CenterChangerequest.objects.filter(
            child=child, status="Pending Approval", is_active=True
        )

        # Build comprehensive response
        response_data = {
            # Basic child information
            "child_info": {
                "id": child.id,
                "admission_number": child.admission_number,
                "full_name": f"{child.child_first_name} {child.child_last_name}",
                "first_name": child.child_first_name,
                "last_name": child.child_last_name,
                "date_of_birth": child.date_of_birth.strftime("%Y-%m-%d")
                if child.date_of_birth
                else None,
                "admission_date": child.admission_date.strftime("%Y-%m-%d")
                if child.admission_date
                else None,
                "fathers_name": child.fathers_name,
                "mothers_name": child.mothers_name,
                "fathers_contact": child.fathers_contact_number,
                "mothers_contact": child.mothers_contact_number,
                "fathers_whatsapp": child.fathers_whatsapp_number,
                "mothers_whatsapp": child.mothers_whatsapp_number,
                "address": f"{child.address_line1 or ''}, {child.address_line2 or ''}, {child.address_line3 or ''}".strip(
                    ", "
                ),
                "email": child.email_address,
                "is_polymath_student": child.is_polymath_student,
                "child_image": child.child_image.url if child.child_image else None,
                "qr_code": child.qr_code,
            },
            # Enrollment information
            "enrollment_info": {
                "enrollment_code": enrollment.enrollment_code if enrollment else None,
                "enrollment_date": enrollment.enrollment_date.strftime("%Y-%m-%d")
                if enrollment
                else None,
                "branch_name": enrollment.branch.branch_name if enrollment else None,
                "center_name": enrollment.center.daycare_name if enrollment else None,
                "status": enrollment.status if enrollment else None,
                "receipt_number": enrollment.recipt_number if enrollment else None,
            }
            if enrollment
            else None,
            # Current package information
            "current_package": {
                "normal_package": {
                    "name": current_package_mapping.normal_package.package_name,
                    "code": current_package_mapping.normal_package.package_code,
                    "from_time": current_package_mapping.normal_package.from_time.strftime(
                        "%H:%M"
                    ),
                    "to_time": current_package_mapping.normal_package.to_time.strftime(
                        "%H:%M"
                    ),
                    "total": float(
                        current_package_mapping.normal_package.package_total
                    ),
                }
                if current_package_mapping and current_package_mapping.normal_package
                else None,
                "holiday_package": {
                    "name": current_package_mapping.holiday_package.package_name,
                    "code": current_package_mapping.holiday_package.package_code,
                    "total": float(
                        current_package_mapping.holiday_package.package_total
                    ),
                }
                if current_package_mapping and current_package_mapping.holiday_package
                else None,
                "flex_package": {
                    "name": current_package_mapping.flex_package.package_name,
                    "code": current_package_mapping.flex_package.package_code,
                    "hours": current_package_mapping.flex_package.no_hours,
                    "total": float(current_package_mapping.flex_package.package_total),
                }
                if current_package_mapping and current_package_mapping.flex_package
                else None,
                "discount": {
                    "name": current_package_mapping.discount.discount_name,
                    "rate": float(current_package_mapping.discount.discount_rate),
                }
                if current_package_mapping and current_package_mapping.discount
                else None,
                "effective_from": current_package_mapping.effective_from.strftime(
                    "%Y-%m-%d"
                )
                if current_package_mapping
                else None,
                "effective_to": current_package_mapping.effective_to.strftime(
                    "%Y-%m-%d"
                )
                if current_package_mapping and current_package_mapping.effective_to
                else None,
            }
            if current_package_mapping
            else None,
            # Attendance statistics
            "attendance_stats": {
                "current_month": {
                    "days_attended": days_attended,
                    "expected_days": total_weekdays,
                    "attendance_percentage": round(attendance_percentage, 1),
                    "month_name": calendar.month_name[current_month],
                    "year": current_year,
                    "total_weekdays_so_far": total_weekdays,
                },
                "current_month_attendance": complete_month_attendance,
            },
            # Financial information
            "financial_info": {
                "outstanding_amount": float(
                    sum(invoice.month_net_balance for invoice in outstanding_invoices)
                ),
                "outstanding_invoices": [
                    {
                        "memo_code": invoice.memo_code,
                        "month_name": calendar.month_name[invoice.month],
                        "year": invoice.year,
                        "amount": float(invoice.month_total_charge),
                        "payments": float(invoice.total_payments_received),
                        "balance": float(invoice.month_net_balance),
                        "status": invoice.status,
                    }
                    for invoice in outstanding_invoices
                ],
                "recent_invoices": [
                    {
                        "memo_code": invoice.memo_code,
                        "month_name": calendar.month_name[invoice.month],
                        "year": invoice.year,
                        "amount": float(invoice.month_total_charge),
                        "payments": float(invoice.total_payments_received),
                        "balance": float(invoice.month_net_balance),
                        "status": invoice.status,
                        "created_date": invoice.date_created.strftime("%Y-%m-%d")
                        if invoice.date_created
                        else None,
                    }
                    for invoice in recent_invoices
                ],
            },
            # Package history
            "package_history": [
                {
                    "normal_package": mapping.normal_package.package_name
                    if mapping.normal_package
                    else None,
                    "holiday_package": mapping.holiday_package.package_name
                    if mapping.holiday_package
                    else None,
                    "flex_package": mapping.flex_package.package_name
                    if mapping.flex_package
                    else None,
                    "effective_from": mapping.effective_from.strftime("%Y-%m-%d")
                    if mapping.effective_from
                    else None,
                    "effective_to": mapping.effective_to.strftime("%Y-%m-%d")
                    if mapping.effective_to
                    else "Current",
                    "is_active": mapping.is_active,
                }
                for mapping in package_history
            ],
            # Pending requests
            "pending_requests": {
                "package_changes": [
                    {
                        "id": req.id,
                        "old_package": req.old_fixed_package.package_name
                        if req.old_fixed_package
                        else req.old_flexed_package.package_name
                        if req.old_flexed_package
                        else None,
                        "new_package": req.new_fixed_package.package_name
                        if req.new_fixed_package
                        else req.new_flexed_package.package_name
                        if req.new_flexed_package
                        else None,
                        "reason": req.reason_for_request,
                        "effective_date": req.effective_date.strftime("%Y-%m-%d"),
                        "requested_date": req.date_requested.strftime("%Y-%m-%d"),
                    }
                    for req in pending_package_changes
                ],
                "center_changes": [
                    {
                        "id": req.id,
                        "old_center": req.old_center.daycare_name
                        if req.old_center
                        else None,
                        "new_center": req.new_center.daycare_name
                        if req.new_center
                        else None,
                        "old_branch": req.old_branch.branch_name
                        if req.old_branch
                        else None,
                        "new_branch": req.new_branch.branch_name
                        if req.new_branch
                        else None,
                        "reason": req.reason_for_request,
                        "effective_date": req.effective_date.strftime("%Y-%m-%d"),
                        "requested_date": req.date_requested.strftime("%Y-%m-%d"),
                    }
                    for req in pending_center_changes
                ],
            },
        }

        return JsonResponse(response_data)

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


########################### invoice


@login_required
def getAllInvoiceMemos(request):
    """Get all invoice memos for listing"""
    try:
        # Get filter parameters
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")
        status = request.GET.get("status")

        # Build query
        memos = InvoiceMemo.objects.filter(is_active=True)

        if child_id:
            memos = memos.filter(child_id=child_id)
        if month:
            memos = memos.filter(memo_month=int(month))
        if year:
            memos = memos.filter(memo_year=int(year))
        if status:
            memos = memos.filter(status=status)

        # Order by most recent first
        memos = memos.order_by("-memo_year", "-memo_month", "-date_created")

        # Prepare data
        memo_list = []
        for memo in memos:
            memo_list.append(
                {
                    "id": memo.id,
                    "memo_code": memo.memo_code,
                    "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                    "child_admission": memo.child.admission_number,
                    "month_name": calendar.month_name[memo.memo_month],
                    "memo_month": memo.memo_month,
                    "memo_year": memo.memo_year,
                    "gross_total": float(memo.gross_total),
                    "total_payments": float(memo.total_payments),
                    "net_amount_due": float(memo.net_amount_due),
                    "status": memo.status,
                    "date_created": memo.date_created.strftime("%Y-%m-%d %H:%M")
                    if memo.date_created
                    else "",
                    "user_created": memo.user_created,
                }
            )

        return JsonResponse(memo_list, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def loadInvoiceMemo(request):
    """Display memo load form - Uses your existing template"""
    try:
        form = LoadInvoiceMemoForm()
        context = {
            "form": form,
            "UserName": request.user.username,
        }
        return render(request, "../templates/invoice.html", context)
    except Exception as e:
        messages.error(request, f"Error loading memo form: {str(e)}")
        return redirect("core:memo_data_entry")


@login_required
def searchInvoiceMemo(request):
    """Search for existing invoice memo"""
    try:
        if request.method != "GET":
            return JsonResponse({"error": "GET method required"}, status=400)

        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = get_object_or_404(Child, id=child_id)
        month_int = int(month)
        year_int = int(year)
        month_name = calendar.month_name[month_int]

        memo = InvoiceMemo.objects.filter(
            child=child, memo_month=month_int, memo_year=year_int, is_active=True
        ).first()

        if memo:
            memo_data = {
                "id": memo.id,
                "memo_code": memo.memo_code,
                "child_id": child.id,
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "child_admission": child.admission_number,
                "memo_month": memo.memo_month,
                "memo_year": memo.memo_year,
                "total_outstanding": float(memo.total_outstanding),
                "total_previous_month": float(memo.total_previous_month),
                "total_current_month": float(memo.total_current_month),
                "gross_total": float(memo.gross_total),
                "total_payments": float(memo.total_payments),
                "net_amount_due": float(memo.net_amount_due),
                "status": memo.status,
                "date_created": memo.date_created.isoformat()
                if memo.date_created
                else None,
                "notes": memo.notes or "",
            }

            return JsonResponse(
                {
                    "success": True,
                    "memo": memo_data,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "month_name": month_name,
                    "year": year_int,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": True,
                    "memo": None,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "month_name": month_name,
                    "year": year_int,
                }
            )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def previewInvoiceMemo(request, memo_id):
    """Preview invoice memo with CORRECTED format to match screenshot"""
    try:
        memo = get_object_or_404(InvoiceMemo, pk=memo_id)
        memo_data = prepare_memo_display_data_fixed(memo)  # Use fixed function
        preview_html = generate_memo_preview_html_with_two_columns(memo_data)
        return HttpResponse(preview_html)
    except Exception as e:
        messages.error(request, f"Error loading memo: {str(e)}")
        return redirect("core:load_invoice_memo")

def generate_memo_pdf_fixed(memo_data):
    """Generate PDF with detailed breakdown matching the sample PDF format"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        # Define consistent styles
        header_style = ParagraphStyle(
            "CustomHeader",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        address_style = ParagraphStyle(
            "AddressStyle",
            parent=styles["Normal"],
            fontSize=11,
            alignment=1,
            spaceAfter=12,
            fontName="Helvetica",
        )

        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontSize=11,
            fontName="Helvetica",
        )

        story = []

        # Header
        story.append(Paragraph("POLYMATH KIDS DIVISION - MEMO", header_style))
        story.append(
            Paragraph(
                "No 452/3 High Level Road, Nawinna, Maharagama<br/>PV 63200 | Phone 0112802554",
                address_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        story.append(Spacer(1, 12))

        # Child info
        child_info_data = [
            [
                f"Name: {memo_data.get('child_name', 'N/A')}",
                f"Child ID: {memo_data.get('child_admission', 'N/A')}",
            ],
            [
                f"Package: {memo_data.get('package_name', 'N/A')}",
                f"Due Date: {memo_data.get('due_date', 'N/A')}",
            ],
        ]

        child_info_table = Table(child_info_data, colWidths=[100 * mm, 70 * mm])
        child_info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(child_info_table)
        story.append(Spacer(1, 15))

        # Main table data
        table_data = [["Description", "Amount (Rs.)"]]

        # Outstanding section
        outstanding = memo_data.get("outstanding_month", {})
        table_data.append(
            [
                f"{outstanding.get('name', 'Outstanding')} {outstanding.get('year', 2025)}",
                "",
            ]
        )
        
        # Outstanding description - simple for now
        outstanding_desc = f"Outstanding from {outstanding.get('name', 'Outstanding')}"
        table_data.append([outstanding_desc, f"{outstanding.get('balance', 0):,.2f}"])

        # Previous month section
        previous = memo_data.get("previous_month", {})
        table_data.append(
            [
                f"{previous.get('name', 'Previous')} {previous.get('year', 2025)} ",
                "",
            ]
        )

        # Day care monthly fee
        package_desc = previous.get(
            "package_description",
            f"Day Care Monthly fee - {previous.get('name', 'Previous')} ({previous.get('days_attended', 0)}/{previous.get('expected_days', 22)} days attended)",
        )
        table_data.append([package_desc, f"{previous.get('package_fee', 0):,.2f}"])

        # Extra hours with detailed breakdown - MATCHING PDF FORMAT
        if previous.get("extra_charges", 0) > 0:
            extra_description = previous.get("extra_hours_description", "Extra Hours Charges")
            extra_detail = previous.get("extra_hours_detail", "")
            
            # Create the full description with breakdown
            full_extra_desc = extra_description
            if extra_detail:
                # Format each line of the breakdown
                detail_lines = extra_detail.split('\n')
                formatted_lines = []
                for line in detail_lines:
                    if line.strip():
                        formatted_lines.append(f"    {line.strip()}")  # Indent for sub-items
                
                if formatted_lines:
                    full_extra_desc = f"{extra_description}\n" + "\n".join(formatted_lines)
            
            table_data.append([full_extra_desc, f"{previous.get('extra_charges', 0):,.2f}"])

        # Holiday charges if any
        if previous.get("holiday_charges", 0) > 0:
            holiday_desc = previous.get("holiday_description", "Holiday Attendance Charges")
            table_data.append([holiday_desc, f"{previous.get('holiday_charges', 0):,.2f}"])

        # Previous month total
        table_data.append(
            [
                f"Total for {previous.get('name', 'Previous')} {previous.get('year', 2025)}",
                f"{previous.get('month_total', 0):,.2f}",
            ]
        )

        # Current month section
        current = memo_data.get("current_month", {})
        table_data.append(
            [
                f"{current.get('name', 'Current')} {current.get('year', 2025)}",
                "",
            ]
        )

        current_desc = current.get(
            "package_description",
            f"Day Care Monthly fee - {current.get('name', 'Current')} {current.get('year', 2025)} (Full Package)",
        )
        current_desc += f"\n{current.get('advance_note', 'Advance charge for upcoming month')}"
        table_data.append([current_desc, f"{current.get('package_fee', 0):,.2f}"])

        # Final total
        totals = memo_data.get("totals", {})
        table_data.append(
            [
                "TOTAL AMOUNT TO PAY",
                f"Rs. {totals.get('grand_total', 0):,.2f}",
            ]
        )

        # Create and style table
        main_table = Table(table_data, colWidths=[120 * mm, 35 * mm])

        # Calculate row indices for styling (accounting for dynamic rows)
        total_rows = len(table_data)
        outstanding_header_row = 1
        outstanding_data_row = 2
        calculated_header_row = 3
        package_fee_row = 4
        
        # Determine row indices based on what's present
        current_row = 5
        extra_hours_row = None
        holiday_charges_row = None
        previous_total_row = None
        advance_header_row = None
        advance_package_row = None
        final_total_row = total_rows - 1

        if previous.get("extra_charges", 0) > 0:
            extra_hours_row = current_row
            current_row += 1

        if previous.get("holiday_charges", 0) > 0:
            holiday_charges_row = current_row
            current_row += 1

        previous_total_row = current_row
        current_row += 1
        advance_header_row = current_row
        current_row += 1
        advance_package_row = current_row

        table_styles = [
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            # Section headers
            ("BACKGROUND", (0, outstanding_header_row), (-1, outstanding_header_row), colors.Color(1, 0.9, 0.9)),
            ("FONTNAME", (0, outstanding_header_row), (-1, outstanding_header_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, calculated_header_row), (-1, calculated_header_row), colors.Color(0.9, 0.95, 1)),
            ("FONTNAME", (0, calculated_header_row), (-1, calculated_header_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, advance_header_row), (-1, advance_header_row), colors.Color(0.9, 1, 1)),
            ("FONTNAME", (0, advance_header_row), (-1, advance_header_row), "Helvetica-Bold"),
            # Total rows
            ("FONTNAME", (0, previous_total_row), (-1, previous_total_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, final_total_row), (-1, final_total_row), colors.Color(1, 0.95, 0.8)),
            ("FONTNAME", (0, final_total_row), (-1, final_total_row), "Helvetica-Bold"),
        ]

        # Special formatting for extra hours row if it exists
        if extra_hours_row is not None:
            table_styles.extend([
                ("FONTSIZE", (0, extra_hours_row), (-1, extra_hours_row), 9),
                ("FONTNAME", (0, extra_hours_row), (0, extra_hours_row), "Helvetica"),
            ])

        main_table.setStyle(TableStyle(table_styles))
        story.append(main_table)
        story.append(Spacer(1, 20))

        # Footer note
        story.append(
            Paragraph(
                f"<b>Please note that,</b> Only the payments made before the invoice date is indicated. "
                f"If there is any outstanding amount please settle on or before <strong> {memo_data.get('due_date', 'N/A')}</strong>. "
                "Ignore this message if you have already settled that outstanding.",
                normal_style,
            )
        )
        story.append(Spacer(1, 12))
        story.append(
            Paragraph("<b>Thank you,</b><br/><b>The Management,</b>", normal_style)
        )
        story.append(Spacer(1, 12))

        # Account details
        account_details = [
            ["Account Details"],
            ["Account Name - Polymath College (PVT) Ltd"],
            ["Bank - Peoples Bank"],
            ["Branch - Gangodawila"],
            ["Account Number - 097100130026495"],
            ["Whatsapp - 0705565858"],
        ]

        account_table = Table(account_details, colWidths=[170 * mm])
        account_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(account_table)

        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Create a simple fallback PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"Error generating memo PDF: {str(e)}", styles["Normal"])]
        doc.build(story)
        buffer.seek(0)
        return buffer
    

@login_required
def downloadInvoiceMemoPDF(request):
    """Generate PDF with FIXED calculations and detailed breakdown"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        data = json.loads(request.body)
        memo_code = data.get("memo_code")

        if not memo_code:
            return JsonResponse({"error": "Memo code required"}, status=400)

        memo = InvoiceMemo.objects.filter(memo_code=memo_code, is_active=True).first()
        if not memo:
            return JsonResponse({"error": "Memo not found"}, status=404)

        memo_data = prepare_memo_display_data_fixed(memo)
        pdf_buffer = generate_memo_pdf_with_two_column_breakdown(memo_data) 

        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        filename = f"Invoice_Memo_{memo_data['memo_code']}_{memo_data['child_admission']}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def prepare_memo_display_data(memo):
    """Prepare enhanced memo data with detailed breakdowns and payment information"""
    try:
        details = memo.month_details.all().order_by("month_sequence")

        # Get basic info
        base_data = {
            "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
            "child_admission": memo.child.admission_number,
            "child_id": memo.child.id,
            "memo_code": memo.memo_code,
            "memo_date": memo.memo_date.strftime("%d/%m/%Y"),
            "due_date": (memo.memo_date + timedelta(days=7)).strftime("%d/%m/%Y"),
            "status": memo.status,
        }

        if details.count() == 3:
            outstanding_detail = details[0]
            previous_detail = details[1]
            current_detail = details[2]

            # Extract detailed breakdowns from calculation_details
            def get_breakdown_data(detail):
                """Extract breakdown data from calculation_details JSON field"""
                calc_details = detail.calculation_details or {}

                # Extra hours breakdown
                extra_hours_breakdown = calc_details.get("extra_hours_breakdown", [])

                # Holiday charges breakdown
                holiday_charges_breakdown = calc_details.get(
                    "holiday_charges_breakdown", []
                )

                # If no stored breakdown but has charges, create summary
                if not extra_hours_breakdown and detail.extra_hours_charge > 0:
                    extra_hours_breakdown = [
                        {
                            "date": f"{detail.actual_year}-{detail.actual_month:02d}-15",
                            "time_out": "18:30",
                            "extra_hours_display": "Multiple instances",
                            "charges": float(detail.extra_hours_charge),
                            "type": "summary",
                        }
                    ]

                if not holiday_charges_breakdown and detail.holiday_charges > 0:
                    holiday_charges_breakdown = [
                        {
                            "date": f"{detail.actual_year}-{detail.actual_month:02d}-15",
                            "holiday_name": "Holiday Attendance",
                            "charges": float(detail.holiday_charges),
                            "type": "summary",
                        }
                    ]

                return extra_hours_breakdown, holiday_charges_breakdown

            # Get package name (priority: previous > current > default)
            package_name = "Normal Package"
            if previous_detail.package_name:
                package_name = previous_detail.package_name
            elif current_detail.package_name:
                package_name = current_detail.package_name

            # Extract payment information with calculation display
            def format_payments_with_calculation(detail):
                """Format payment information with clear calculation display"""
                payments = []
                calculation_display = ""

                if detail.payments_received > 0:
                    payment_receipts = detail.payment_receipts or []

                    if payment_receipts:
                        for payment in payment_receipts:
                            payments.append(
                                {
                                    "amount": payment.get("amount", 0),
                                    "receipt_number": payment.get(
                                        "receipt_number", "N/A"
                                    ),
                                    "date": payment.get("date", "N/A"),
                                    "type": payment.get("type", "payment"),
                                }
                            )
                    else:
                        # If no detailed receipts but has payment amount
                        payments.append(
                            {
                                "amount": float(detail.payments_received),
                                "receipt_number": "N/A",
                                "date": memo.memo_date.strftime("%Y-%m-%d"),
                                "type": "payment",
                            }
                        )

                # Create calculation display
                if detail.gross_charges > 0 and detail.payments_received > 0:
                    calculation_display = f"Rs.{detail.gross_charges:,.2f} - Rs.{detail.payments_received:,.2f} = Rs.{detail.net_balance:,.2f}"
                elif detail.gross_charges > 0:
                    calculation_display = (
                        f"Rs.{detail.gross_charges:,.2f} (No payments)"
                    )

                return payments, calculation_display

            # Get breakdowns for previous month
            prev_extra_breakdown, prev_holiday_breakdown = get_breakdown_data(
                previous_detail
            )

            # Get payment calculations for each month
            outstanding_payments, outstanding_calc = format_payments_with_calculation(
                outstanding_detail
            )
            previous_payments, previous_calc = format_payments_with_calculation(
                previous_detail
            )
            current_payments, current_calc = format_payments_with_calculation(
                current_detail
            )

            base_data.update(
                {
                    "package_name": package_name,
                    # Outstanding month with clear calculation
                    "outstanding_month": {
                        "name": outstanding_detail.month_name,
                        "year": outstanding_detail.actual_year,
                        "original_amount": float(outstanding_detail.gross_charges),
                        "payments": outstanding_payments,
                        "payments_total": float(outstanding_detail.payments_received),
                        "balance": float(outstanding_detail.net_balance),
                        "calculation_display": outstanding_calc,
                        "payment_summary": f"Rs.{outstanding_detail.payments_received:,.2f}"
                        if outstanding_detail.payments_received > 0
                        else "No payments",
                    },
                    # Previous month with detailed breakdown and calculation
                    "previous_month": {
                        "name": previous_detail.month_name,
                        "year": previous_detail.actual_year,
                        "package_fee": float(previous_detail.package_fee),
                        "extra_charges": float(previous_detail.extra_hours_charge),
                        "holiday_charges": float(previous_detail.holiday_charges),
                        "discount_applied": float(previous_detail.discount_applied),
                        "gross_charges": float(previous_detail.gross_charges),
                        "payments": previous_payments,
                        "payments_total": float(previous_detail.payments_received),
                        "net_balance": float(previous_detail.net_balance),
                        "calculation_display": previous_calc,
                        "days_attended": previous_detail.days_attended or 0,
                        "expected_days": previous_detail.expected_days or 22,
                        "attendance_percentage": float(
                            previous_detail.attendance_percentage or 0
                        ),
                        "is_half_charge": previous_detail.is_half_charge_applied,
                        # Detailed breakdowns
                        "extra_hours_breakdown": prev_extra_breakdown,
                        "holiday_charges_breakdown": prev_holiday_breakdown,
                        "payment_summary": f"Rs.{previous_detail.payments_received:,.2f}"
                        if previous_detail.payments_received > 0
                        else "No payments",
                    },
                    # Current month with calculation
                    "current_month": {
                        "name": current_detail.month_name,
                        "year": current_detail.actual_year,
                        "package_fee": float(current_detail.package_fee),
                        "extra_charges": float(current_detail.extra_hours_charge),
                        "holiday_charges": float(current_detail.holiday_charges),
                        "discount_applied": float(current_detail.discount_applied),
                        "gross_charges": float(current_detail.gross_charges),
                        "payments": current_payments,
                        "payments_total": float(current_detail.payments_received),
                        "net_balance": float(current_detail.net_balance),
                        "calculation_display": current_calc,
                        "expected_days": current_detail.expected_days or 22,
                        "payment_summary": f"Rs.{current_detail.payments_received:,.2f}"
                        if current_detail.payments_received > 0
                        else "No payments",
                    },
                    # Summary totals with final calculation
                    "totals": {
                        "gross_total": float(memo.gross_total),
                        "total_payments": float(memo.total_payments),
                        "net_amount_due": float(memo.net_amount_due),
                        "grand_total": float(memo.net_amount_due),
                        "final_calculation": f"Rs.{memo.gross_total:,.2f} - Rs.{memo.total_payments:,.2f} = Rs.{memo.net_amount_due:,.2f}"
                        if memo.total_payments > 0
                        else f"Rs.{memo.gross_total:,.2f} (No payments)",
                    },
                    # Summary breakdowns for display
                    "summary_breakdowns": {
                        "total_extra_hours_instances": len(prev_extra_breakdown),
                        "total_holiday_days": len(prev_holiday_breakdown),
                        "has_extra_charges": previous_detail.extra_hours_charge > 0,
                        "has_holiday_charges": previous_detail.holiday_charges > 0,
                        "has_payments": memo.total_payments > 0,
                    },
                }
            )

        else:
            # Fallback for incomplete data
            base_data.update(
                {
                    "package_name": "Normal Package",
                    "outstanding_month": {
                        "name": "Previous Outstanding",
                        "year": 2025,
                        "balance": 0.00,
                        "original_amount": 0.00,
                        "payments": [],
                        "payment_summary": "No payments",
                    },
                    "previous_month": {
                        "name": "Previous Month",
                        "year": 2025,
                        "package_fee": 0.00,
                        "extra_charges": 0.00,
                        "holiday_charges": 0.00,
                        "gross_charges": 0.00,
                        "payments": [],
                        "net_balance": 0.00,
                        "days_attended": 0,
                        "expected_days": 22,
                        "attendance_percentage": 0,
                        "extra_hours_breakdown": [],
                        "holiday_charges_breakdown": [],
                        "payment_summary": "No payments",
                    },
                    "current_month": {
                        "name": "Current Month",
                        "year": 2025,
                        "package_fee": 0.00,
                        "gross_charges": 0.00,
                        "payments": [],
                        "net_balance": 0.00,
                        "payment_summary": "No payments",
                    },
                    "totals": {
                        "gross_total": 0.00,
                        "total_payments": 0.00,
                        "net_amount_due": 0.00,
                        "grand_total": 0.00,
                    },
                    "summary_breakdowns": {
                        "total_extra_hours_instances": 0,
                        "total_holiday_days": 0,
                        "has_extra_charges": False,
                        "has_holiday_charges": False,
                        "has_payments": False,
                    },
                }
            )

        return base_data

    except Exception as e:
        print(f"Error in prepare_memo_display_data: {str(e)}")
        # Return minimal fallback data
        return {
            "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
            "child_admission": memo.child.admission_number,
            "child_id": memo.child.id,
            "memo_code": memo.memo_code,
            "package_name": "Normal Package",
            "memo_date": memo.memo_date.strftime("%d/%m/%Y"),
            "due_date": (memo.memo_date + timedelta(days=7)).strftime("%d/%m/%Y"),
            "error": str(e),
        }


def generate_memo_pdf(memo_data):
    """Generate PDF that exactly matches the HTML preview and your desired format"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        # Define consistent styles using the same font
        header_style = ParagraphStyle(
            "CustomHeader",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        address_style = ParagraphStyle(
            "AddressStyle",
            parent=styles["Normal"],
            fontSize=11,
            alignment=1,
            spaceAfter=12,
            fontName="Helvetica",
        )

        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontSize=11,
            fontName="Helvetica",
        )

        story = []

        # Header
        story.append(Paragraph("POLYMATH KIDS DIVISION - MEMO", header_style))
        story.append(
            Paragraph(
                "No 452/3 High Level Road, Nawinna, Maharagama<br/>PV 63200 | Phone 0112802554",
                address_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        story.append(Spacer(1, 12))

        # Child info
        child_info_data = [
            [
                f"Name: {memo_data.get('child_name', 'N/A')}",
                f"Child ID: {memo_data.get('child_admission', 'N/A')}",
            ],
            [
                f"Package: {memo_data.get('package_name', 'N/A')}",
                f"Due Date: {memo_data.get('due_date', 'N/A')}",
            ],
        ]

        child_info_table = Table(child_info_data, colWidths=[100 * mm, 70 * mm])
        child_info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(child_info_table)
        story.append(Spacer(1, 15))

        # Main table data
        table_data = [["Description", "Amount (Rs.)"]]

        # Outstanding section
        outstanding = memo_data.get("outstanding_month", {})
        table_data.append(
            [
                f"{outstanding.get('name', 'Outstanding')} {outstanding.get('year', 2025)}",
                "",
            ]
        )
        table_data.append(
            [
                f"Outstanding from {outstanding.get('name', 'Outstanding')}",
                f"{outstanding.get('balance', 0):,.2f}",
            ]
        )

        # Previous month section
        previous = memo_data.get("previous_month", {})
        table_data.append(
            [
                f"{previous.get('name', 'Previous')} {previous.get('year', 2025)} ",
                "",
            ]
        )
        table_data.append(
            [
                f"Day Care Monthly fee - {previous.get('name', 'Previous')} ({previous.get('days_attended', 0)}/{previous.get('expected_days', 22)} days attended)",
                f"{previous.get('package_fee', 0):,.2f}",
            ]
        )

        # Extra hours if any
        if previous.get("extra_charges", 0) > 0:
            table_data.append(
                ["Extra Hours Charges", f"{previous.get('extra_charges', 0):,.2f}"]
            )

        # Holiday charges if any
        if previous.get("holiday_charges", 0) > 0:
            table_data.append(
                [
                    "Holiday Attendance Charges",
                    f"{previous.get('holiday_charges', 0):,.2f}",
                ]
            )

        # Previous month total
        table_data.append(
            [
                f"Total for {previous.get('name', 'Previous')} {previous.get('year', 2025)}",
                f"{previous.get('month_total', 0):,.2f}",
            ]
        )

        # Current month section
        current = memo_data.get("current_month", {})
        table_data.append(
            [
                f"{current.get('name', 'Current')} {current.get('year', 2025)} ",
                "",
            ]
        )
        table_data.append(
            [
                f"Day Care Monthly fee - {current.get('name', 'Current')} {current.get('year', 2025)} (Full Package)\nAdvance charge for upcoming month",
                f"{current.get('package_fee', 0):,.2f}",
            ]
        )

        # Final total
        totals = memo_data.get("totals", {})
        table_data.append(
            [
                "TOTAL AMOUNT TO PAY\n" + totals.get("final_calculation", ""),
                f"Rs. {totals.get('grand_total', 0):,.2f}",
            ]
        )

        # Create and style table
        main_table = Table(table_data, colWidths=[120 * mm, 35 * mm])

        table_styles = [
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            # Section headers
            ("BACKGROUND", (0, 1), (-1, 1), colors.Color(1, 0.9, 0.9)),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 3), (-1, 3), colors.Color(0.9, 0.95, 1)),
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            # Find advance header dynamically
            ("BACKGROUND", (0, -3), (-1, -3), colors.Color(0.9, 1, 1)),
            ("FONTNAME", (0, -3), (-1, -3), "Helvetica-Bold"),
            # Total rows
            ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.Color(1, 0.95, 0.8)),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]

        main_table.setStyle(TableStyle(table_styles))
        story.append(main_table)
        story.append(Spacer(1, 20))

        # Footer note
        story.append(
            Paragraph(
                f"<b>Please note that,</b> Only the payments made before the invoice date is indicated. "
                f"If there is any outstanding amount please settle on or before <strong> {memo_data.get('due_date', 'N/A')}</strong>. "
                "Ignore this message if you have already settled that outstanding.",
                normal_style,
            )
        )
        story.append(Spacer(1, 12))
        story.append(
            Paragraph("<b>Thank you,</b><br/><b>The Management,</b>", normal_style)
        )
        story.append(Spacer(1, 12))

        # Account details
        account_details = [
            ["Account Details"],
            ["Account Name - Polymath College (PVT) Ltd"],
            ["Bank - Peoples Bank"],
            ["Branch - Gangodawila"],
            ["Account Number - 097100130026495"],
            ["Whatsapp - 0705565858"],
        ]

        account_table = Table(account_details, colWidths=[170 * mm])
        account_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(account_table)

        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        # Create a simple fallback PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"Error generating memo PDF: {str(e)}", styles["Normal"])]
        doc.build(story)
        buffer.seek(0)
        return buffer


def generate_memo_preview_html(memo_data):
    """Generate enhanced HTML preview with detailed breakdowns and payments"""

    # Helper function to format payment details with calculation
    def format_payment_details_with_calc(payments, calculation_display):
        if not payments:
            return "No payments received"

        payment_lines = []
        for payment in payments:
            receipt_info = (
                f"Receipt: {payment['receipt_number']}"
                if payment["receipt_number"] != "N/A"
                else "No receipt"
            )
            payment_lines.append(f"• Rs.{payment['amount']:,.2f} ({receipt_info})")

        result = "<br>".join(payment_lines)
        if calculation_display:
            result += f"<br><strong>Calculation: {calculation_display}</strong>"

        return result

    # Helper function to format extra hours breakdown
    def format_extra_hours_breakdown(breakdown):
        if not breakdown:
            return ""

        breakdown_html = ""
        for item in breakdown:
            if item.get("type") == "summary":
                breakdown_html += "<br><small class='text-muted'>Multiple extra hour </small>"
            else:
                date_formatted = (
                    datetime.strptime(item["date"], "%Y-%m-%d").strftime("%d/%m")
                    if "date" in item
                    else item.get("date", "N/A")
                )
                breakdown_html += f"<br><small class='text-muted'>{date_formatted} → {item.get('time_out', 'N/A')} {item.get('extra_hours_display', '')}</small>"

        return breakdown_html

    # Helper function to format holiday charges breakdown
    def format_holiday_breakdown(breakdown):
        if not breakdown:
            return ""

        breakdown_html = ""
        for item in breakdown:
            if item.get("type") == "summary":
                breakdown_html += (
                    "<br><small class='text-muted'>Holiday attendance charges</small>"
                )
            else:
                date_formatted = (
                    datetime.strptime(item["date"], "%Y-%m-%d").strftime("%d/%m")
                    if "date" in item
                    else item.get("date", "N/A")
                )
                holiday_name = item.get("holiday_name", "Holiday")
                breakdown_html += f"<br><small class='text-muted'>{date_formatted} → {holiday_name}</small>"

        return breakdown_html

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Memo Preview - {memo_data["memo_code"]}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            
            .memo-container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .company-header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            
            .company-title {{
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
            }}
            
            .company-address {{
                font-size: 9px;
                color: #666;
                margin-bottom: 15px;
            }}
            
            .divider {{
                height: 1px;
                background: #000;
                margin: 15px 0;
            }}
            
            .memo-info {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
                font-size: 10px;
            }}
            
            .memo-info .right {{
                text-align: right;
            }}
            
            .memo-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 11px;
                margin-bottom: 20px;
            }}
            
            .memo-table th,
            .memo-table td {{
                border: 0.5px solid #999;
                padding: 8px 6px;
                text-align: left;
                vertical-align: top;
            }}
            
            .memo-table th {{
                background: #e9ecef;
                font-weight: bold;
                font-size: 10px;
            }}
            
            .memo-table .amount-col {{
                text-align: right;
                width: 100px;
            }}
            
            .outstanding-header {{
                background: #ffeaea !important;
                font-weight: bold;
            }}
            
            .calculated-header {{
                background: #e6f3ff !important;
                font-weight: bold;
            }}
            
            .advance-header {{
                background: #e6ffff !important;
                font-weight: bold;
            }}
            
            .total-row {{
                background: #fff4e6 !important;
                font-weight: bold;
            }}
            
            .final-total {{
                background: #fff0cc !important;
                font-weight: bold;
                font-size: 11px;
            }}
            
            .payment-details {{
                background: #f0f8ff;
                font-size: 8px;
                color: #0066cc;
                border-top: 1px dashed #ccc;
                margin-top: 3px;
                padding-top: 3px;
            }}
            
            .payment-calculation {{
                background: #e8f4fd;
                font-size: 8px;
                color: #1565c0;
                border: 1px solid #90caf9;
                border-radius: 3px;
                margin-top: 3px;
                padding: 4px 6px;
                font-weight: bold;
            }}
            
            .breakdown-details {{
                font-size: 8px;
                color: #666;
                margin-top: 2px;
            }}
            
            .memo-note {{
                font-size: 8px;
                margin: 15px 0;
                line-height: 1.2;
            }}
            
            .account-details {{
                background: #f7f7f7;
                border: 0.5px solid #999;
                padding: 8px;
                font-size: 8px;
                margin-top: 15px;
            }}
            
            .account-details .title {{
                font-weight: bold;
                border-bottom: 0.5px solid #999;
                margin-bottom: 5px;
                padding-bottom: 3px;
            }}
            
            .account-details div {{
                padding: 2px 0;
            }}
            
            .action-buttons {{
                text-align: center;
                margin: 20px 0;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 5px;
            }}
            
            .btn {{
                display: inline-block;
                padding: 8px 16px;
                margin: 0 5px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            
            .btn:hover {{
                background: #0056b3;
                color: white;
                text-decoration: none;
            }}
            
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #1e7e34; }}
            
            @media print {{
                .action-buttons {{ display: none; }}
                body {{ background: white; margin: 0; }}
                .memo-container {{ box-shadow: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="action-buttons">
            <a href="javascript:window.print()" class="btn">🖨️ Print</a>
            <a href="#" onclick="downloadPDF()" class="btn btn-success">📄 Download PDF</a>
        </div>
        
        <div class="memo-container">
            <!-- Company Header -->
            <div class="company-header">
                <div class="company-title">POLYMATH KIDS DIVISION - MEMO</div>
                <div class="company-address">
                    No 452/3 High Level Road, Nawinna, Maharagama<br>
                    PV 63200 | Phone 0112802554
                </div>
            </div>
            
            <div class="divider"></div>
            
            <!-- Memo Info -->
            <div class="memo-info">
                <div>
                    <strong>Name:</strong> {memo_data["child_name"]}<br>
                    <strong>Package:</strong> {memo_data["package_name"]}
                </div>
                <div class="right">
                    <strong>Child ID:</strong> {memo_data["child_admission"]}<br>
                    <strong>Due Date:</strong> {memo_data["due_date"]}
                </div>
            </div>
            
            <!-- Main Table -->
            <table class="memo-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th class="amount-col">Amount (Rs.)</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Outstanding Section -->
                    <tr class="outstanding-header">
                        <td>{memo_data["outstanding_month"]["name"]} {memo_data["outstanding_month"]["year"]} </td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>
                            Outstanding from {memo_data["outstanding_month"]["name"]}
                            {f"<div class='payment-details'>{format_payment_details_with_calc(memo_data['outstanding_month']['payments'], memo_data['outstanding_month']['calculation_display'])}</div>" if memo_data["outstanding_month"]["payments"] or memo_data["outstanding_month"]["calculation_display"] else ""}
                        </td>
                        <td class="amount-col">{memo_data["outstanding_month"]["balance"]:,.2f}</td>
                    </tr>
                    
                    <!-- Previous Month Section -->
                    <tr class="calculated-header">
                        <td>{memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]} </td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>
                            Day Care Monthly fee - {memo_data["previous_month"]["name"]} ({memo_data["previous_month"]["days_attended"]}/{memo_data["previous_month"]["expected_days"]} days attended)
                            {f"<div class='payment-details'>{format_payment_details_with_calc(memo_data['previous_month']['payments'], memo_data['previous_month']['calculation_display'])}</div>" if memo_data["previous_month"]["payments"] or memo_data["previous_month"]["calculation_display"] else ""}
                        </td>
                        <td class="amount-col">{memo_data["previous_month"]["package_fee"]:,.2f}</td>
                    </tr>"""

    # Add extra hours if any
    if memo_data["previous_month"]["extra_charges"] > 0:
        extra_hours_text = "Extra Hours Charges"
        if (
            memo_data.get("summary_breakdowns", {}).get(
                "total_extra_hours_instances", 0
            )
            > 0
        ):
            extra_hours_text += f" ({memo_data['summary_breakdowns']['total_extra_hours_instances']} instances)"

        # Add breakdown details
        breakdown_html = format_extra_hours_breakdown(
            memo_data["previous_month"].get("extra_hours_breakdown", [])
        )

        html_content += f"""
                    <tr>
                        <td>
                            {extra_hours_text}
                            {breakdown_html}
                        </td>
                        <td class="amount-col">{memo_data["previous_month"]["extra_charges"]:,.2f}</td>
                    </tr>"""

    # Add holiday charges if any
    if memo_data["previous_month"]["holiday_charges"] > 0:
        holiday_text = "Holiday Attendance Charges"
        if memo_data.get("summary_breakdowns", {}).get("total_holiday_days", 0) > 0:
            holiday_text += (
                f" ({memo_data['summary_breakdowns']['total_holiday_days']} days)"
            )

        # Add breakdown details
        holiday_breakdown_html = format_holiday_breakdown(
            memo_data["previous_month"].get("holiday_charges_breakdown", [])
        )

        html_content += f"""
                    <tr>
                        <td>
                            {holiday_text}
                            {holiday_breakdown_html}
                        </td>
                        <td class="amount-col">{memo_data["previous_month"]["holiday_charges"]:,.2f}</td>
                    </tr>"""

    # Add discount if any
    if memo_data["previous_month"]["discount_applied"] > 0:
        html_content += f"""
                    <tr>
                        <td>Discount Applied</td>
                        <td class="amount-col">-{memo_data["previous_month"]["discount_applied"]:,.2f}</td>
                    </tr>"""

    # Continue with rest of table
    html_content += f"""
                    <tr class="total-row">
                        <td>
                            Total for {memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]}
                            {f"<div class='payment-calculation'>{memo_data['previous_month']['calculation_display']}</div>" if memo_data["previous_month"]["calculation_display"] else ""}
                        </td>
                        <td class="amount-col">{memo_data["previous_month"]["gross_charges"]:,.2f}</td>
                    </tr>
                    
                    <!-- Current Month Section -->
                    <tr class="advance-header">
                        <td>{memo_data["current_month"]["name"]} {memo_data["current_month"]["year"]}</td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>
                            Day Care Monthly fee - {memo_data["current_month"]["name"]} {memo_data["current_month"]["year"]} (Full Package)<br>
                            <span style="color: orange;">Advance charge for upcoming month</span>
                            {f"<div class='payment-details'>{format_payment_details_with_calc(memo_data['current_month']['payments'], memo_data['current_month']['calculation_display'])}</div>" if memo_data["current_month"]["payments"] or memo_data["current_month"]["calculation_display"] else ""}
                        </td>
                        <td class="amount-col">{memo_data["current_month"]["package_fee"]:,.2f}</td>
                    </tr>
                    
                    <!-- Final Total -->
                    <tr class="final-total">
                        <td>
                            <strong>TOTAL AMOUNT TO PAY</strong>
                            {f"<div class='payment-calculation'>{memo_data['totals']['final_calculation']}</div>" if memo_data["totals"].get("final_calculation") else ""}
                        </td>
                        <td class="amount-col"><strong>Rs. {memo_data["totals"]["net_amount_due"]:,.2f}</strong></td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Footer Note -->
            <div class="memo-note">
                <strong>Please note that,</strong> Only the payments made before the invoice date is indicated. 
                If there is any outstanding amount please settle on or before <strong> {memo_data.get('due_date', 'N/A')}</strong>. 
                Ignore this message if you have already settled that outstanding.
            </div>
            
            <div class="memo-note">
                <strong>Thank you,</strong><br>
                <strong>The Management,</strong>
            </div>
            
            <!-- Account Details -->
            <div class="account-details">
                <div class="title">Account Details</div>
                <div>Account Name - Polymath College (PVT) Ltd</div>
                <div>Bank - Peoples Bank</div>
                <div>Branch - Gangodawila</div>
                <div>Account Number - 097100130026495</div>
                <div>Whatsapp - 0705565858</div>
            </div>
        </div>
        
        <script>
            function downloadPDF() {{
                fetch('/download_invoice_memo_pdf/', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    }},
                    body: JSON.stringify({{
                        memo_code: '{memo_data["memo_code"]}',
                        child_id: {memo_data["child_id"]}
                    }})
                }})
                .then(response => {{
                    if (response.ok) {{
                        return response.blob();
                    }} else {{
                        throw new Error('PDF generation failed');
                    }}
                }})
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'Invoice_Memo_{memo_data["memo_code"]}.pdf';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error generating PDF. Please try again.');
                }});
            }}
            
            function getCookie(name) {{
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {{
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {{
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }}
                    }}
                }}
                return cookieValue;
            }}
        </script>
    </body>
    </html>
    """

    return html_content


def get_automatic_breakdown_data(child, month, year):
    """
    Automatically fetch detailed breakdown data for a child's specific month
    Returns breakdown data that can be stored in calculation_details JSON field
    """
    try:
        import calendar
        from collections import defaultdict
        from datetime import datetime, time
        from decimal import Decimal

        # Get date range for the month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # Get package mapping for this period
        package_mapping = (
            ChildPackageMapping.objects.filter(
                child=child,
                is_active=True,
                effective_from__lte=last_day,
            )
            .filter(Q(effective_to__gte=first_day) | Q(effective_to__isnull=True))
            .first()
        )

        if not package_mapping:
            return {
                "extra_hours_breakdown": [],
                "holiday_charges_breakdown": [],
                "summary": {"total_extra_instances": 0, "total_holiday_days": 0},
            }

        # Get attendance logs for the month
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day)
        ).order_by("date_logged", "time_logged")

        # Get holidays in this month
        holidays = Holiday.objects.filter(
            start_date__lte=last_day, end_date__gte=first_day, is_active=True
        ).values_list("start_date", flat=True)
        holiday_dates = set(holidays)

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        # Determine package details
        package = None
        package_end_time = None
        package_type = None

        if package_mapping.normal_package:
            package = package_mapping.normal_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.holiday_package:
            package = package_mapping.holiday_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.flex_package:
            package = package_mapping.flex_package
            package_end_time = time(17, 30)  # Default for flex
            package_type = package.package_type

        if not package_end_time or not package_type:
            return {
                "extra_hours_breakdown": [],
                "holiday_charges_breakdown": [],
                "summary": {"total_extra_instances": 0, "total_holiday_days": 0},
            }

        # Calculate detailed charges
        extra_hours_breakdown = []
        holiday_charges_breakdown = []

        for log_date, logs in logs_by_date.items():
            if len(logs) < 2:  # Need both in and out
                continue

            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))
            time_in = logs_sorted[0].time_logged
            time_out = logs_sorted[-1].time_logged

            if not time_out or not package_end_time:
                continue

            is_holiday_day = log_date in holiday_dates

            # Calculate extra hours charges using corrected cumulative logic
            if time_out > package_end_time:
                package_end_datetime = datetime.combine(log_date, package_end_time)
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                day_extra_charges = Decimal("0.00")
                applied_rates = []

                # Handle charges BEFORE 5:30 PM
                cutoff_530 = time(17, 30)
                if package_end_time < cutoff_530 and time_out > package_end_time:
                    end_time_for_before_530 = min(time_out, cutoff_530)

                    if end_time_for_before_530 > package_end_time:
                        before_530_datetime = datetime.combine(
                            log_date, end_time_for_before_530
                        )
                        hours_before_530 = (
                            before_530_datetime - package_end_datetime
                        ).total_seconds() / 3600

                        hour_count = int(hours_before_530)
                        if hours_before_530 % 1 > 0:
                            hour_count += 1

                        for hour_num in range(1, min(hour_count + 1, 7)):
                            rate_obj = (
                                ExtraHoursUpTo530.objects.filter(
                                    hour_number=hour_num,
                                    effective_from__lte=log_date,
                                    is_active=True,
                                )
                                .filter(
                                    Q(effective_to__gte=log_date)
                                    | Q(effective_to__isnull=True)
                                )
                                .first()
                            )

                            if rate_obj:
                                day_extra_charges += rate_obj.extra_rate
                                applied_rates.append(
                                    {
                                        "time_slot": f"Hour {hour_num} (before 5:30 PM)",
                                        "rate": float(rate_obj.extra_rate),
                                        "type": "Before 5:30 PM",
                                    }
                                )

                # Handle charges AFTER 5:30 PM (cumulative)
                if time_out > cutoff_530:
                    start_time_after_530 = max(package_end_time, cutoff_530)

                    # Get ALL applicable slots (CUMULATIVE)
                    applicable_slots = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__gte=start_time_after_530,
                            from_time__lt=time_out,
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .order_by("from_time")
                    )

                    # Add charges for ALL applicable slots
                    for slot in applicable_slots:
                        day_extra_charges += slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{slot.from_time.strftime('%H:%M')} - {slot.to_time.strftime('%H:%M')}",
                                "rate": float(slot.extra_rate),
                                "type": "After 5:30 PM",
                            }
                        )

                    # Handle partial slot
                    partial_slot = (
                        ExtraHoursAfter530.objects.filter(
                            package_type=package_type,
                            from_time__lt=time_out,
                            to_time__gt=time_out,
                            from_time__gte=start_time_after_530,
                            effective_from__lte=log_date,
                        )
                        .filter(
                            Q(effective_to__gte=log_date) | Q(effective_to__isnull=True)
                        )
                        .first()
                    )

                    if partial_slot and partial_slot not in [
                        slot for slot in applicable_slots
                    ]:
                        day_extra_charges += partial_slot.extra_rate
                        applied_rates.append(
                            {
                                "time_slot": f"{partial_slot.from_time.strftime('%H:%M')} - {partial_slot.to_time.strftime('%H:%M')} (partial)",
                                "rate": float(partial_slot.extra_rate),
                                "type": "After 5:30 PM (Partial)",
                            }
                        )

                if day_extra_charges > 0:
                    # Convert decimal hours to hours and minutes format
                    total_minutes = int(extra_hours * 60)
                    hours_part = total_minutes // 60
                    minutes_part = total_minutes % 60

                    if hours_part > 0:
                        extra_hours_display = f"{hours_part} hr{'s' if hours_part != 1 else ''} {minutes_part} min{'s' if minutes_part != 1 else ''}"
                    else:
                        extra_hours_display = (
                            f"{minutes_part} min{'s' if minutes_part != 1 else ''}"
                        )

                    extra_hours_breakdown.append(
                        {
                            "date": log_date.strftime("%Y-%m-%d"),
                            "day_name": log_date.strftime("%A"),
                            "time_in": time_in.strftime("%H:%M") if time_in else "N/A",
                            "time_out": time_out.strftime("%H:%M"),
                            "package_end_time": package_end_time.strftime("%H:%M"),
                            "extra_hours": round(extra_hours, 2),
                            "extra_hours_display": extra_hours_display,
                            "charges": float(day_extra_charges),
                            "applied_rates": applied_rates,
                            "is_holiday": is_holiday_day,
                        }
                    )

            # Calculate holiday charges
            if is_holiday_day and package_mapping.holiday_package:
                expected_days = package_mapping.holiday_package.no_days_months or 22
                daily_holiday_rate = (
                    package_mapping.holiday_package.package_total
                    / Decimal(expected_days)
                )

                holiday_obj = Holiday.objects.filter(
                    start_date__lte=log_date, end_date__gte=log_date, is_active=True
                ).first()

                holiday_charges_breakdown.append(
                    {
                        "date": log_date.strftime("%Y-%m-%d"),
                        "day_name": log_date.strftime("%A"),
                        "holiday_name": holiday_obj.title if holiday_obj else "Holiday",
                        "holiday_package": package_mapping.holiday_package.package_name,
                        "daily_rate": float(daily_holiday_rate),
                        "charges": float(daily_holiday_rate),
                    }
                )

        return {
            "extra_hours_breakdown": extra_hours_breakdown,
            "holiday_charges_breakdown": holiday_charges_breakdown,
            "summary": {
                "total_extra_instances": len(extra_hours_breakdown),
                "total_holiday_days": len(holiday_charges_breakdown),
                "package_name": package.package_name if package else "Unknown",
                "package_end_time": package_end_time.strftime("%H:%M")
                if package_end_time
                else "Unknown",
                "month_name": calendar.month_name[month],
                "year": year,
            },
        }

    except Exception as e:
        print(f"Error in get_automatic_breakdown_data: {str(e)}")
        return {
            "extra_hours_breakdown": [],
            "holiday_charges_breakdown": [],
            "summary": {
                "total_extra_instances": 0,
                "total_holiday_days": 0,
                "error": str(e),
            },
        }


def enhance_existing_memo_with_breakdown(memo_id):
    """
    Enhance an existing memo with detailed breakdown data
    This can be called to update memos that were created without detailed breakdowns
    """
    try:
        memo = InvoiceMemo.objects.get(id=memo_id)
        previous_detail = memo.month_details.filter(month_type="PREVIOUS").first()

        if not previous_detail:
            return False, "No previous month detail found"

        # Get breakdown data for the previous month
        breakdown_data = get_automatic_breakdown_data(
            memo.child, previous_detail.actual_month, previous_detail.actual_year
        )

        # Update the calculation_details field
        current_calc_details = previous_detail.calculation_details or {}
        current_calc_details.update(breakdown_data)

        previous_detail.calculation_details = current_calc_details
        previous_detail.save()

        return True, f"Enhanced memo {memo.memo_code} with detailed breakdown"

    except Exception as e:
        return False, f"Error enhancing memo: {str(e)}"


@login_required
def enhanceExistingMemoBreakdown(request):
    """
    View to enhance existing memos with detailed breakdown data
    Can be called via AJAX to update memos retroactively
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        memo_id = request.POST.get("memo_id")
        if not memo_id:
            return JsonResponse({"error": "Memo ID required"}, status=400)

        success, message = enhance_existing_memo_with_breakdown(memo_id)

        if success:
            return JsonResponse({"success": True, "message": message})
        else:
            return JsonResponse({"error": message}, status=400)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


#@login_required
@transaction.atomic
def generateEnhancedMemoFromCalculation(request):
    """Generate memo with CORRECTED detailed breakdown storage for display"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        data = json.loads(request.body)
        child_id = data.get("child_id")
        month = data.get("month")
        year = data.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)
        month_int = int(month)
        year_int = int(year)

        # Check if memo already exists
        if InvoiceMemo.objects.filter(
            child=child, memo_month=month_int, memo_year=year_int, is_active=True
        ).exists():
            return JsonResponse(
                {
                    "error": f"Memo already exists for {calendar.month_name[month_int]} {year_int}"
                },
                status=400,
            )

        # Calculate month positions
        if month_int > 2:
            outstanding_month = month_int - 2
            outstanding_year = year_int
        elif month_int == 2:
            outstanding_month = 12
            outstanding_year = year_int - 1
        else:  # month_int == 1
            outstanding_month = 11
            outstanding_year = year_int - 1

        if month_int > 1:
            previous_month = month_int - 1
            previous_year = year_int
        else:
            previous_month = 12
            previous_year = year_int - 1

        # Get detailed breakdown for previous month using existing function
        previous_month_breakdown = get_automatic_breakdown_data(child, previous_month, previous_year)
        
        # Calculate enhanced data for all three months
        three_month_data = calculate_enhanced_three_month_data(child, month, year)

        # Generate memo code
        next_memo_id = InvoiceMemo.objects.count() + 1
        memo_code = f"MO{next_memo_id:04d}"
        while InvoiceMemo.objects.filter(memo_code=memo_code).exists():
            next_memo_id += 1
            memo_code = f"MO{next_memo_id:04d}"

        with transaction.atomic():
            # Create main memo record
            memo = InvoiceMemo.objects.create(
                memo_date=datetime.now().date(),
                memo_code=memo_code,
                child=child,
                memo_month=month_int,
                memo_year=year_int,
                status="GENERATED",
                notes=f"Auto-generated enhanced memo with detailed breakdown on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                user_created=request.user.username,
            )

            # Extract data using existing structure
            month1_data = three_month_data["month1"]  # Outstanding
            month2_data = three_month_data["month2"]  # Calculated (Previous)
            month3_data = three_month_data["month3"]  # Advance (Current)

            # Create Outstanding Month Detail (Month 1)
            outstanding_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=1,
                month_type="OUTSTANDING",
                actual_month=outstanding_month,
                actual_year=outstanding_year,
                month_name=month1_data["name"],
                package_fee=Decimal(str(month1_data.get("charge", 0))),
                extra_hours_charge=Decimal("0"),
                holiday_charges=Decimal("0"),
                other_charges=Decimal("0"),
                discount_applied=Decimal("0"),
                other_deductions=Decimal("0"),
                payments_received=Decimal(str(month1_data.get("payments", 0))),
                payment_receipts=month1_data.get("payment_details", []),
                package_name="Outstanding Balance",
                notes=f"Outstanding from {month1_data['name']}",
                calculation_details={
                    "type": "outstanding",
                    "original_charge": month1_data.get("charge", 0),
                    "payments_received": month1_data.get("payments", 0),
                    "calculation": f"Rs.{month1_data.get('charge', 0):,.2f} - Rs.{month1_data.get('payments', 0):,.2f} = Rs.{month1_data.get('balance', 0):,.2f}",
                },
                user_created=request.user.username,
            )

            # Create Previous Month Detail (Month 2) - WITH DETAILED BREAKDOWN
            previous_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=2,
                month_type="PREVIOUS",
                actual_month=previous_month,
                actual_year=previous_year,
                month_name=month2_data["name"],
                package_fee=Decimal(str(month2_data.get("package_fee", 0))),
                extra_hours_charge=Decimal(str(month2_data.get("extra_charges", 0))),
                holiday_charges=Decimal(str(month2_data.get("holiday_charges", 0))),
                other_charges=Decimal("0"),
                discount_applied=Decimal(str(month2_data.get("discount", 0))),
                other_deductions=Decimal("0"),
                payments_received=Decimal(str(month2_data.get("payments", 0))),
                payment_receipts=month2_data.get("payment_details", []),
                package_name=month2_data.get("package_name", "Normal Package"),
                days_attended=month2_data.get("days_attended", 0),
                expected_days=month2_data.get("expected_days", 22),
                attendance_percentage=Decimal(
                    str(month2_data.get("attendance_percentage", 0))
                ),
                is_half_charge_applied=month2_data.get("is_half_charge", False),
                notes=f"Calculated for {month2_data['name']} - {month2_data.get('days_attended', 0)}/{month2_data.get('expected_days', 22)} days",
                calculation_details={
                    "type": "calculated",
                    # Store the detailed breakdown from automatic calculation
                    "extra_hours_breakdown": previous_month_breakdown.get("extra_hours_breakdown", []),
                    "holiday_charges_breakdown": previous_month_breakdown.get("holiday_charges_breakdown", []),
                    "breakdown_summary": previous_month_breakdown.get("summary", {}),
                    "payment_details": month2_data.get("payment_details", []),
                    "calculation": f"Package: Rs.{month2_data.get('package_fee', 0):,.2f} + Extra: Rs.{month2_data.get('extra_charges', 0):,.2f} - Payment: Rs.{month2_data.get('payments', 0):,.2f}",
                    # Add formatted breakdown text for display
                    "extra_hours_display_text": format_extra_hours_for_display(previous_month_breakdown.get("extra_hours_breakdown", [])),
                    "holiday_charges_display_text": format_holiday_charges_for_display(previous_month_breakdown.get("holiday_charges_breakdown", [])),
                },
                user_created=request.user.username,
            )

            # Create Current Month Detail (Month 3) - ADVANCE section
            current_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=3,
                month_type="CURRENT",
                actual_month=month_int,
                actual_year=year_int,
                month_name=month3_data["name"],
                package_fee=Decimal(str(month3_data.get("package_fee", 0))),
                extra_hours_charge=Decimal("0"),  # No extra hours for advance
                holiday_charges=Decimal("0"),  # No holiday charges for advance
                other_charges=Decimal("0"),
                discount_applied=Decimal(str(month3_data.get("discount", 0))),
                other_deductions=Decimal("0"),
                payments_received=Decimal(str(month3_data.get("payments", 0))),
                payment_receipts=month3_data.get("payment_details", []),
                package_name=month3_data.get("package_name", "Normal Package"),
                expected_days=month3_data.get("expected_days", 22),
                notes=f"Advance charge for {month3_data['name']} (Full Package)",
                calculation_details={
                    "type": "advance",
                    "full_package_charge": True,
                    "payment_details": month3_data.get("payment_details", []),
                    "calculation": f"Rs.{month3_data.get('package_fee', 0):,.2f} - Rs.{month3_data.get('payments', 0):,.2f} = Rs.{month3_data.get('balance', 0):,.2f}",
                },
                user_created=request.user.username,
            )

            # Calculate memo totals using model method
            memo.calculate_totals()

        # Return success with corrected totals
        return JsonResponse(
            {
                "success": True,
                "memo_code": memo_code,
                "memo_id": memo.id,
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "month_name": calendar.month_name[month_int],
                "year": year_int,
                "net_amount_due": float(memo.net_amount_due),
                "gross_total": float(memo.gross_total),
                "total_payments": float(memo.total_payments),
                "breakdown": {
                    "outstanding": float(outstanding_detail.net_balance),
                    "previous_month": float(previous_detail.net_balance),
                    "current_month": float(current_detail.net_balance),
                    "total": float(memo.net_amount_due),
                },
                "detailed_breakdown": {
                    "extra_hours_instances": len(previous_month_breakdown.get("extra_hours_breakdown", [])),
                    "holiday_days": len(previous_month_breakdown.get("holiday_charges_breakdown", [])),
                }
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


def format_extra_hours_for_display(extra_hours_breakdown):
    """Format extra hours breakdown for PDF/HTML display like the PDF sample"""
    if not extra_hours_breakdown:
        return ""
    
    formatted_lines = []
    for item in extra_hours_breakdown:
        # Format: 2025-05-08 -> 18:10 (0.09h extra)
        date_part = item.get("date", "").replace("-", "-")
        if date_part.startswith("2025-"):
            # Convert 2025-05-08 to 05-08 format
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")
            date_display = date_obj.strftime("%m-%d")
        else:
            date_display = date_part
            
        time_out = item.get("time_out", "N/A")
        extra_hours = item.get("extra_hours", 0)
        extra_hours_display = item.get("extra_hours_display", f"{extra_hours:.2f}h extra")
        
        formatted_lines.append(f"2025-{date_display} -> {time_out} ({extra_hours_display})")
    
    return "\n".join(formatted_lines)


def format_holiday_charges_for_display(holiday_breakdown):
    """Format holiday charges breakdown for display"""
    if not holiday_breakdown:
        return ""
    
    formatted_lines = []
    for item in holiday_breakdown:
        date_part = item.get("date", "").replace("-", "-")
        if date_part.startswith("2025-"):
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")
            date_display = date_obj.strftime("%m-%d")
        else:
            date_display = date_part
            
        holiday_name = item.get("holiday_name", "Holiday")
        charges = item.get("charges", 0)
        
        formatted_lines.append(f"2025-{date_display} -> {holiday_name} (Rs.{charges:,.2f})")
    
    return "\n".join(formatted_lines)

def generate_memo_preview_html_fixed(memo_data):
    """Generate HTML preview with detailed breakdown matching PDF format"""

    # Add extra hours section with detailed breakdown like in PDF
    extra_hours_html = ""
    if memo_data["previous_month"]["extra_charges"] > 0:
        extra_hours_description = memo_data["previous_month"].get("extra_hours_description", "Extra Hours Charges")
        extra_hours_detail = memo_data["previous_month"].get("extra_hours_detail", "")
        
        # Format the detail text for HTML display
        detail_html = ""
        if extra_hours_detail:
            # Split the detail text into lines and format each
            detail_lines = extra_hours_detail.split('\n')
            detail_html_lines = []
            for line in detail_lines:
                if line.strip():
                    detail_html_lines.append(f"<span style='font-size: 9px; color: #666; font-style: italic;'>{line.strip()}</span>")
            detail_html = "<br>".join(detail_html_lines)
        
        extra_hours_html = f"""
                    <tr>
                        <td>
                            {extra_hours_description}
                            {f"<br>{detail_html}" if detail_html else ""}
                        </td>
                        <td class="amount-col">{memo_data["previous_month"]["extra_charges"]:,.2f}</td>
                    </tr>"""

    # Add holiday charges section if any
    holiday_charges_html = ""
    if memo_data["previous_month"].get("holiday_charges", 0) > 0:
        holiday_description = memo_data["previous_month"].get("holiday_description", "Holiday Attendance Charges")
        holiday_charges_html = f"""
                    <tr>
                        <td>{holiday_description}</td>
                        <td class="amount-col">{memo_data["previous_month"]["holiday_charges"]:,.2f}</td>
                    </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Memo Preview - {memo_data["memo_code"]}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background: #f5f5f5;
                font-size: 10px;
                line-height: 1.2;
            }}
            
            .memo-container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .company-header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            
            .company-title {{
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .company-address {{
                font-size: 11px;
                color: #000;
                margin-bottom: 15px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .divider {{
                height: 1px;
                background: #000;
                margin: 15px 0;
            }}
            
            .memo-info {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
                font-size: 11px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .memo-table {{
                width: 100%;
                border-collapse: collapse;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 11px;
                margin-bottom: 20px;
            }}
            
            .memo-table th,
            .memo-table td {{
                border: 1px solid #000;
                padding: 8px;
                text-align: left;
                vertical-align: top;
                font-size: 11px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .memo-table th {{
                background: #e9ecef;
                font-weight: bold;
                font-size: 11px;
            }}
            
            .memo-table .amount-col {{
                text-align: right;
                width: 120px;
            }}
            
            .outstanding-header {{
                background: #ffeaea !important;
                font-weight: bold;
            }}
            
            .calculated-header {{
                background: #e6f3ff !important;
                font-weight: bold;
            }}
            
            .advance-header {{
                background: #e6ffff !important;
                font-weight: bold;
            }}
            
            .total-row {{
                font-weight: bold;
            }}
            
            .final-total {{
                background: #fff0cc !important;
                font-weight: bold;
            }}
            
            .breakdown-detail {{
                font-size: 9px;
                color: #666;
                font-style: italic;
                line-height: 1.2;
                margin-top: 2px;
            }}
            
            .memo-note {{
                font-size: 11px;
                margin: 15px 0;
                line-height: 1.4;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .account-details {{
                border: 1px solid #000;
                margin-top: 15px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 9px;
                
            }}
            
            .account-details .title {{
                background: #f0f0f0;
                font-weight: bold;
                padding: 8px;
                border-bottom: 1px solid #000;
                font-size: 11px;
            }}
            
            .account-details .row {{
                padding: 6px 8px;
                border-bottom: 1px solid #000;
                font-size: 11px;
            }}
            
            .account-details .row:last-child {{
                border-bottom: none;
            }}
            
            .action-buttons {{
                text-align: center;
                margin: 20px 0;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 5px;
            }}
            
            .btn {{
                display: inline-block;
                padding: 8px 16px;
                margin: 0 5px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            
            .btn:hover {{
                background: #0056b3;
                color: white;
                text-decoration: none;
            }}
            
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #1e7e34; }}
            
            @media print {{
                .action-buttons {{ display: none; }}
                body {{ background: white; margin: 0; }}
                .memo-container {{ box-shadow: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="action-buttons">
            <a href="javascript:window.print()" class="btn">🖨️ Print</a>
            <a href="#" onclick="downloadPDF()" class="btn btn-success">📄 Download PDF</a>
        </div>
        
        <div class="memo-container">
            <!-- Company Header -->
            <div class="company-header">
                <div class="company-title">POLYMATH KIDS DIVISION - MEMO</div>
                <div class="company-address">
                    No 452/3 High Level Road, Nawinna, Maharagama<br>
                    PV 63200 | Phone 0112802554
                </div>
            </div>
            
            <div class="divider"></div>
            
            <!-- Memo Info -->
            <div class="memo-info">
                <div>
                    <strong>Name:</strong> {memo_data["child_name"]}<br>
                    <strong>Package:</strong> {memo_data["package_name"]}
                </div>
                <div>
                    <strong>Child ID:</strong> {memo_data["child_admission"]}<br>
                    <strong>Due Date:</strong> {memo_data["due_date"]}
                </div>
            </div>
            
            <!-- Main Table -->
            <table class="memo-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th class="amount-col">Amount (Rs.)</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Outstanding Section -->
                    <tr class="outstanding-header">
                        <td>{memo_data["outstanding_month"]["name"]} {memo_data["outstanding_month"]["year"]} </td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>Outstanding from {memo_data["outstanding_month"]["name"]}</td>
                        <td class="amount-col">{memo_data["outstanding_month"]["balance"]:,.2f}</td>
                    </tr>
                    
                    <!-- Previous Month Section -->
                    <tr class="calculated-header">
                        <td>{memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]} </td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>{memo_data["previous_month"]["package_description"]}</td>
                        <td class="amount-col">{memo_data["previous_month"]["package_fee"]:,.2f}</td>
                    </tr>
                    
                    {extra_hours_html}
                    
                    {holiday_charges_html}
                    
                    <tr class="total-row">
                        <td><strong>Total for {memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]}</strong></td>
                        <td class="amount-col"><strong>{memo_data["previous_month"]["month_total"]:,.2f}</strong></td>
                    </tr>
                    
                    <!-- Current Month Section -->
                    <tr class="advance-header">
                        <td>{memo_data["current_month"]["name"]} {memo_data["current_month"]["year"]}</td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>
                            {memo_data["current_month"]["package_description"]}<br>
                            <span style="color: orange; font-size: 10px;">{memo_data["current_month"]["advance_note"]}</span>
                        </td>
                        <td class="amount-col">{memo_data["current_month"]["package_fee"]:,.2f}</td>
                    </tr>
                    
                    <!-- Final Total -->
                    <tr class="final-total">
                        <td>
                            <strong>TOTAL AMOUNT TO PAY</strong>
                        </td>
                        <td class="amount-col"><strong>Rs. {memo_data["totals"]["grand_total"]:,.2f}</strong></td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Footer Note -->
            <div class="memo-note">
                <strong>Please note that,</strong> Only the payments made before the invoice date is indicated. 
                If there is any outstanding amount please settle on or before <strong> {memo_data.get('due_date', 'N/A')}</strong>. 
                Ignore this message if you have already settled that outstanding.
            </div>
            
            <div class="memo-note">
                <strong>Thank you,</strong><br>
                <strong>The Management,</strong>
            </div>
            
            <!-- Account Details -->
            <div class="account-details">
                <div class="title">Account Details</div>
                <div class="row">Account Name - Polymath College (PVT) Ltd</div>
                <div class="row">Bank - Peoples Bank</div>
                <div class="row">Branch - Gangodawila</div>
                <div class="row">Account Number - 097100130026495</div>
                <div class="row">Whatsapp - 0705565858</div>
            </div>
        </div>
        
        <script>
            function downloadPDF() {{
                fetch('/download_invoice_memo_pdf/', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    }},
                    body: JSON.stringify({{
                        memo_code: '{memo_data["memo_code"]}',
                        child_id: {memo_data["child_id"]}
                    }})
                }})
                .then(response => {{
                    if (response.ok) {{
                        return response.blob();
                    }} else {{
                        throw new Error('PDF generation failed');
                    }}
                }})
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'Invoice_Memo_{memo_data["memo_code"]}.pdf';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error generating PDF. Please try again.');
                }});
            }}
            
            function getCookie(name) {{
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {{
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {{
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }}
                    }}
                }}
                return cookieValue;
            }}
        </script>
    </body>
    </html>
    """

    return html_content

def format_extra_hours_for_memo_display(extra_hours_breakdown):
    """Format extra hours breakdown for memo display exactly like PDF format"""
    if not extra_hours_breakdown:
        return ""
    
    print(f"DEBUG: Formatting breakdown with {len(extra_hours_breakdown)} items")  # Debug
    
    # Format each line like: 2025-05-08 -> 18:10 (0.09h extra)
    formatted_lines = []
    for item in extra_hours_breakdown:
        
        
        date_str = item.get("date", "")
        time_out = item.get("time_out", "N/A")
        extra_hours = item.get("extra_hours", 0)
        extra_hours_display = item.get("extra_hours_display", "")
        
        # Convert date format if needed
        if date_str:
            try:
                # If it's already in YYYY-MM-DD format, use it directly
                if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
                    formatted_lines.append(f"{date_str} -> {time_out} ({extra_hours_display})")
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = date_obj.strftime("%Y-%m-%d")
                    formatted_lines.append(f"{date_display} -> {time_out} ({extra_hours_display})")
            except Exception as e:
                print(f"DEBUG: Date formatting error: {e}")
                formatted_lines.append(f"{date_str} -> {time_out} ({extra_hours_display})")
        else:
            formatted_lines.append(f"N/A -> {time_out} ({extra_hours_display})")
    
    result = "\n".join(formatted_lines)
    return result


def prepare_memo_display_data_fixed(memo):
    """CORRECTED memo display data preparation with detailed breakdown matching PDF format - FIXED VERSION"""
    try:
        details = memo.month_details.all().order_by("month_sequence")

        # Get basic info
        base_data = {
            "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
            "child_admission": memo.child.admission_number,
            "child_id": memo.child.id,
            "memo_code": memo.memo_code,
            "memo_date": memo.memo_date.strftime("%d/%m/%Y"),
            "due_date": (memo.memo_date + timedelta(days=7)).strftime("%d/%m/%Y"),
            "status": memo.status,
        }

        if details.count() == 3:
            outstanding_detail = details[0]
            previous_detail = details[1]
            current_detail = details[2]

            # Get package name
            package_name = (
                previous_detail.package_name
                or current_detail.package_name
                or "Normal Package"
            )

            # Get payment receipt numbers
            outstanding_receipt = "N/A"
            if outstanding_detail.payment_receipts:
                outstanding_receipt = outstanding_detail.payment_receipts[0].get(
                    "receipt_number", "N/A"
                )

            previous_receipt = "N/A"
            if previous_detail.payment_receipts:
                previous_receipt = previous_detail.payment_receipts[0].get(
                    "receipt_number", "N/A"
                )

            # Extract detailed breakdown from calculation_details - FIXED
            calc_details = previous_detail.calculation_details or {}
            
            
            extra_hours_breakdown = calc_details.get("extra_hours_breakdown", [])
            holiday_breakdown = calc_details.get("holiday_charges_breakdown", [])
            
            
            
            # Format extra hours detail text like the PDF
            extra_hours_detail_text = ""
            if extra_hours_breakdown and len(extra_hours_breakdown) > 0:
                extra_hours_detail_text = format_extra_hours_for_memo_display(extra_hours_breakdown)
                print(f"DEBUG: Generated detail text: {extra_hours_detail_text}")  # Debug
            elif previous_detail.extra_hours_charge > 0:
                # Fallback if no detailed breakdown stored
                extra_hours_detail_text = f"Multiple instances (Rs.{previous_detail.extra_hours_charge:,.2f})"
                print("DEBUG: Using fallback detail text")  # Debug

            # Count instances for display
            extra_instances_count = len(extra_hours_breakdown) if extra_hours_breakdown else (1 if previous_detail.extra_hours_charge > 0 else 0)
            holiday_days_count = len(holiday_breakdown) if holiday_breakdown else (1 if previous_detail.holiday_charges > 0 else 0)

            base_data.update({
                "package_name": package_name,
                # Outstanding month
                "outstanding_month": {
                    "name": outstanding_detail.month_name,
                    "year": outstanding_detail.actual_year,
                    "original_charge": float(outstanding_detail.package_fee),
                    "payment_amount": float(outstanding_detail.payments_received),
                    "payment_receipt": outstanding_receipt,
                    "balance": float(outstanding_detail.net_balance),
                    "calculation_text": f"Rs.{outstanding_detail.package_fee:,.2f} - Rs.{outstanding_detail.payments_received:,.2f} = Rs.{outstanding_detail.net_balance:,.2f}",
                },
                # Previous month - WITH FIXED DETAILED BREAKDOWN
                "previous_month": {
                    "name": previous_detail.month_name,
                    "year": previous_detail.actual_year,
                    "package_fee": float(previous_detail.package_fee),
                    "package_description": f"Day Care Monthly fee - {previous_detail.month_name} ({previous_detail.days_attended or 0}/{previous_detail.expected_days or 22} days attended)",
                    "payment_amount": float(previous_detail.payments_received),
                    "payment_receipt": previous_receipt,
                    "payment_calculation": f"Rs.{previous_detail.package_fee:,.2f} - Rs.{previous_detail.payments_received:,.2f} = Rs.{previous_detail.package_fee - previous_detail.payments_received:,.2f}",
                    "subtotal_after_payment": float(previous_detail.package_fee - previous_detail.payments_received),
                    
                    # Extra hours section with FIXED detailed breakdown
                    "extra_charges": float(previous_detail.extra_hours_charge),
                    "extra_hours_description": f"Extra Hours Charges {extra_instances_count} instances",
                    "extra_hours_detail": extra_hours_detail_text,  # This should now show the detailed breakdown
                    "extra_hours_breakdown_list": extra_hours_breakdown,
                    
                    # Holiday charges section
                    "holiday_charges": float(previous_detail.holiday_charges),
                    "holiday_description": f"Holiday Attendance Charges {holiday_days_count} days" if holiday_days_count > 0 else "Holiday Attendance Charges",
                    "holiday_breakdown_list": holiday_breakdown,
                    
                    # Month total
                    "month_total": float(previous_detail.net_balance + previous_detail.extra_hours_charge + previous_detail.holiday_charges),
                    
                    # Detailed breakdown
                    "days_attended": previous_detail.days_attended or 0,
                    "expected_days": previous_detail.expected_days or 22,
                    "attendance_percentage": float(previous_detail.attendance_percentage or 0),
                    "is_half_charge": previous_detail.is_half_charge_applied,
                },
                # Current month
                "current_month": {
                    "name": current_detail.month_name,
                    "year": current_detail.actual_year,
                    "package_fee": float(current_detail.package_fee),
                    "package_description": f"Day Care Monthly fee - {current_detail.month_name} {current_detail.actual_year} (Full Package)",
                    "advance_note": "Advance charge for upcoming month",
                    "payment_status": "No payments received",
                    "balance": float(current_detail.net_balance),
                },
                # Summary totals
                "totals": {
                    "outstanding": float(outstanding_detail.net_balance),
                    "previous_month": float(previous_detail.net_balance + previous_detail.extra_hours_charge + previous_detail.holiday_charges),
                    "current_month": float(current_detail.net_balance),
                    "grand_total": float(memo.net_amount_due),
                    "final_calculation": f"Rs.{outstanding_detail.net_balance:,.2f} + Rs.{previous_detail.net_balance + previous_detail.extra_hours_charge + previous_detail.holiday_charges:,.2f} + Rs.{current_detail.net_balance:,.2f} = Rs.{memo.net_amount_due:,.2f}",
                },
            })

        else:
            # Fallback for incomplete data
            base_data.update({
                "package_name": "Normal Package",
                "outstanding_month": {
                    "name": "Outstanding", "year": 2025, "original_charge": 0,
                    "payment_amount": 0, "payment_receipt": "N/A", "balance": 0, "calculation_text": "",
                },
                "previous_month": {
                    "name": "Previous", "year": 2025, "package_fee": 0, "package_description": "Day Care Monthly fee",
                    "payment_amount": 0, "payment_receipt": "N/A", "payment_calculation": "",
                    "subtotal_after_payment": 0, "extra_charges": 0, "extra_hours_description": "Extra Hours Charges",
                    "extra_hours_detail": "", "month_total": 0, "days_attended": 0, "expected_days": 22,
                    "attendance_percentage": 0, "is_half_charge": False, "holiday_charges": 0,
                },
                "current_month": {
                    "name": "Current", "year": 2025, "package_fee": 0, "package_description": "Day Care Monthly fee",
                    "advance_note": "Advance charge for upcoming month", "payment_status": "No payments received", "balance": 0,
                },
                "totals": {
                    "outstanding": 0, "previous_month": 0, "current_month": 0, "grand_total": 0, "final_calculation": "",
                },
            })

        return base_data

    except Exception as e:
        print(f"Error in prepare_memo_display_data_fixed: {str(e)}")
        import traceback
        traceback.print_exc()
        return base_data

# Update your existing loadInvoiceMemo view to include the generate button
@login_required
def loadInvoiceMemo(request):
    """Enhanced load memo form with generate functionality"""
    try:
        form = LoadInvoiceMemoForm()

        # Get children for dropdown
        children = Child.objects.filter(
            is_active=True, is_enrolled=True, enrollement_approved=True
        ).order_by("admission_number")

        context = {
            "form": form,
            "children": children,
            "UserName": request.user.username,
        }
        return render(request, "../templates/invoice.html", context)
    except Exception as e:
        messages.error(request, f"Error loading memo form: {str(e)}")
        return redirect("core:memo_data_entry")


def generate_memo_pdf_with_two_column_breakdown(memo_data):
    """Generate PDF with detailed breakdown in 2-column format"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        # Define consistent styles
        header_style = ParagraphStyle(
            "CustomHeader",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=6,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        address_style = ParagraphStyle(
            "AddressStyle",
            parent=styles["Normal"],
            fontSize=11,
            alignment=1,
            spaceAfter=12,
            fontName="Helvetica",
        )

        normal_style = ParagraphStyle(
            "NormalStyle",
            parent=styles["Normal"],
            fontSize=11,
            fontName="Helvetica",
        )

        # Style for breakdown items
        breakdown_style = ParagraphStyle(
            "BreakdownStyle",
            parent=styles["Normal"],
            fontSize=9,
            fontName="Helvetica",
            leftIndent=10,
            spaceAfter=2,
        )

        story = []

        # Header
        story.append(Paragraph("POLYMATH KIDS DIVISION - MEMO", header_style))
        story.append(
            Paragraph(
                "No 452/3 High Level Road, Nawinna, Maharagama<br/>PV 63200 | Phone 0112802554",
                address_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        story.append(Spacer(1, 12))

        # Child info
        child_info_data = [
            [
                f"Name: {memo_data.get('child_name', 'N/A')}",
                f"Child ID: {memo_data.get('child_admission', 'N/A')}",
            ],
            [
                f"Package: {memo_data.get('package_name', 'N/A')}",
                f"Due Date: {memo_data.get('due_date', 'N/A')}",
            ],
        ]

        child_info_table = Table(child_info_data, colWidths=[100 * mm, 70 * mm])
        child_info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(child_info_table)
        story.append(Spacer(1, 15))

        # Main table data
        table_data = [["Description", "Amount (Rs.)"]]

        # Outstanding section
        outstanding = memo_data.get("outstanding_month", {})
        table_data.append(
            [
                f"{outstanding.get('name', 'Outstanding')} {outstanding.get('year', 2025)} • OUTSTANDING",
                "",
            ]
        )
        
        outstanding_desc = f"Outstanding from {outstanding.get('name', 'Outstanding')}"
        table_data.append([outstanding_desc, f"{outstanding.get('balance', 0):,.2f}"])

        # Previous month section
        previous = memo_data.get("previous_month", {})
        table_data.append(
            [
                f"{previous.get('name', 'Previous')} {previous.get('year', 2025)} • CALCULATED",
                "",
            ]
        )

        # Day care monthly fee
        package_desc = previous.get(
            "package_description",
            f"Day Care Monthly fee - {previous.get('name', 'Previous')} ({previous.get('days_attended', 0)}/{previous.get('expected_days', 22)} days attended)",
        )
        table_data.append([package_desc, f"{previous.get('package_fee', 0):,.2f}"])

        # Extra hours with 2-column detailed breakdown
        if previous.get("extra_charges", 0) > 0:
            extra_breakdown = previous.get("extra_hours_breakdown_list", [])
            extra_count = len(extra_breakdown)
            
            extra_description = f"Extra Hours for the month"
            
            if extra_breakdown and len(extra_breakdown) > 0:
                # Create 2-column breakdown table
                breakdown_table_data = []
                
                # Split items into 2 columns
                for i in range(0, len(extra_breakdown), 2):
                    left_item = extra_breakdown[i]
                    right_item = extra_breakdown[i + 1] if i + 1 < len(extra_breakdown) else None
                    
                    # Format left column
                    left_text = format_breakdown_item(left_item)
                    
                    # Format right column (if exists)
                    right_text = format_breakdown_item(right_item) if right_item else ""
                    
                    breakdown_table_data.append([left_text, right_text])
                
                # Create the breakdown table
                breakdown_table = Table(breakdown_table_data, colWidths=[60 * mm, 60 * mm])
                breakdown_table.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                            # No borders for breakdown table
                            ("GRID", (0, 0), (-1, -1), 0, colors.white),
                        ]
                    )
                )
                
                # Combine description with breakdown table
                full_extra_desc = [
                    [extra_description, f"{previous.get('extra_charges', 0):,.2f}"],
                    [breakdown_table, ""]  # Breakdown table spans both columns
                ]
                
                # Add both rows
                table_data.extend(full_extra_desc)
            else:
                # Fallback if no detailed breakdown
                table_data.append([extra_description, f"{previous.get('extra_charges', 0):,.2f}"])

        # Holiday charges with 2-column breakdown
        if previous.get("holiday_charges", 0) > 0:
            holiday_breakdown = previous.get("holiday_breakdown_list", [])
            holiday_count = len(holiday_breakdown)
            
            holiday_description = f"Holiday Attendance Charges {holiday_count} days"
            
            if holiday_breakdown and len(holiday_breakdown) > 0:
                # Create 2-column breakdown for holidays
                holiday_breakdown_data = []
                
                for i in range(0, len(holiday_breakdown), 2):
                    left_item = holiday_breakdown[i]
                    right_item = holiday_breakdown[i + 1] if i + 1 < len(holiday_breakdown) else None
                    
                    left_text = format_holiday_breakdown_item(left_item)
                    right_text = format_holiday_breakdown_item(right_item) if right_item else ""
                    
                    holiday_breakdown_data.append([left_text, right_text])
                
                holiday_breakdown_table = Table(holiday_breakdown_data, colWidths=[60 * mm, 60 * mm])
                holiday_breakdown_table.setStyle(
                    TableStyle(
                        [
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                            ("GRID", (0, 0), (-1, -1), 0, colors.white),
                        ]
                    )
                )
                
                full_holiday_desc = [
                    [holiday_description, f"{previous.get('holiday_charges', 0):,.2f}"],
                    [holiday_breakdown_table, ""]
                ]
                
                table_data.extend(full_holiday_desc)
            else:
                table_data.append([holiday_description, f"{previous.get('holiday_charges', 0):,.2f}"])

        # Previous month total
        table_data.append(
            [
                f"Total for {previous.get('name', 'Previous')} {previous.get('year', 2025)}",
                f"{previous.get('month_total', 0):,.2f}",
            ]
        )

        # Current month section
        current = memo_data.get("current_month", {})
        table_data.append(
            [
                f"{current.get('name', 'Current')} {current.get('year', 2025)} • ADVANCE",
                "",
            ]
        )

        current_desc = current.get(
            "package_description",
            f"Day Care Monthly fee - {current.get('name', 'Current')} {current.get('year', 2025)} (Full Package)",
        )
        current_desc += f"\n{current.get('advance_note', 'Advance charge for upcoming month')}"
        table_data.append([current_desc, f"{current.get('package_fee', 0):,.2f}"])

        # Final total
        totals = memo_data.get("totals", {})
        table_data.append(
            [
                "TOTAL AMOUNT TO PAY",
                f"Rs. {totals.get('grand_total', 0):,.2f}",
            ]
        )

        # Create and style main table
        main_table = Table(table_data, colWidths=[120 * mm, 35 * mm])

        # Calculate row indices for styling (this gets complex with dynamic rows)
        table_styles = [
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            # Section headers - you'll need to calculate these based on your table structure
            ("BACKGROUND", (0, 1), (-1, 1), colors.Color(1, 0.9, 0.9)),  # Outstanding
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 3), (-1, 3), colors.Color(0.9, 0.95, 1)),  # Calculated
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            # Final total
            ("BACKGROUND", (0, -1), (-1, -1), colors.Color(1, 0.95, 0.8)),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]

        main_table.setStyle(TableStyle(table_styles))
        story.append(main_table)
        story.append(Spacer(1, 20))

        # Footer note
        story.append(
            Paragraph(
                f"<b>Please note that,</b> Only the payments made before the invoice date is indicated. "
                f"If there is any outstanding amount please settle on or before {memo_data.get('due_date', 'N/A')}. "
                "Ignore this message if you have already settled that outstanding.",
                normal_style,
            )
        )
        story.append(Spacer(1, 12))
        story.append(
            Paragraph("<b>Thank you,</b><br/><b>The Management,</b>", normal_style)
        )
        story.append(Spacer(1, 12))

        # Account details
        account_details = [
            ["Account Details"],
            ["Account Name - Polymath College (PVT) Ltd"],
            ["Bank - Peoples Bank"],
            ["Branch - Gangodawila"],
            ["Account Number - 097100130026495"],
            ["Whatsapp - 0705565858"],
        ]

        account_table = Table(account_details, colWidths=[170 * mm])
        account_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(account_table)

        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Create fallback PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(f"Error generating memo PDF: {str(e)}", styles["Normal"])]
        doc.build(story)
        buffer.seek(0)
        return buffer


def format_breakdown_item(item):
    """Format individual extra hours breakdown item"""
    if not item:
        return ""
    
    date_str = item.get("date", "")
    time_out = item.get("time_out", "N/A")
    extra_hours_display = item.get("extra_hours_display", "")
    charges = item.get("charges", 0)
    
    # Format date
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except:
            formatted_date = date_str
    else:
        formatted_date = "N/A"
    
    return f"{formatted_date} -> {time_out} ({extra_hours_display})"


def format_holiday_breakdown_item(item):
    """Format individual holiday breakdown item"""
    if not item:
        return ""
    
    date_str = item.get("date", "")
    holiday_name = item.get("holiday_name", "Holiday")
    charges = item.get("charges", 0)
    
    # Format date
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except:
            formatted_date = date_str
    else:
        formatted_date = "N/A"
    
    return f"{formatted_date} -> {holiday_name} (Rs.{charges:,.2f})"


def count_breakdown_items(memo_data):
    """Count extra hours and holiday breakdown items"""
    previous = memo_data.get("previous_month", {})
    
    extra_breakdown = previous.get("extra_hours_breakdown_list", [])
    holiday_breakdown = previous.get("holiday_breakdown_list", [])
    
    return {
        "extra_hours_count": len(extra_breakdown),
        "holiday_days_count": len(holiday_breakdown),
        "extra_breakdown_items": extra_breakdown,
        "holiday_breakdown_items": holiday_breakdown
    }

def generate_memo_preview_html_with_two_columns(memo_data):
    """Generate HTML preview with 2-column breakdown display"""

    # Process breakdown data
    previous = memo_data.get("previous_month", {})
    extra_breakdown = previous.get("extra_hours_breakdown_list", [])
    holiday_breakdown = previous.get("holiday_breakdown_list", [])
    
    # Generate extra hours HTML with 2-column layout
    extra_hours_html = ""
    if previous.get("extra_charges", 0) > 0:
        extra_count = len(extra_breakdown)
        extra_description = f"Extra Hours Charges for the month"
        
        # Create 2-column breakdown
        breakdown_html = ""
        if extra_breakdown:
            breakdown_html = '<div class="breakdown-grid">'
            for i in range(0, len(extra_breakdown), 2):
                left_item = extra_breakdown[i]
                right_item = extra_breakdown[i + 1] if i + 1 < len(extra_breakdown) else None
                
                left_text = format_breakdown_item_html(left_item)
                right_text = format_breakdown_item_html(right_item) if right_item else ""
                
                breakdown_html += f'''
                <div class="breakdown-row">
                    <div class="breakdown-col">{left_text}</div>
                    <div class="breakdown-col">{right_text}</div>
                </div>'''
            breakdown_html += '</div>'
        
        extra_hours_html = f"""
                    <tr>
                        <td>
                            {extra_description}
                            {breakdown_html}
                        </td>
                        <td class="amount-col">{previous.get('extra_charges', 0):,.2f}</td>
                    </tr>"""

    # Generate holiday charges HTML with 2-column layout
    holiday_charges_html = ""
    if previous.get("holiday_charges", 0) > 0:
        holiday_count = len(holiday_breakdown)
        holiday_description = f"Holiday Attendance Charges {holiday_count} days"
        
        # Create 2-column breakdown for holidays
        holiday_breakdown_html = ""
        if holiday_breakdown:
            holiday_breakdown_html = '<div class="breakdown-grid">'
            for i in range(0, len(holiday_breakdown), 2):
                left_item = holiday_breakdown[i]
                right_item = holiday_breakdown[i + 1] if i + 1 < len(holiday_breakdown) else None
                
                left_text = format_holiday_breakdown_item_html(left_item)
                right_text = format_holiday_breakdown_item_html(right_item) if right_item else ""
                
                holiday_breakdown_html += f'''
                <div class="breakdown-row">
                    <div class="breakdown-col">{left_text}</div>
                    <div class="breakdown-col">{right_text}</div>
                </div>'''
            holiday_breakdown_html += '</div>'
        
        holiday_charges_html = f"""
                    <tr>
                        <td>
                            {holiday_description}
                            {holiday_breakdown_html}
                        </td>
                        <td class="amount-col">{previous.get('holiday_charges', 0):,.2f}</td>
                    </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Memo Preview - {memo_data["memo_code"]}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background: #f5f5f5;
                font-size: 11px;
                line-height: 1.4;
            }}
            
            .memo-container {{
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .company-header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            
            .company-title {{
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
            }}
            
            .company-address {{
                font-size: 11px;
                color: #000;
                margin-bottom: 15px;
            }}
            
            .divider {{
                height: 1px;
                background: #000;
                margin: 15px 0;
            }}
            
            .memo-info {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
                font-size: 11px;
            }}
            
            .memo-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 11px;
                margin-bottom: 20px;
            }}
            
            .memo-table th,
            .memo-table td {{
                border: 1px solid #000;
                padding: 8px;
                text-align: left;
                vertical-align: top;
                font-size: 11px;
            }}
            
            .memo-table th {{
                background: #e9ecef;
                font-weight: bold;
            }}
            
            .memo-table .amount-col {{
                text-align: right;
                width: 120px;
            }}
            
            .outstanding-header {{
                background: #ffeaea !important;
                font-weight: bold;
            }}
            
            .calculated-header {{
                background: #e6f3ff !important;
                font-weight: bold;
            }}
            
            .advance-header {{
                background: #e6ffff !important;
                font-weight: bold;
            }}
            
            .total-row {{
                font-weight: bold;
            }}
            
            .final-total {{
                background: #fff0cc !important;
                font-weight: bold;
            }}
            
            /* 2-Column Breakdown Styles */
            .breakdown-grid {{
                margin-top: 8px;
                font-size: 9px;
                color: #666;
                font-style: italic;
            }}
            
            .breakdown-row {{
                display: flex;
                margin-bottom: 3px;
            }}
            
            .breakdown-col {{
                flex: 1;
                padding-right: 10px;
                line-height: 1.3;
            }}
            
            .breakdown-col:last-child {{
                padding-right: 0;
            }}
            
            .memo-note {{
                font-size: 11px;
                margin: 15px 0;
                line-height: 1.4;
            }}
            
            .account-details {{
                border: 1px solid #000;
                margin-top: 15px;
            }}
            
            .account-details .title {{
                background: #f0f0f0;
                font-weight: bold;
                padding: 8px;
                border-bottom: 1px solid #000;
                font-size: 11px;
            }}
            
            .account-details .row {{
                padding: 6px 8px;
                border-bottom: 1px solid #000;
                font-size: 11px;
            }}
            
            .account-details .row:last-child {{
                border-bottom: none;
            }}
            
            .action-buttons {{
                text-align: center;
                margin: 20px 0;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 5px;
            }}
            
            .btn {{
                display: inline-block;
                padding: 8px 16px;
                margin: 0 5px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            
            .btn:hover {{
                background: #0056b3;
                color: white;
                text-decoration: none;
            }}
            
            .btn-success {{ background: #28a745; }}
            .btn-success:hover {{ background: #1e7e34; }}
            
            @media print {{
                .action-buttons {{ display: none; }}
                body {{ background: white; margin: 0; }}
                .memo-container {{ box-shadow: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="action-buttons">
            <a href="javascript:window.print()" class="btn">🖨️ Print</a>
            <a href="#" onclick="downloadPDF()" class="btn btn-success">📄 Download PDF</a>
        </div>
        
        <div class="memo-container">
            <!-- Company Header -->
            <div class="company-header">
                <div class="company-title">POLYMATH KIDS DIVISION - MEMO</div>
                <div class="company-address">
                    No 452/3 High Level Road, Nawinna, Maharagama<br>
                    PV 63200 | Phone 0112802554
                </div>
            </div>
            
            <div class="divider"></div>
            
            <!-- Memo Info -->
            <div class="memo-info">
                <div>
                    <strong>Name:</strong> {memo_data["child_name"]}<br>
                    <strong>Package:</strong> {memo_data["package_name"]}
                </div>
                <div>
                    <strong>Child ID:</strong> {memo_data["child_admission"]}<br>
                    <strong>Due Date:</strong> {memo_data["due_date"]}
                </div>
            </div>
            
            <!-- Main Table -->
            <table class="memo-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th class="amount-col">Amount (Rs.)</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Outstanding Section -->
                    <tr class="outstanding-header">
                        <td>{memo_data["outstanding_month"]["name"]} {memo_data["outstanding_month"]["year"]} • OUTSTANDING</td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>Outstanding from {memo_data["outstanding_month"]["name"]}</td>
                        <td class="amount-col">{memo_data["outstanding_month"]["balance"]:,.2f}</td>
                    </tr>
                    
                    <!-- Previous Month Section -->
                    <tr class="calculated-header">
                        <td>{memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]} • CALCULATED</td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>{memo_data["previous_month"]["package_description"]}</td>
                        <td class="amount-col">{memo_data["previous_month"]["package_fee"]:,.2f}</td>
                    </tr>
                    
                    {extra_hours_html}
                    
                    {holiday_charges_html}
                    
                    <tr class="total-row">
                        <td><strong>Total for {memo_data["previous_month"]["name"]} {memo_data["previous_month"]["year"]}</strong></td>
                        <td class="amount-col"><strong>{memo_data["previous_month"]["month_total"]:,.2f}</strong></td>
                    </tr>
                    
                    <!-- Current Month Section -->
                    <tr class="advance-header">
                        <td>{memo_data["current_month"]["name"]} {memo_data["current_month"]["year"]} • ADVANCE</td>
                        <td class="amount-col"></td>
                    </tr>
                    <tr>
                        <td>
                            {memo_data["current_month"]["package_description"]}<br>
                            <span style="color: orange; font-size: 10px;">{memo_data["current_month"]["advance_note"]}</span>
                        </td>
                        <td class="amount-col">{memo_data["current_month"]["package_fee"]:,.2f}</td>
                    </tr>
                    
                    <!-- Final Total -->
                    <tr class="final-total">
                        <td>
                            <strong>TOTAL AMOUNT TO PAY</strong>
                        </td>
                        <td class="amount-col"><strong>Rs. {memo_data["totals"]["grand_total"]:,.2f}</strong></td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Footer Note -->
            <div class="memo-note">
                <strong>Please note that,</strong> Only the payments made before the invoice date is indicated. 
                If there is any outstanding amount please settle on or before {memo_data["due_date"]}. 
                Ignore this message if you have already settled that outstanding.
            </div>
            
            <div class="memo-note">
                <strong>Thank you,</strong><br>
                <strong>The Management,</strong>
            </div>
            
            <!-- Account Details -->
            <div class="account-details">
                <div class="title">Account Details</div>
                <div class="row">Account Name - Polymath College (PVT) Ltd</div>
                <div class="row">Bank - Peoples Bank</div>
                <div class="row">Branch - Gangodawila</div>
                <div class="row">Account Number - 097100130026495</div>
                <div class="row">Whatsapp - 0705565858</div>
            </div>
        </div>
        
        <script>
            function downloadPDF() {{
                fetch('/download_invoice_memo_pdf/', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    }},
                    body: JSON.stringify({{
                        memo_code: '{memo_data["memo_code"]}',
                        child_id: {memo_data["child_id"]}
                    }})
                }})
                .then(response => {{
                    if (response.ok) {{
                        return response.blob();
                    }} else {{
                        throw new Error('PDF generation failed');
                    }}
                }})
                .then(blob => {{
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'Invoice_Memo_{memo_data["memo_code"]}.pdf';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error generating PDF. Please try again.');
                }});
            }}
            
            function getCookie(name) {{
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {{
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {{
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }}
                    }}
                }}
                return cookieValue;
            }}
        </script>
    </body>
    </html>
    """

    return html_content


def format_breakdown_item_html(item):
    """Format individual extra hours breakdown item for HTML"""
    if not item:
        return ""
    
    date_str = item.get("date", "")
    time_out = item.get("time_out", "N/A")
    extra_hours_display = item.get("extra_hours_display", "")
    
    # Format date
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except:
            formatted_date = date_str
    else:
        formatted_date = "N/A"
    
    return f"{formatted_date} → {time_out} ({extra_hours_display})"


def format_holiday_breakdown_item_html(item):
    """Format individual holiday breakdown item for HTML"""
    if not item:
        return ""
    
    date_str = item.get("date", "")
    holiday_name = item.get("holiday_name", "Holiday")
    charges = item.get("charges", 0)
    
    # Format date
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except:
            formatted_date = date_str
    else:
        formatted_date = "N/A"
    
    return f"{formatted_date} → {holiday_name} (Rs.{charges:,.2f})"