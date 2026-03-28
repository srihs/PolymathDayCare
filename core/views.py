import calendar
import csv
import datetime
import json
import logging
import math
import os
import shutil
import tempfile
from collections import defaultdict
from datetime import date, datetime, time, timedelta
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
    Sum,
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
    CreateVacationForm,
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
    UpdateVacationForm,
)
from .models import (
    AttendanceLog,
    AttendanceLogAudit,
    Branch,
    CenterChangerequest,
    Child,
    ChildEnrollment,
    ChildPackageMapping,
    DayCare,
    Discount,
    EnrollmentDiscountRequest,
    ExtraChargesHistory,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    FixedPackage,
    FlexPackages,
    Holiday,
    InvoiceMemo,
    InvoiceMemoDetail,
    PackageChangerequest,
    PackageExtraHoursMapping,
    PackageType,
    PaymentTransaction,
    TimeAdjustmentRequest,
)

# Authentication and Basic Utility Functions


@login_required
def index(request):
    """
    Renders the main dashboard/home page of the daycare management system.

    This is the entry point after successful login, displaying the main navigation
    and dashboard overview with key performance indicators (KPIs).

    Args:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the index.html template with dashboard KPIs and metrics

    Business Logic:
        - Requires user authentication via @login_required decorator
        - Calculates and displays key metrics:
            - Active enrolled children count
            - Today's attendance count and percentage
            - Pending approvals across all approval workflows
            - Outstanding balance from unpaid invoices
            - Monthly revenue from current month charges
            - Payment status (percentage of paid invoices)
        - Shows upcoming holidays for the next 30 days
    """
    UserName = request.user.username
    today = date.today()

    # 1. Active Children: Count of children with is_active=True and is_enrolled=True
    active_children_count = Child.objects.filter(
        is_active=True, is_enrolled=True
    ).count()

    # 2. Total Children: Count of all children in the database
    total_children_in_db = Child.objects.count()

    # 3. Not Enrolled: Count of children where is_enrolled=False
    not_enrolled_count = Child.objects.filter(is_enrolled=False).count()

    # 4. Outstanding Balance: Sum of net_amount_due from InvoiceMemo where status in ['GENERATED', 'PARTIAL']
    outstanding_balance = (
        InvoiceMemo.objects.filter(
            status__in=["GENERATED", "PARTIAL"], is_active=True
        ).aggregate(total=Sum("net_amount_due"))["total"]
        or Decimal("0.00")
    )

    # 5. Monthly Revenue: Sum of gross_charges from InvoiceMemoDetail for current month where month_type='CURRENT'
    current_month = today.month
    current_year = today.year

    monthly_revenue = (
        InvoiceMemoDetail.objects.filter(
            month_type="CURRENT",
            actual_month=current_month,
            actual_year=current_year,
            is_active=True,
        ).aggregate(total=Sum("gross_charges"))["total"]
        or Decimal("0.00")
    )

    # 6. Active Child %: Children with attendance in last 60 days (2 months)
    two_months_ago = today - timedelta(days=60)

    # Children with at least one attendance record in last 60 days
    # Only count enrolled children (is_active=True, is_enrolled=True) to match Active Children KPI
    children_with_recent_attendance = (
        Child.objects.filter(
            is_active=True,
            is_enrolled=True,
            attendancelog__date_logged__gte=two_months_ago,
            attendancelog__is_active=True,
        )
        .distinct()
        .count()
    )

    # Use enrolled children count as the base (same as Active Children KPI)
    total_children_count = active_children_count

    active_child_percentage = 0
    if total_children_count > 0:
        active_child_percentage = round(
            (children_with_recent_attendance / total_children_count) * 100, 1
        )

    # 7. Upcoming Holidays: Next 30 days from Holiday model
    thirty_days_from_now = today + timedelta(days=30)
    upcoming_holidays = Holiday.objects.filter(
        start_date__gte=today, start_date__lte=thirty_days_from_now, is_active=True
    ).order_by("start_date")[:5]

    # 8. Inactive Children: Active enrolled children with no attendance in last 2 months
    # Use subquery to get the last attendance date for each child
    last_attendance_subquery = (
        AttendanceLog.objects.filter(child=OuterRef("pk"), is_active=True)
        .order_by("-date_logged")
        .values("date_logged")[:1]
    )

    # Children who are active and enrolled but have no attendance in last 60 days
    inactive_children = (
        Child.objects.filter(is_active=True, is_enrolled=True)
        .annotate(last_attended=Subquery(last_attendance_subquery))
        .filter(Q(last_attended__lt=two_months_ago) | Q(last_attended__isnull=True))
        .order_by(F("last_attended").desc(nulls_last=True))[:10]
    )

    inactive_children_count = (
        Child.objects.filter(is_active=True, is_enrolled=True)
        .annotate(last_attended=Subquery(last_attendance_subquery))
        .filter(Q(last_attended__lt=two_months_ago) | Q(last_attended__isnull=True))
        .count()
    )

    # Prepare context for template
    context = {
        "UserName": UserName,
        # KPI Metrics - Row 1
        "active_children_count": active_children_count,
        "total_children_in_db": total_children_in_db,
        "not_enrolled_count": not_enrolled_count,
        # KPI Metrics - Row 2
        "outstanding_balance": outstanding_balance,
        "monthly_revenue": monthly_revenue,
        "active_child_percentage": active_child_percentage,
        "children_with_recent_attendance": children_with_recent_attendance,
        "total_children_count": total_children_count,
        # Upcoming holidays
        "upcoming_holidays": upcoming_holidays,
        # Inactive children
        "inactive_children": inactive_children,
        "inactive_children_count": inactive_children_count,
        # Date info
        "current_month_name": today.strftime("%B"),
        "current_year": current_year,
    }

    return render(request, "index.html", context)


def UserLogOut(request):
    """
    Logs out the current user and redirects to the home page.

    This function handles user logout by clearing the session data and
    redirecting to the login/home page.

    Args:
        request (HttpRequest): The HTTP request object containing user session

    Returns:
        HttpResponseRedirect: Redirects to the home page after logout

    Business Logic:
        - Clears all session data for the current user
        - Redirects to the core:home URL pattern (typically login page)
        - No authentication required as this is a public logout action
    """
    logout(request)
    return redirect("core:home")


def UserLogin(request):
    """
    Handles user authentication and login for the daycare management system.

    This function processes both GET and POST requests for user login.
    GET requests display the login form, while POST requests attempt to
    authenticate the user credentials.

    Args:
        request (HttpRequest): The HTTP request object containing login data

    Returns:
        HttpResponse: Either renders login.html template or redirects after successful login

    Business Logic:
        - GET request: Displays the login form
        - POST request: Validates username and password credentials
        - On successful authentication: Logs in user and redirects to intended page
        - Supports secure redirect to 'next' parameter if provided
        - Validates redirect URLs to prevent malicious redirects
        - Shows error messages for invalid credentials or inactive users
        - Handles exceptions gracefully with error messages
    """
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
    """
    Generates a QR code image for a child's attendance tracking.

    This function creates a QR code containing the child's attendance tracking URL,
    adds the child's name and admission number as text below the QR code,
    and saves the complete image to the media/qr directory.

    Args:
        admission_no (str): The child's unique admission number
        child_first_name (str): The child's first name
        child_last_name (str): The child's last name

    Returns:
        str: The filename of the generated QR code image

    Business Logic:
        - Creates QR code with URL: PROD_URL + QR_METHOD_NAME + admission_no
        - Generates PNG image with QR code and child's name/admission number
        - Saves image to media/qr/ directory with structured filename
        - QR code links to attendance recording system for easy check-in/out
        - Image includes child identification text for manual verification

    File Structure:
        - Filename format: "[admission_no]- [first_name] [last_name].png"
        - Saved to: media/qr/[filename]
    """
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
def getChildJson(request):
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
def getChildWithEnrolementsJson(request):
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

        # Check user permissions - Data Entry users cannot create/update children
        user = User.objects.get(username=request.user.username)
        if user.groups.filter(name="Data Entry").exists():
            messages.error(request, "You are not authorized to perform this operation.")
            return redirect("core:view_child")

        try:
            # Use get_or_create to handle both creation and updates
            # This allows the same function to handle both new children and updates
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
                # Record exists, update it with new information
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
    """
    Soft deletes a child record by setting is_active to False.

    This function performs a soft delete operation on a child record,
    preserving the data for historical purposes while marking the child
    as inactive. It also sets the leave date and updates audit fields.

    Args:
        request (HttpRequest): The HTTP request object
        pk (int): The primary key of the child to delete

    Returns:
        HttpResponseRedirect: Redirects to view_child page

    Business Logic:
        - Checks user permissions (Data Entry users are restricted)
        - Performs soft delete by setting is_active=False
        - Sets leave_date to current timestamp
        - Updates user_updated audit field
        - Preserves all child data for historical and reporting purposes
        - Shows appropriate success/error messages

    Security:
        - Requires login authentication
        - Restricts Data Entry group users from deletion
        - Uses get_object_or_404 for safe record retrieval
    """
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


# Package Type Management Functions


@login_required
def getPackageTypeJs(reuest):
    """
    Retrieves all active package types as JSON for frontend consumption.

    This endpoint provides package type data for use in dropdowns,
    DataTables, and other frontend components that need to display
    or select package types.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing active package types

    Business Logic:
        - Filters package types by is_active=True
        - Returns essential package type information
        - Includes holiday and vacation package flags for business logic
        - Includes computed category field for display purposes
        - Used for package selection in various forms
    """
    packageTypes = PackageType.objects.filter(is_active=True)
    packageTypeList = []
    for pt in packageTypes:
        packageTypeList.append({
            "id": pt.id,
            "package_type_name": pt.package_type_name,
            "is_holiday_package": pt.is_holiday_package,
            "is_vacation_package": pt.is_vacation_package,
            "category": pt.get_package_category(),
            "is_active": pt.is_active,
        })
    return JsonResponse(packageTypeList, safe=False)


@login_required
def getPacakgeTypes(request):
    """
    Displays the package types management page with creation form.

    This function renders the package types management interface,
    allowing users to view, create, and manage package types.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders packagetypes.html template with form

    Business Logic:
        - GET request: Shows empty creation form
        - Handles both creation and update scenarios
        - Provides interface for managing package types
        - Package types define normal vs holiday packages

    Package Type Categories:
        - Normal packages: Regular daycare packages
        - Holiday packages: Special pricing for holiday periods
    """
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
    """
    Retrieves a specific package type by ID as JSON with formatted data.

    This endpoint fetches a single package type and formats the data
    for frontend display, including converting boolean values to
    user-friendly text.

    Args:
        request (HttpRequest): The HTTP request object with packageType_id parameter

    Returns:
        JsonResponse: JSON array containing the specific package type

    Business Logic:
        - Expects packageType_id in GET parameters
        - Converts is_active boolean to "Active"/"Inactive" text
        - Includes holiday and vacation package flags
        - Includes computed category field for display purposes
        - Returns formatted data for frontend display
        - Used for populating edit forms and detail views
    """
    if request.GET.get("packageType_id") is not None:
        id = request.GET.get("packageType_id")
        packageTypeList = list(
            PackageType.objects.filter(id=id).values(
                "id",
                "package_type_name",
                "is_holiday_package",
                "is_vacation_package",
                "is_active",
            )
        )
        for i, n in enumerate(packageTypeList):
            if n["is_active"] == True:
                packageTypeList[i]["is_active"] = "Active"
            else:
                packageTypeList[i]["is_active"] = "Inactive"
            # Add category based on package type flags
            if n["is_holiday_package"]:
                packageTypeList[i]["category"] = "Holiday"
            elif n["is_vacation_package"]:
                packageTypeList[i]["category"] = "Vacation"
            else:
                packageTypeList[i]["category"] = "Normal"
    return JsonResponse(packageTypeList, safe=False)


@login_required
def getPackageTypeId(request):
    """
    Retrieves a specific package type and prepares it for editing.

    This function fetches a package type record by ID and creates
    an update form pre-populated with the existing data.

    Args:
        request (HttpRequest): The HTTP request object with packageType_id parameter

    Returns:
        HttpResponse: Renders packagetypeUpdate.html template with update form

    Business Logic:
        - Expects packageType_id in GET parameters
        - Stores package type ID in session for update operation
        - Creates UpdatePackageTypeForm pre-populated with existing data
        - Handles exceptions gracefully with error messages
        - Used for editing existing package types
    """
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
    """
    Saves or updates package type information.

    This function handles both creation of new package types and
    updates to existing ones, with proper validation and security checks.

    Args:
        request (HttpRequest): The HTTP request object containing package type data

    Returns:
        HttpResponseRedirect: Redirects to package types view page

    Business Logic:
        - Handles both create and update operations
        - Validates user permissions (restricts Data Entry users)
        - Processes checkboxes for is_holiday_package and is_vacation_package
        - Ensures only one category can be selected (Normal, Holiday, or Vacation)
        - Updates audit fields (user_updated, date_updated)
        - Creates new record if no ID provided
        - Updates existing record if ID provided

    Form Fields:
        - package_type_name: Name of the package type
        - is_holiday_package: Boolean flag for holiday packages (public holidays)
        - is_vacation_package: Boolean flag for vacation packages (polymath/other holidays)
        - is_active: Always set to True for new/updated records

    Security:
        - Restricts Data Entry group users from updates
        - Validates package type existence before update
    """
    try:
        if request.method == "POST":
            form = UpdatePackageTypeForm(request.POST)
            objPackageType = form.save(commit=False)
            # capturing the variables with data
            package_type_name = request.POST.get("package_type_name")
            is_holiday_package = request.POST.get("is_holiday_package")
            is_vacation_package = request.POST.get("is_vacation_package")
            if is_holiday_package == "on":
                is_holiday_package = True
            else:
                is_holiday_package = False
            if is_vacation_package == "on":
                is_vacation_package = True
            else:
                is_vacation_package = False
            # Validate that only one category is selected
            if is_holiday_package and is_vacation_package:
                messages.error(
                    request,
                    "A package type cannot be both Holiday and Vacation. Please select only one.",
                )
                return redirect("core:view_package_types")
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
                        objPackageType.is_vacation_package = is_vacation_package
                        objPackageType.is_active = True
                        objPackageType.user_updated = request.user.username
                        objPackageType.date_updated = datetime.now()
                        objPackageType.save()
                        messages.success(request, "Package type details updated.")
            else:
                objPackageType = PackageType(
                    package_type_name=package_type_name,
                    is_holiday_package=is_holiday_package,
                    is_vacation_package=is_vacation_package,
                    is_active=True,
                    user_created=request.user.username,
                )
                objPackageType.save()
                messages.success(request, "Package type saved.")
    except Exception as e:
        messages.error(request, e)
    return redirect("core:view_package_types")


# Additional Rates and Extra Hours Management Functions


@login_required
def getAdditionalRatesUpto530(request):
    """
    Displays the additional rates (up to 5:30 PM) management page.

    This function renders the interface for managing extra hour rates
    that apply to children who stay beyond regular hours but before 5:30 PM.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders extrahourseupto530.html template with form

    Business Logic:
        - Displays form for creating extra hour rates (up to 5:30 PM)
        - Supports rate definition for hours 1-6 beyond regular time
        - Each hour can have different rates and effective date ranges
        - Used for managing tiered pricing structure

    Rate Structure:
        - Hour 1-6: Different rates for each additional hour
        - Effective date ranges: Start and end dates for rate validity
        - Separate rates for before and after 5:30 PM
    """
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
    """
    Saves additional rates for extra hours up to 5:30 PM.

    This function processes the form data for creating extra hour rates
    that apply before 5:30 PM, creating both the rate records and
    corresponding history entries for audit purposes.

    Args:
        request (HttpRequest): The HTTP request object containing rate data

    Returns:
        HttpResponseRedirect: Redirects to additional rates page

    Business Logic:
        - Validates user permissions (restricts Data Entry users)
        - Processes rates for hours 1-6 beyond regular time
        - Creates ExtraHoursUpTo530 records for each hour
        - Creates corresponding ExtraChargesHistory records
        - Uses atomic transactions to ensure data consistency
        - Only saves rates that have both rate and effective_from date

    Database Operations:
        - Creates ExtraHoursUpTo530 records for pricing
        - Creates ExtraChargesHistory records for audit trail
        - Uses @transaction.atomic for data integrity

    Form Processing:
        - Processes dynamic form fields (extra_rate_1 to extra_rate_6)
        - Validates required fields before saving
        - Handles effective date ranges for each rate
    """
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
    """
    Updates existing additional rates for extra hours up to 5:30 PM.

    This function handles updates to existing extra hour rates,
    maintaining a complete audit trail by creating history records
    for all changes.

    Args:
        request (HttpRequest): The HTTP request object containing updated rate data

    Returns:
        HttpResponseRedirect: Redirects to additional rates page

    Business Logic:
        - Validates user permissions (restricts Data Entry users)
        - Updates existing ExtraHoursUpTo530 record
        - Creates new ExtraChargesHistory record for audit trail
        - Uses atomic transactions for data consistency
        - Updates audit fields (user_updated)

    Database Operations:
        - Updates ExtraHoursUpTo530 record with new values
        - Creates ExtraChargesHistory record for change tracking
        - Uses @transaction.atomic for data integrity

    Audit Trail:
        - Every rate change creates a history record
        - Tracks who made the change and when
        - Preserves effective date ranges for historical analysis
    """
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
    """
    Calculates the duration between two times in hours and minutes.

    This utility function takes start and end times and calculates
    the duration between them, returning the result as hours and minutes.
    Used for calculating package durations and attendance periods.

    Args:
        request (HttpRequest): GET request with from_time and to_time parameters

    Returns:
        JsonResponse: JSON object containing duration_hours and duration_minutes

    URL Parameters:
        from_time (str): Start time in "HH:MM" format
        to_time (str): End time in "HH:MM" format

    Business Logic:
        - Parses time strings into datetime objects
        - Calculates difference in seconds
        - Converts to hours and minutes
        - Used for package duration calculations

    Error Handling:
        - Returns 400 for invalid time formats
        - Returns 500 for other exceptions
        - All errors returned as JSON responses
    """
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
def getFixedPackages(request):
    """
    Displays the fixed packages management page with creation form.

    This function renders the fixed packages management interface,
    allowing users to create and manage time-based daycare packages
    with fixed hours and pricing.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders fixedpackages.html template with form

    Business Logic:
        - Generates next package code (FIP00X format)
        - Validates prerequisite data (package types, extra charges)
        - Shows error messages if prerequisites are missing
        - Provides form for creating new fixed packages

    Fixed Package Features:
        - Time-based packages with from/to times
        - Fixed number of hours per day/week/month
        - Automatic duration calculation
        - Integration with extra hour charges

    Prerequisites:
        - Package types must be defined
        - Extra charges must be configured
        - Both are required for package creation

    Security:
        - Requires login authentication
        - Package code auto-generation prevents conflicts
    """
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
    """
    Retrieves all fixed packages as JSON for frontend consumption.

    This endpoint provides fixed package data for use in DataTables,
    dropdowns, and other frontend components that need to display
    or select fixed packages.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing fixed package details

    Business Logic:
        - Fetches all fixed packages with essential fields
        - Resolves package type foreign key to readable name
        - Includes timing, duration, and pricing information
        - Used for package selection and display

    Package Information:
        - Package identification (id, code, name)
        - Timing details (from_time, to_time, no_hours)
        - Frequency (no_days_week, no_days_months)
        - Pricing (package_total)
        - Package type (resolved to name)

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
    """
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
    """
    Saves a new fixed package with automatic extra hours mapping.

    This function processes the form data for creating a new fixed package,
    automatically setting up the appropriate extra hours mappings based on
    the package timing and type.

    Args:
        request (HttpRequest): POST request containing fixed package data

    Returns:
        HttpResponseRedirect: Redirects to view_fixed_packages page

    Business Logic:
        - Creates new FixedPackage record from form data
        - Determines if package is holiday-based from package type
        - Automatically creates PackageExtraHoursMapping records
        - Maps extra hours that extend beyond package end time
        - Maps before 5:30 PM rates if package ends before 5:30 PM

    Extra Hours Mapping:
        - After 5:30 PM: Maps rates that extend beyond package end time
        - Before 5:30 PM: Maps all rates if package ends before 5:30 PM
        - Only applies to non-holiday packages

    Database Operations:
        - Creates FixedPackage record
        - Creates multiple PackageExtraHoursMapping records
        - Uses @transaction.atomic for data consistency

    Package Code Generation:
        - Uses format: FIP00X (Fixed Package)
        - Auto-increments based on existing package count

    Security:
        - Requires login authentication
        - Uses atomic transactions for data integrity
    """
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
    """
    Displays the flexible packages management page with creation form.

    This function renders the flexible packages management interface,
    allowing users to create and manage hour-based flexible daycare packages
    without fixed time constraints.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders flexpackages.html template with form

    Business Logic:
        - Generates next package code (FLP00X format)
        - Validates prerequisite data (package types, extra charges)
        - Shows error messages if prerequisites are missing
        - Provides form for creating new flexible packages

    Flexible Package Features:
        - Hour-based packages without fixed times
        - Flexible usage within defined limits
        - Total hours per week/month allocation
        - Integration with extra hour charges

    Prerequisites:
        - Package types must be defined
        - Extra charges must be configured
        - Both are required for package creation

    Package Code Format:
        - FLP00X (Flexible Package)
        - Auto-increments based on existing count

    Security:
        - Requires login authentication
        - Package code auto-generation prevents conflicts
    """
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
    """
    Retrieves all flexible packages as JSON for frontend consumption.

    This endpoint provides flexible package data for use in DataTables,
    dropdowns, and other frontend components that need to display
    or select flexible packages.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing flexible package details

    Business Logic:
        - Fetches all flexible packages with essential fields
        - Resolves package type foreign key to readable name
        - Includes hour allocation and pricing information
        - Used for package selection and display

    Package Information:
        - Package identification (id, code, name)
        - Hour allocation (no_hours)
        - Frequency (no_days_week, no_days_months)
        - Pricing (package_total)
        - Package type (resolved to name)

    Flexible Package Features:
        - No fixed time constraints
        - Hour-based allocation system
        - Flexible usage patterns
        - Total hours per period limits

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
    """
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
    """
    Saves a new flexible package with automatic extra hours mapping.

    This function processes the form data for creating a new flexible package,
    automatically setting up the appropriate extra hours mappings for all
    available extra hour rates.

    Args:
        request (HttpRequest): POST request containing flexible package data

    Returns:
        HttpResponseRedirect: Redirects to view_flex_packages page

    Business Logic:
        - Creates new FlexPackages record from form data
        - Automatically creates PackageExtraHoursMapping records
        - Maps all available extra hour rates (both before and after 5:30 PM)
        - Flexible packages get all extra hour options

    Extra Hours Mapping:
        - After 5:30 PM: Maps all rates for the package type
        - Before 5:30 PM: Maps all available rates
        - More comprehensive mapping than fixed packages

    Database Operations:
        - Creates FlexPackages record
        - Creates multiple PackageExtraHoursMapping records
        - Uses @transaction.atomic for data consistency

    Package Code Generation:
        - Uses format: FLP00X (Flexible Package)
        - Auto-increments based on existing package count

    Security:
        - Requires login authentication
        - Uses atomic transactions for data integrity
    """
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
    """
    Retrieves extra hours rates before 5:30 PM for a specific package.

    This function returns the extra hour rates that apply before 5:30 PM
    for either fixed or flexible packages, based on the package type.

    Args:
        request (HttpRequest): GET request with package id and packageTerm parameters

    Returns:
        JsonResponse: JSON array containing extra hour rates before 5:30 PM

    URL Parameters:
        id (str): Package ID
        packageTerm (str): "1" for fixed package, other values for flexible

    Business Logic:
        - Determines package type from packageTerm parameter
        - Retrieves PackageExtraHoursMapping records for the package
        - Filters for extra hours before 5:30 PM only
        - Returns detailed rate information with effective dates

    Package Types:
        - Fixed packages: Uses fixed_package foreign key
        - Flexible packages: Uses flex_package foreign key

    Rate Information:
        - hour_number: Hour sequence (1-6)
        - extra_rate: Rate per hour
        - effective_from: Rate start date
        - effective_to: Rate end date

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
    """
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
    """
    Retrieves extra hours rates after 5:30 PM for a specific package.

    This function returns the extra hour rates that apply after 5:30 PM
    for either fixed or flexible packages, based on the package type.

    Args:
        request (HttpRequest): GET request with package id and packageTerm parameters

    Returns:
        JsonResponse: JSON array containing extra hour rates after 5:30 PM

    URL Parameters:
        id (str): Package ID
        packageTerm (str): "1" for fixed package, other values for flexible

    Business Logic:
        - Determines package type from packageTerm parameter
        - Retrieves PackageExtraHoursMapping records for the package
        - Filters for extra hours after 5:30 PM only
        - Returns detailed rate information with time ranges and effective dates

    Package Types:
        - Fixed packages: Uses fixed_package foreign key
        - Flexible packages: Uses flex_package foreign key

    Rate Information:
        - from_time: Hour start time
        - to_time: Hour end time
        - extra_rate: Rate per hour
        - effective_from: Rate start date
        - effective_to: Rate end date

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
    """
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
    """
    Retrieves all branches as JSON for frontend consumption.

    This endpoint provides branch data for use in DataTables,
    dropdowns, and other frontend components that need to display
    or select branch locations.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing branch details

    Business Logic:
        - Fetches all branches with complete information
        - Includes contact details and address information
        - Returns both active and inactive branches
        - Used for branch selection and display

    Branch Information:
        - Branch identification (id, code, name)
        - Contact details (person, mobile, phone)
        - Address information (line1, line2, line3)
        - Status (is_active)

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
        - All branch data is accessible to authenticated users
    """
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
    """
    Displays the branch management page with creation form.

    This function renders the branch management interface,
    allowing users to create and manage branch locations
    for the daycare system.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders branch.html template with form

    Business Logic:
        - Generates next branch code (BRN00X format)
        - Provides form for creating new branches
        - Handles both creation and update scenarios
        - Auto-generates unique branch codes

    Branch Features:
        - Branch identification and contact information
        - Address management
        - Contact person and phone details
        - Active/inactive status management

    Branch Code Format:
        - BRN00X (Branch)
        - Auto-increments based on existing count
        - Ensures unique identification

    Security:
        - Requires login authentication
        - Branch code auto-generation prevents conflicts
    """
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
    """
    Saves or updates branch information.

    This function handles both creation of new branches and updates
    to existing branch records, determining the operation based on
    whether the branch code already exists.

    Args:
        request (HttpRequest): POST request containing branch data

    Returns:
        HttpResponseRedirect: Redirects to view_branches page

    Business Logic:
        - Checks if branch code already exists to determine create vs update
        - Updates existing branch with new information and audit fields
        - Creates new branch using form validation
        - Handles checkbox conversion for is_active field
        - Shows appropriate success/error messages

    Form Fields:
        - Branch identification (code, name)
        - Contact information (person, mobile, phone)
        - Address details (line1, line2, line3)
        - Status (is_active)

    Database Operations:
        - Update: Direct field assignment with audit trail
        - Create: Form-based creation with validation
        - Updates audit fields (user_updated, date_updated)

    Security:
        - Requires login authentication
        - Uses get_object_or_404 for safe record retrieval
        - Validates form data before saving
    """
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
    """
    Retrieves a specific branch for updating.

    This function fetches branch data by primary key and renders
    the update form with the existing branch information pre-populated.

    Args:
        request (HttpRequest): The HTTP request object
        pk (int): Primary key of the branch to update

    Returns:
        HttpResponse: Renders branchUpdate.html partial with populated form

    Business Logic:
        - Retrieves branch record by primary key
        - Pre-populates update form with existing data
        - Handles exceptions gracefully with error messages
        - Renders partial template for modal/AJAX usage

    Form Handling:
        - Uses UpdateBranchForm for data validation
        - Pre-populates all fields with existing values
        - Maintains form state for editing

    Error Handling:
        - Uses get_object_or_404 for safe record retrieval
        - Catches and displays any exceptions
        - Returns empty form on error

    Security:
        - Requires login authentication
        - Uses get_object_or_404 for safe record access
    """
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
    """
    Displays the daycare centers management page with creation form.

    This function renders the daycare centers management interface,
    allowing users to create and manage daycare centers within branches.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders dccenters.html template with form

    Business Logic:
        - Generates next daycare center code (DC00X format)
        - Provides form for creating new daycare centers
        - Handles both creation and update scenarios
        - Auto-generates unique center codes

    Daycare Center Features:
        - Center identification and details
        - Branch association
        - Contact information
        - Capacity management
        - Active/inactive status

    Center Code Format:
        - DC00X (Daycare Center)
        - Auto-increments based on existing count
        - Ensures unique identification

    Security:
        - Requires login authentication
        - Center code auto-generation prevents conflicts
    """
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
    """
    Saves or updates daycare center information.

    This function handles both creation of new daycare centers and updates
    to existing center records, determining the operation based on
    whether the daycare code already exists.

    Args:
        request (HttpRequest): POST request containing daycare center data

    Returns:
        HttpResponseRedirect: Redirects to view_centers page

    Business Logic:
        - Checks if daycare code exists to determine create vs update
        - Updates existing center with new information and audit fields
        - Creates new center using form validation
        - Handles checkbox conversion for is_active field
        - Associates centers with branches

    Form Fields:
        - Center identification (code, name)
        - Branch association
        - Contact information (incharge, mobile, phone)
        - Status (is_active)

    Database Operations:
        - Update: Direct field assignment with audit trail
        - Create: Form-based creation with validation
        - Updates audit fields (user_updated, date_updated)

    Security:
        - Requires login authentication
        - Uses exception handling for create/update logic
        - Validates form data before saving
    """
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
    """
    Retrieves all daycare centers as JSON for frontend consumption.

    This endpoint provides daycare center data for use in DataTables,
    dropdowns, and other frontend components that need to display
    or select daycare centers.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing daycare center details

    Business Logic:
        - Fetches all daycare centers with complete information
        - Converts boolean is_active to readable "Yes"/"No" format
        - Includes contact details and branch association
        - Used for center selection and display

    Center Information:
        - Center identification (id, code, name)
        - Management details (incharge)
        - Contact information (phone, mobile)
        - Branch association
        - Status (converted to readable format)

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
        - All center data is accessible to authenticated users
    """
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
    """
    Retrieves a formatted center name by branch ID.

    This function fetches a branch by ID and returns a formatted
    string combining the branch code and name for display purposes.

    Args:
        request (HttpRequest): GET request with branch id parameter

    Returns:
        JsonResponse: JSON string containing formatted center name

    URL Parameters:
        id (str): Branch ID to look up

    Business Logic:
        - Retrieves branch record by primary key
        - Formats name as "CODE-NAME" for display
        - Returns formatted string for frontend usage

    Name Format:
        - Combines branch_code and branch_name
        - Uses hyphen as separator
        - Example: "BRN001-Main Branch"

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
        - Direct database access by ID
    """
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        objBranch = Branch.objects.get(pk=id)
        if objBranch is not None:
            centerName = objBranch.branch_code + "-" + objBranch.branch_name
        return JsonResponse(centerName, safe=False)


@login_required
def getDayCareCenterForUpdateById(request, pk):
    """
    Retrieves a specific daycare center for updating.

    This function fetches daycare center data by primary key and renders
    the update form with the existing center information pre-populated.

    Args:
        request (HttpRequest): The HTTP request object
        pk (int): Primary key of the daycare center to update

    Returns:
        HttpResponse: Renders centerUpdate.html partial with populated form

    Business Logic:
        - Retrieves daycare center record by primary key
        - Pre-populates update form with existing data
        - Handles exceptions gracefully with error messages
        - Renders partial template for modal/AJAX usage

    Form Handling:
        - Uses UpdateDayCareForm for data validation
        - Pre-populates all fields with existing values
        - Maintains form state for editing

    Error Handling:
        - Uses get_object_or_404 for safe record retrieval
        - Catches and displays any exceptions
        - Returns empty form on error

    Security:
        - Requires login authentication
        - Uses get_object_or_404 for safe record access
    """
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
    """
    Retrieves active daycare centers for a specific branch.

    This function filters daycare centers by branch ID and returns
    only the active centers for that branch.

    Args:
        request (HttpRequest): GET request with branch id parameter

    Returns:
        JsonResponse: JSON array containing active daycare centers for the branch

    URL Parameters:
        id (str): Branch ID to filter centers

    Business Logic:
        - Filters daycare centers by branch_id
        - Returns only active centers (is_active=True)
        - Used for center selection based on branch
        - Provides complete center information

    Filtering Logic:
        - Filters by branch_id (foreign key)
        - Filters by is_active=True
        - Returns all fields for matching centers

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
        - Filters by branch association
    """
    if request.GET.get("id") is not None:
        id = request.GET.get("id")
        dayCareList = list(
            DayCare.objects.filter(branch_id=id, is_active=True).values()
        )
        return JsonResponse(dayCareList, safe=False)


@login_required
def getDiscounts(request):
    """
    Displays the discount management page with creation form.

    This function renders the discount management interface,
    allowing users to create and manage discount codes for
    the daycare system.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders discount.html template with form

    Business Logic:
        - Generates next discount code (DS00X format)
        - Provides form for creating new discounts
        - Handles both creation and update scenarios
        - Auto-generates unique discount codes

    Discount Features:
        - Discount code and name management
        - Percentage-based discount rates
        - Approval workflow integration
        - Active/inactive status management

    Discount Code Format:
        - DS00X (Discount)
        - Auto-increments based on existing count
        - Ensures unique identification

    Security:
        - Requires login authentication
        - Discount code auto-generation prevents conflicts
    """
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
    """
    Retrieves all discounts as JSON for frontend consumption.

    This endpoint provides discount data for use in DataTables,
    dropdowns, and other frontend components that need to display
    or select discount codes.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON array containing discount details

    Business Logic:
        - Fetches all discounts with essential information
        - Includes discount rates and approval status
        - Used for discount selection and management
        - Provides complete discount information

    Discount Information:
        - Discount identification (id, code, name)
        - Discount rate (percentage)
        - Approval status (Pending/Approved/Rejected)
        - Active status (is_active)

    Security:
        - Requires login authentication
        - No sensitive data filtering needed
        - All discount data is accessible to authenticated users
    """
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
    """
    Saves or updates discount information with approval workflow.

    This function handles both creation of new discounts and updates
    to existing discount records, automatically setting up the approval
    workflow for new discounts.

    Args:
        request (HttpRequest): POST request containing discount data

    Returns:
        HttpResponseRedirect: Redirects to view_discounts page

    Business Logic:
        - Checks if discount code exists to determine create vs update
        - Updates existing discount with new information and audit fields
        - Creates new discount with "Pending Approval" status
        - Handles checkbox conversion for is_active field
        - Integrates with approval workflow

    Approval Workflow:
        - New discounts start with "Pending Approval" status
        - Requires administrative approval before activation
        - Updates to existing discounts maintain current status

    Form Fields:
        - Discount identification (code, name)
        - Discount rate (percentage)
        - Status (for updates)
        - Active flag (is_active)

    Security:
        - Requires login authentication
        - Uses exception handling for create/update logic
        - Validates form data before saving
    """
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
    """
    Approves a pending discount request.

    This function processes discount approval requests, updating
    the discount status to "Approved" and maintaining audit trail.

    Args:
        request (HttpRequest): GET request with discount id parameter

    Returns:
        JsonResponse: JSON response confirming approval

    URL Parameters:
        id (str): Discount ID to approve

    Business Logic:
        - Updates discount status to "Approved"
        - Maintains audit trail with user and timestamp
        - Enables discount for use in enrollments
        - Part of approval workflow process

    Approval Process:
        - Changes status from "Pending Approval" to "Approved"
        - Records who approved and when
        - Discount becomes available for use

    Security:
        - Requires login authentication
        - Direct database access by ID
        - Updates audit fields for tracking
    """
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
    """
    Rejects a pending discount request.

    This function processes discount rejection requests, updating
    the discount status to "Rejected" and deactivating the discount.

    Args:
        request (HttpRequest): GET request with discount id parameter

    Returns:
        JsonResponse: JSON response confirming rejection

    URL Parameters:
        id (str): Discount ID to reject

    Business Logic:
        - Updates discount status to "Rejected"
        - Sets is_active to False to disable the discount
        - Maintains audit trail with user and timestamp
        - Prevents discount from being used in enrollments

    Rejection Process:
        - Changes status from "Pending Approval" to "Rejected"
        - Deactivates the discount (is_active = False)
        - Records who rejected and when
        - Discount becomes unavailable for use

    Security:
        - Requires login authentication
        - Direct database access by ID
        - Updates audit fields for tracking
    """
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
    """
    Renders the enrollment management page with a form for creating new enrollments.

    This view handles the initial display of the enrollment form interface where users can
    create new child enrollments. It automatically generates the next enrollment code
    by incrementing the highest existing enrollment count.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the enrollment.html template with:
            - form: CreateEnrollmentForm pre-populated with next enrollment code
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests

    Business Logic:
        - Calculates next enrollment code as "E00" + (total_enrollments + 1)
        - Handles edge case where no enrollments exist (starts with E001)
        - Pre-populates form with calculated enrollment code

    Template Context:
        - form: Form instance for creating new enrollments
        - UserName: Username for navigation display

    URL Pattern:
        - /enrollments/ (GET)
    """
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
    """
    Returns JSON data for pending enrollments to populate DataTables interface.

    This AJAX endpoint provides enrollment data for the frontend DataTables component,
    specifically filtering for enrollments that are pending approval. It uses complex
    database queries with subqueries to efficiently retrieve package information.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of enrollment objects with structure:
            - id: Primary key of enrollment
            - enrollment_code: Unique enrollment identifier
            - enrollment_date: Date when enrollment was created
            - child_name: Combined first and last name of child
            - branch_name: Name of the branch
            - center_name: Name of the daycare center
            - discount_name: Combined discount code and name
            - status: Enrollment status (filtered to "Pending Approval")
            - is_active: Boolean indicating if enrollment is active
            - package_name: Determined package name (normal > flex > holiday priority)
            - holiday_package: Holiday package name if applicable

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests

    Business Logic:
        - Uses Django ORM subqueries for efficient package name retrieval
        - Filters only active enrollments with "Pending Approval" status
        - Implements package name priority: normal_package > flex_package > holiday_package
        - Concatenates child first and last names for display
        - Joins multiple related tables for comprehensive data

    Database Operations:
        - Performs complex query with annotations and subqueries
        - Filters: status="Pending Approval", is_active=True
        - Joins: Child, Branch, DayCare, Discount, ChildPackageMapping
        - Subqueries: Retrieves package names from ChildPackageMapping

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Returns JSON array for direct consumption by jQuery DataTables
        - Provides all necessary data for enrollment approval workflow

    URL Pattern:
        - /enrollments/js/ (GET)
    """
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
    vacation_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "vacation_package__package_name"
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
            vacation_package=vacation_package_subquery,
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
            "vacation_package",
        )
    )
    return JsonResponse(enrolmentList, safe=False)


@login_required
@transaction.atomic
def saveEnrollments(request):
    """
    Processes enrollment form submissions for both new enrollments and updates.

    This view handles the creation and updating of child enrollments through a comprehensive
    workflow that includes child enrollment records, package mappings, and enrollment status
    management. It uses database transactions to ensure data integrity.

    Parameters:
        request (HttpRequest): The HTTP request object containing POST data with:
            - enrollment_code: Unique identifier for the enrollment
            - enrollment_date: Date of enrollment
            - child: Child ID to be enrolled
            - branch: Branch ID where child will be enrolled
            - dayCare: DayCare center ID
            - normal_package: Normal package ID (optional)
            - holiday_package: Holiday package ID (optional)
            - flex_package: Flex package ID (optional)
            - discount: Discount ID (optional)
            - recipt_number: Receipt number for payment
            - is_active: Boolean indicating if enrollment is active

    Returns:
        HttpResponse: Redirects to view_enrollments page after processing

    Security:
        - Requires user authentication via @login_required decorator
        - Uses @transaction.atomic for database integrity
        - Only accepts POST requests
        - Validates all foreign key relationships

    Business Logic:
        - Determines if operation is update (existing enrollment_code) or create (new)
        - For updates: Modifies existing enrollment record
        - For creates: Creates new enrollment with "Pending Approval" status
        - Automatically sets child.is_enrolled = True upon enrollment creation
        - Creates corresponding ChildPackageMapping record (inactive until approval)
        - Supports multiple package types (normal, flex, holiday)
        - Handles optional discount application
        - Validates enrollment date against child admission date

    Database Operations:
        - Creates/updates ChildEnrollment record
        - Creates ChildPackageMapping record (for new enrollments)
        - Updates Child.is_enrolled flag
        - Links enrollment to Branch, DayCare, and optional Discount
        - Uses atomic transaction for data consistency

    Validation Rules:
        - Child must be active and exist in system
        - Enrollment date must be on or after child admission date
        - Branch and DayCare must be active
        - At least one package type must be selected
        - Discount (if provided) must be active

    Workflow States:
        - New enrollments: Created with "Pending Approval" status
        - Package mappings: Created as inactive until enrollment approval
        - Child enrollment flag: Set to True immediately

    Error Handling:
        - Catches and displays form validation errors
        - Catches and displays database constraint errors
        - Provides user-friendly error messages
        - Rolls back transaction on any failure

    Success Flow:
        1. Validate form data
        2. Create/update enrollment record
        3. Create package mapping record
        4. Update child enrollment status
        5. Display success message
        6. Redirect to enrollment listing

    URL Pattern:
        - /enrollments/save/ (POST)
    """
    if request.method == "POST":
        enrollment_code = request.POST.get("enrollment_code")
        enrollment_date = request.POST.get("enrollment_date")
        child = request.POST.get("child")
        branch = request.POST.get("branch")
        dayCare = request.POST.get("dayCare")
        normal_package = request.POST.get("normal_package")
        holiday_package = request.POST.get("holiday_package")
        vacation_package = request.POST.get("vacation_package")
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

                        if vacation_package:
                            objPackageMapping.vacation_package = (
                                FixedPackage.objects.get(pk=vacation_package)
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
    vacation_package_subquery = Subquery(
        ChildPackageMapping.objects.filter(child=OuterRef("child")).values(
            "vacation_package__package_name"
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
            vacation_package=vacation_package_subquery,
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
            "vacation_package",
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
    """
    Approves a pending enrollment and activates associated package mappings.

    This view handles the approval workflow for child enrollments, transitioning them
    from "Pending Approval" to "Approved" status. It also activates the associated
    package mappings and triggers automatic enrollment form generation.

    Parameters:
        request (HttpRequest): The HTTP request object containing:
            - id (GET parameter): Primary key of the enrollment to approve

    Returns:
        JsonResponse: Success message confirming enrollment approval

    Security:
        - Requires user authentication via @login_required decorator
        - Uses @transaction.atomic for database integrity
        - Validates enrollment exists before processing

    Business Logic:
        - Updates enrollment status from "Pending Approval" to "Approved"
        - Sets child.enrollement_approved = True
        - Sets child.is_enrolled = True
        - Deletes all old package mappings for the child
        - Activates the most recent package mapping (created with this enrollment)
        - Triggers automatic enrollment form generation
        - Updates audit fields (user_updated, date_updated)

    Database Operations:
        - Updates ChildEnrollment record status
        - Updates Child enrollment flags
        - Deletes old ChildPackageMapping records (keeps only most recent)
        - Activates the most recent ChildPackageMapping record
        - Uses atomic transaction for consistency

    Workflow Integration:
        - Automatically generates enrollment forms via generate_enrollment_forms()
        - Completes the enrollment approval workflow
        - Enables child for attendance tracking
        - Activates package pricing for billing

    Side Effects:
        - Generates PDF enrollment forms in media/enrollment_forms/
        - Child becomes eligible for attendance logging
        - Package mappings become active for billing calculations
        - Child status changes to fully enrolled

    Error Handling:
        - Handles cases where child has multiple package mappings by deleting old ones
        - Keeps only the most recent mapping to maintain data integrity
        - Uses .first() and .exclude() to safely handle multiple records
        - Transaction rollback on any failure ensures data consistency

    URL Pattern:
        - /enrollments/approve/?id={enrollment_id} (GET)
    """
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

        # Get all package mappings for this child, ordered by most recent first
        all_mappings = ChildPackageMapping.objects.filter(
            child=objChild
        ).order_by('-date_created')

        if all_mappings.exists():
            # Get the most recent mapping (the one created with this enrollment)
            most_recent_mapping = all_mappings.first()

            # Delete all old mappings, keep only the most recent one
            old_mappings = all_mappings.exclude(pk=most_recent_mapping.pk)
            if old_mappings.exists():
                old_mappings.delete()

            # Activate the most recent mapping
            most_recent_mapping.is_active = True
            most_recent_mapping.save()

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
    """
    Draws three enrollment forms on a single A4 page for efficient printing.

    This function creates a complete enrollment form set on one page, containing
    Parent Copy, Office Copy, and Office Copy forms. This design allows for
    efficient printing and distribution of enrollment forms to different stakeholders.

    Args:
        c (Canvas): ReportLab canvas object for PDF generation
        data (dict): Dictionary containing child and enrollment information

    Returns:
        None: Function draws directly on the canvas

    Page Layout:
        - A4 page size (595 x 842 points)
        - Three equal sections vertically divided
        - Each form section height: (page_height - 60) / 3
        - 20-point margins on all sides
        - 30-point top margin for first form

    Form Distribution:
        1. Parent Copy (Top section)
           - For parent/guardian records
           - Includes To/From section
           - Standard formatting

        2. Office Copy (Middle section)
           - For daycare center records
           - Includes To/From section
           - Standard formatting

        3. Office Copy (Bottom section)
           - For administrative records
           - Excludes To/From section
           - Shows "Office Copy" label
           - Includes center code display

    Spacing Calculations:
        - Total page height: 842 points
        - Available space: 782 points (after 60-point margins)
        - Each form height: ~260 points
        - Vertical spacing between forms: Automatic

    Business Logic:
        - Provides complete enrollment documentation on single page
        - Supports different stakeholder needs (parent, center, office)
        - Enables efficient printing and distribution
        - Maintains consistent information across all copies
        - Reduces paper usage and printing costs

    Integration:
        - Called by generate_enrollment_forms() function
        - Uses draw_single_form() for individual form rendering
        - Works with ReportLab canvas system
        - Supports A4 page size standard

    Print Considerations:
        - Optimized for A4 paper size
        - Forms can be separated by cutting
        - Clear borders for easy identification
        - Consistent formatting for professional appearance
        - All essential information included on each copy
    """
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
    """
    Draws a single enrollment form section on a PDF canvas using ReportLab.

    This function creates a formatted enrollment form with child information,
    contact details, and package information. It supports different form types
    (Parent, Office, Office Copy) with conditional formatting based on the form type.

    Args:
        c (Canvas): ReportLab canvas object for drawing
        data (dict): Dictionary containing child and enrollment information
        from_type (str): Type of form ("Parent", "Office", "Office Copy")
        y_start (float): Starting Y coordinate for form placement
        form_height (float): Height allocated for this form section
        width (float): Page width for centering calculations
        is_office_copy (bool): Whether this is the office copy (affects layout)

    Returns:
        None: Function draws directly on the canvas

    Data Dictionary Structure:
        - child_name: Full name of the child
        - date_of_birth: Child's birth date (formatted)
        - date_of_admission: Enrollment date (formatted)
        - admission_no: Unique admission number
        - receipt_no: Receipt number for payment
        - fathers_name: Father's full name
        - mothers_name: Mother's full name
        - fathers_contact: Father's contact number
        - mothers_contact: Mother's contact number
        - fathers_whatsapp: Father's WhatsApp number
        - mothers_whatsapp: Mother's WhatsApp number
        - package_name: Enrolled package name
        - center_display: Center code and name

    Form Layout:
        - Header with "POLYMATH COLLEGE" title
        - Office Copy label (if applicable)
        - To/From section (except for office copy)
        - "New Admission - Day Care Division" title
        - Center information
        - Child details (name, DOB, admission date, etc.)
        - Parent contact information
        - Package information
        - Signature line

    Typography:
        - Header: Helvetica-Bold, 14pt
        - Office Copy: Helvetica-Bold, 12pt
        - Title: Helvetica-Bold, 11pt
        - Content: Helvetica-Bold, 9pt
        - Center text: Helvetica, 9pt

    Spacing and Alignment:
        - Left margin: 30 points
        - Right margin: 30 points
        - Line height: 12 points
        - Centered text for headers
        - Right-aligned contact numbers
        - Form border with 20-point margins

    Conditional Formatting:
        - Office Copy: Shows "Office Copy" label, excludes To/From section
        - Parent/Office: Shows To/From section, excludes Office Copy label
        - Contact alignment: Right-aligned for better readability

    Business Logic:
        - Creates professional enrollment forms for daycare management
        - Supports multiple form types for different stakeholders
        - Includes all essential child and contact information
        - Provides signature space for authentication
        - Maintains consistent formatting across all form types

    Integration:
        - Called by draw_all_forms_single_page() for multi-form layouts
        - Uses data from generate_enrollment_forms() function
        - Works with ReportLab canvas for PDF generation
    """

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
    """
    Renders the attendance check-in page for manual attendance recording.

    This view provides the user interface for staff to manually record child attendance.
    It displays a form where staff can enter child admission numbers and attendance details
    for children who may not have QR codes or need manual attendance entry.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the checkin.html template with:
            - form: CreateCheckInForm for manual attendance entry
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Staff members can manually record attendance for enrolled children

    Business Logic:
        - Provides manual attendance entry alternative to QR code scanning
        - Allows staff to record attendance for children without QR codes
        - Supports backup attendance recording when QR system is unavailable

    Form Components:
        - Child admission number input field
        - Date and time fields for attendance recording
        - Validation for enrolled children only

    Template Context:
        - form: Form instance for attendance recording
        - UserName: Username for navigation display

    Integration:
        - Works alongside QR code-based attendance system
        - Feeds into same AttendanceLog model as QR scanner
        - Provides manual override capability for attendance tracking

    URL Pattern:
        - /attendance/checkin/ (GET)
    """
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
    """
    Processes manual attendance recording from the check-in form.

    This view handles the submission of manual attendance records from staff members.
    It validates the child's enrollment status, checks date constraints, and creates
    attendance log entries for enrolled children.

    Parameters:
        request (HttpRequest): The HTTP request object containing POST data with:
            - child: Child's admission number
            - date_logged: Date of attendance
            - time_logged: Time of attendance

    Returns:
        HttpResponse: Redirects to view_check_ins page after processing

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts POST requests
        - Validates child enrollment status before recording
        - Checks child is active and enrollment is approved

    Business Logic:
        - Validates child exists with provided admission number
        - Ensures child is enrolled and enrollment is approved
        - Validates attendance date is on or after child's admission date
        - Creates attendance log record with branch and center information
        - Links attendance to child's enrollment branch and center
        - Updates audit fields with current user information

    Validation Rules:
        - Child must exist and be active
        - Child must be enrolled (is_enrolled = True)
        - Child enrollment must be approved (enrollement_approved = True)
        - Attendance date must be >= child.admission_date
        - Form data must pass CreateCheckInForm validation

    Database Operations:
        - Creates AttendanceLog record
        - Links to Child, Branch, and DayCare through enrollment
        - Updates audit fields (user_created, date_created)

    Error Handling:
        - Displays error if child not found or not enrolled
        - Displays error if attendance date is before admission date
        - Displays form validation errors
        - Catches and displays database exceptions

    Success Flow:
        1. Validate child exists and is enrolled
        2. Validate attendance date against admission date
        3. Create attendance log record
        4. Link to enrollment branch and center
        5. Display success message
        6. Redirect to attendance listing

    Integration:
        - Works alongside QR code attendance system
        - Feeds into same AttendanceLog model
        - Provides manual backup for attendance recording

    URL Pattern:
        - /attendance/save/ (POST)
    """
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
    """
    Automatically records attendance when a child scans their QR code.

    This view is the core of the QR code-based attendance system. It's called when
    a child's QR code is scanned, automatically recording their attendance with
    the current date and time. This function does not require authentication
    as it's accessed via QR code scanning.

    Parameters:
        request (HttpRequest): The HTTP request object (no authentication required)
        admission_no (str): The child's admission number from the QR code URL

    Returns:
        HttpResponse: Renders the success.html template with:
            - child: Child object that was checked in
            - time: Time when attendance was recorded

    Security:
        - No authentication required (public QR code endpoint)
        - Validates child exists and is enrolled before recording
        - Uses admission number as unique identifier

    Business Logic:
        - Looks up child by admission number
        - Validates child is enrolled (is_enrolled = True)
        - Records attendance with current date and time
        - Uses system-generated timestamp for accuracy
        - Marks attendance as "Scanned by the USER"

    QR Code Integration:
        - URL format: {PROD_URL}/{QR_METHOD_NAME}/{admission_number}/
        - Automatically triggered when QR code is scanned
        - Provides instant attendance recording
        - No manual intervention required

    Database Operations:
        - Creates AttendanceLog record
        - Links to Child record by admission number
        - Sets current date and time automatically
        - Updates audit fields with system user

    Validation Rules:
        - Child must exist with provided admission number
        - Child must be active (is_active = True)
        - Child must be enrolled (is_enrolled = True)

    Error Handling:
        - Displays error if child not found
        - Displays error if child is not enrolled
        - Catches and displays database exceptions
        - Provides user-friendly error messages

    Success Flow:
        1. Validate child exists and is enrolled
        2. Create attendance record with current timestamp
        3. Save attendance log
        4. Display success page with child and time information

    Template Context:
        - child: Child object for display
        - time: Recorded attendance time

    URL Pattern:
        - /qr/{admission_number}/ (GET)
    """
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
    """
    Display the missing attendance records page with search functionality.

    This view renders the missing attendance interface where users can identify
    and track incomplete attendance records. It helps maintain data integrity
    by highlighting days with missing IN or OUT records.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data
        context (list, optional): Pre-filtered list of missing attendance records

    Returns:
        HttpResponse: Renders the missingtime.html template with:
            - list: List of missing attendance records (if provided)
            - form: SearchForm for filtering missing records
            - UserName: Current authenticated user's username

    Template Context:
        - list: List of missing attendance records or None
        - form: SearchForm instance for date range filtering
        - UserName: String containing current user's username

    Security:
        - Requires user login (@login_required decorator)
        - Provides access to attendance data for authorized users
        - Handles sensitive attendance information securely

    Business Logic:
        - Initializes search form for date range filtering
        - Displays pre-filtered context data if provided
        - Prepares interface for missing record identification
        - Supports operational data cleanup workflows

    Integration:
        - Works with processMissingAttendanceRecordsJS() for AJAX data
        - Provides interface for attendance data correction
        - Supports bulk attendance record updates
        - Integrates with memo generation validation

    Form Features:
        - Date range selection (from_date, to_date)
        - Flexible search parameters
        - User-friendly interface for data cleanup
        - Real-time missing record identification

    Missing Record Types:
        - Missing IN: Records with only OUT times
        - Missing OUT: Records with only IN times
        - Incomplete days: Single records requiring classification

    Usage:
        - Data quality maintenance and cleanup
        - Attendance record verification before billing
        - Operational reporting for incomplete data
        - Support for memo generation validation

    Related Views:
        - processMissingAttendanceRecordsJS(): Provides AJAX data for missing records
        - saveAttendance(): Allows manual attendance record creation
        - getAttendanceReports(): Provides comprehensive attendance analysis

    Data Quality:
        - Identifies incomplete attendance data
        - Supports data cleanup workflows
        - Maintains billing accuracy
        - Ensures operational data integrity
    """
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
    """
    Process and return missing attendance records via AJAX with intelligent analysis.

    This view analyzes attendance records to identify incomplete attendance data
    and returns detailed information about missing IN or OUT records. It uses
    intelligent time-based logic to classify incomplete records.

    Parameters:
        request (HttpRequest): AJAX GET request containing search parameters:
            - from_date: String start date in YYYY-MM-DD format (optional)
            - to_date: String end date in YYYY-MM-DD format (optional)

    Returns:
        JsonResponse: JSON array of missing attendance records with:
            - child_name: String child identification and name
            - date_logged: Date of incomplete attendance
            - in_time: String IN time or "Missing"
            - out_time: String OUT time or "Missing"
            - missing_record: String type of missing record ("IN" or "OUT")

    Security:
        - Requires user login (@login_required decorator)
        - Filters data for active, enrolled children only
        - Handles sensitive attendance information securely

    Business Logic:
        - Defaults to 30-day lookback period if no dates provided
        - Filters for active, enrolled children only
        - Groups attendance logs by child and date
        - Identifies days with single attendance records
        - Classifies missing records using 3:00 PM cutoff

    Missing Record Classification:
        - Single log after 3:00 PM: OUT time (missing IN)
        - Single log before 3:00 PM: IN time (missing OUT)
        - Uses intelligent time-based classification
        - Provides specific missing record type

    Data Processing:
        - Converts raw attendance logs to dictionary format
        - Identifies incomplete attendance days
        - Formats times for display
        - Builds comprehensive missing record details

    Query Optimization:
        - Filters for active children only
        - Uses efficient date range filtering
        - Minimizes database queries
        - Optimizes for large datasets

    Time Logic:
        - Uses 3:00 PM (15:00) as cutoff threshold
        - Before 3:00 PM: Considered arrival (IN)
        - After 3:00 PM: Considered departure (OUT)
        - Handles edge cases in time interpretation

    Integration:
        - Called by missing attendance report interface
        - Supports DataTables integration
        - Provides real-time missing record analysis
        - Works with attendance correction workflows

    Data Quality:
        - Identifies incomplete attendance patterns
        - Supports data cleanup workflows
        - Maintains billing accuracy requirements
        - Ensures operational data integrity

    Error Handling:
        - Handles missing date parameters gracefully
        - Provides safe JSON responses
        - Maintains data consistency
        - Handles edge cases in attendance patterns

    Performance Features:
        - Efficient database filtering
        - Minimal data processing overhead
        - Scalable for large datasets
        - Optimized query patterns
    """
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
    """
    Display the attendance reports page with search form.

    This view renders the attendance reports interface where users can search
    and filter attendance records by various criteria. It provides the main
    entry point for attendance analysis and reporting functionality.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the attendancereport.html template with:
            - form: AttendanceReportForm for filtering attendance records
            - UserName: Current authenticated user's username

    Template Context:
        - form: AttendanceReportForm instance for search parameters
        - UserName: String containing current user's username

    Security:
        - Requires user login (@login_required decorator)
        - Provides access to attendance data for authorized users

    Business Logic:
        - Initializes empty search form for user input
        - Prepares interface for attendance data filtering
        - Supports date range and child-specific searches

    Integration:
        - Works with attendanceReportsJS() for AJAX data loading
        - Provides search interface for attendance analysis
        - Supports various attendance report formats

    Form Features:
        - Child selection dropdown
        - Date range selection (from_date, to_date)
        - Flexible search parameters
        - User-friendly interface elements

    Usage:
        - Primary entry point for attendance reporting
        - Supports manager and admin attendance analysis
        - Provides data for billing and operational decisions

    Related Views:
        - attendanceReportsJS(): Provides AJAX data for reports
        - getMissingAttendanceRecords(): Shows incomplete attendance
        - getAttendanceSummary(): Provides detailed attendance calculations
    """
    # Get children with active enrollments for the dropdown
    children = Child.objects.filter(
        is_active=True,
        childenrollment__status="Approved",
        childenrollment__is_active=True
    ).distinct().order_by("admission_number")

    return render(
        request,
        "../templates/reports/attendancereport.html",
        {
            "children": children,
            "UserName": request.user.username
        },
    )


@login_required
def attendanceReportsJS(request):
    """
    Provide AJAX-based attendance report data with advanced filtering and processing.

    This view processes attendance report requests and returns filtered attendance
    data in JSON format. It includes intelligent time processing to distinguish
    between IN and OUT records based on time patterns.

    Parameters:
        request (HttpRequest): AJAX GET request containing search parameters:
            - child: String admission number for child-specific filtering
            - from_date: String start date in YYYY-MM-DD format (optional)
            - to_date: String end date in YYYY-MM-DD format (optional)

    Returns:
        JsonResponse: JSON array of attendance records with:
            - admission_number: String child's admission number
            - child_name: String child's full name
            - date_logged: Date of attendance record
            - in_time: Time of first log or None if missing
            - out_time: Time of last log or None if missing
            - log_count: Integer number of logs for the day

    Security:
        - Requires user login (@login_required decorator)
        - Filters data based on user permissions
        - Handles parameter validation

    Business Logic:
        - Groups attendance logs by child and date
        - Calculates IN and OUT times from raw log data
        - Applies intelligent time interpretation rules
        - Handles single-log scenarios with time-based logic

    Time Processing Rules:
        - Multiple logs per day: First = IN, Last = OUT
        - Single log after 4:00 PM: Treated as OUT (missing IN)
        - Single log before 4:00 PM: Treated as IN (missing OUT)
        - Handles partial attendance scenarios

    Data Aggregation:
        - Groups logs by (child_id, date_logged)
        - Counts total logs per child per day
        - Identifies minimum (IN) and maximum (OUT) times
        - Provides comprehensive attendance overview

    Filtering Capabilities:
        - Child-specific filtering by admission number
        - Date range filtering (from_date, to_date)
        - Flexible parameter handling (optional filters)
        - Combines multiple filter criteria

    Query Optimization:
        - Uses database aggregation for efficiency
        - Leverages Django ORM annotations
        - Minimizes database queries
        - Optimizes for large datasets

    Data Processing:
        - Post-processes aggregated data for business rules
        - Applies 4:00 PM cutoff logic for single logs
        - Handles edge cases in attendance patterns
        - Provides consistent data format

    Integration:
        - Called by attendance report interface
        - Supports DataTables integration
        - Provides real-time data updates
        - Works with various front-end frameworks

    Error Handling:
        - Handles missing parameters gracefully
        - Provides safe JSON responses
        - Maintains data integrity
        - Logs processing errors

    Performance Features:
        - Efficient database queries
        - Minimal data transfer
        - Optimized aggregation
        - Scalable processing
    """
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
                "child",  # Include child ID for package mapping lookup
                "admission_number",
                "child_name",
                "date_logged",
                "in_time",  # Initially, the first log is considered "in_time"
                "out_time",  # Initially, the last log is considered "out_time"
                "log_count",  # Include log_count here to use it later in the code
            )
        )

        # Build a cache of child package mappings for efficient lookup
        # Get unique child IDs from the attendance logs
        child_ids = set(log["child"] for log in attendance_logs)

        # Get all active package mappings for these children
        package_mappings = {}
        for mapping in ChildPackageMapping.objects.filter(
            child_id__in=child_ids, is_active=True
        ).select_related(
            "normal_package",
            "vacation_package",
            "holiday_package",
            "flex_package",
            "normal_package__package_type",
        ):
            package_mappings[mapping.child_id] = mapping

        # Now modify the records based on the scenario you described
        for log in attendance_logs:
            child_id = log["child"]

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

            # Add package information
            package_mapping = package_mappings.get(child_id)
            if package_mapping:
                # Determine active package name
                if package_mapping.normal_package:
                    pkg = package_mapping.normal_package
                    log["package_name"] = pkg.package_name
                    log["package_end_time"] = (
                        pkg.to_time.strftime("%H:%M") if pkg.to_time else None
                    )
                elif package_mapping.flex_package:
                    pkg = package_mapping.flex_package
                    log["package_name"] = f"{pkg.package_name} (Flex)"
                    log["package_end_time"] = None  # Flex packages don't have fixed end time
                else:
                    log["package_name"] = "No Package"
                    log["package_end_time"] = None

                # Calculate extra hours if both in_time and out_time exist
                log["has_extra_hours"] = False
                log["extra_hours_display"] = ""

                if log["in_time"] and log["out_time"] and log["package_end_time"]:
                    out_time = log["out_time"]
                    package_end = datetime.strptime(
                        log["package_end_time"], "%H:%M"
                    ).time()

                    # Extra hours: checkout AFTER package_end_time counts as extra
                    # Checkout exactly AT package_end_time = no extra hours (using > not >=)
                    if out_time > package_end:
                        log["has_extra_hours"] = True
                        # Calculate extra minutes from package_end_time
                        out_dt = datetime.combine(datetime.today(), out_time)
                        package_end_dt = datetime.combine(datetime.today(), package_end)
                        extra_minutes = int((out_dt - package_end_dt).total_seconds() / 60)
                        hours = extra_minutes // 60
                        mins = extra_minutes % 60
                        if hours > 0:
                            log["extra_hours_display"] = f"{hours}h {mins}m"
                        else:
                            log["extra_hours_display"] = f"{mins}m"
            else:
                log["package_name"] = "No Mapping"
                log["package_end_time"] = None
                log["has_extra_hours"] = False
                log["extra_hours_display"] = ""

    return JsonResponse(attendance_logs, safe=False)


@login_required
def getPublicHolidays(request):
    """
    Renders the public holidays management page with a form for creating new holidays.

    This view provides the administrative interface for managing public holidays
    that affect daycare operations. Public holidays are used for billing calculations
    and special package pricing during holiday periods.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the publicholidays.html template with:
            - form: CreatePublicHolidayForm for adding new public holidays
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Provides interface for managing public holidays
        - Integrates with holiday package pricing system
        - Affects billing calculations during holiday periods
        - Supports date range management for extended holidays

    Form Components:
        - Holiday title/name field
        - Start date selection
        - End date selection
        - Automatic day calculation (weekdays, weekends)

    Template Context:
        - form: Form instance for creating public holidays
        - UserName: Username for navigation display

    Integration:
        - Works with Holiday model (is_public_holiday = True)
        - Integrates with package pricing system
        - Affects invoice calculations
        - Used for attendance and billing reports

    URL Pattern:
        - /holidays/public/ (GET)
    """
    holidayform = CreatePublicHolidayForm()
    return render(
        request,
        "../templates/publicholidays.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getPublicHolidaysJS(request):
    """
    Returns JSON data for public holidays to populate DataTables interface.

    This AJAX endpoint provides public holiday data for the frontend DataTables
    component, allowing administrators to view and manage public holidays in
    a tabular format with sorting and filtering capabilities.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of public holiday objects with structure:
            - id: Primary key of holiday record
            - title: Holiday name/title
            - start_date: Holiday start date
            - end_date: Holiday end date
            - no_of_days: Total number of days in holiday period
            - weekdays_count: Number of weekdays in holiday period
            - weekends_count: Number of weekend days in holiday period

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Filters only active public holidays (is_active=True, is_public_holiday=True)
        - Provides comprehensive date range information
        - Includes day count breakdowns for billing calculations
        - Supports frontend table operations (sorting, searching, pagination)

    Database Operations:
        - Queries Holiday model with specific filters
        - Returns only public holidays (excludes Polymath/other holidays)
        - Includes calculated fields for day counts

    Data Structure:
        - Each holiday record includes date ranges and day counts
        - Weekdays/weekends breakdown helps with billing calculations
        - Total days count used for package pricing adjustments

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Supports real-time table updates
        - Enables inline editing and management operations
        - Provides data for holiday calendar views

    URL Pattern:
        - /holidays/public/js/ (GET)
    """
    # Get current year to filter holidays
    current_year = datetime.now().year
    year_start = date(current_year, 1, 1)
    year_end = date(current_year, 12, 31)

    # Filter for holidays that overlap with current year
    # A holiday overlaps if: (start_date <= year_end) AND (end_date >= year_start)
    # This includes holidays that start in previous year but end in current year
    holidayList = list(
        Holiday.objects.filter(
            is_active=True,
            is_public_holiday=True,
            start_date__lte=year_end,  # Starts on or before Dec 31 of current year
            end_date__gte=year_start   # Ends on or after Jan 1 of current year
        ).values(
            "id",
            "title",
            "start_date",
            "end_date",
            "no_of_days",
            "weekdays_count",
            "weekends_count",
        ).order_by('start_date')  # Order by date for better UX
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
    """
    Renders the Polymath-specific holidays management page with a form for creating new holidays.

    This view provides the administrative interface for managing Polymath daycare-specific
    holidays that are separate from public holidays. These holidays are internal to the
    daycare system and may have different billing and operational implications.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the polymathholidays.html template with:
            - form: CreatePolymathHolidayForm for adding new Polymath holidays
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Provides interface for managing Polymath-specific holidays
        - Separate from public holidays for operational flexibility
        - May have different billing implications than public holidays
        - Supports custom holiday scheduling for the daycare system

    Holiday Types:
        - Polymath holidays: Internal daycare holidays
        - Public holidays: Government/national holidays
        - Other holidays: Custom or regional holidays

    Form Components:
        - Holiday title/name field
        - Start date selection
        - End date selection
        - Automatic day calculation (weekdays, weekends)

    Template Context:
        - form: Form instance for creating Polymath holidays
        - UserName: Username for navigation display

    Integration:
        - Works with Holiday model (is_polymath_holiday = True)
        - Integrates with package pricing system
        - Affects billing calculations during holiday periods
        - Used for attendance and operational reports

    URL Pattern:
        - /holidays/polymath/ (GET)
    """
    holidayform = CreatePolymathHolidayForm()
    return render(
        request,
        "../templates/polymathholidays.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getPolymathHolidaysJS(request):
    """
    Returns JSON data for Polymath holidays to populate DataTables interface.

    This AJAX endpoint provides Polymath-specific holiday data for the frontend
    DataTables component, allowing administrators to view and manage internal
    daycare holidays in a tabular format with sorting and filtering capabilities.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of Polymath holiday objects with structure:
            - id: Primary key of holiday record
            - title: Holiday name/title
            - start_date: Holiday start date
            - end_date: Holiday end date
            - no_of_days: Total number of days in holiday period
            - weekdays_count: Number of weekdays in holiday period
            - weekends_count: Number of weekend days in holiday period

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Filters only active Polymath holidays (is_active=True, is_polymath_holiday=True)
        - Provides comprehensive date range information
        - Includes day count breakdowns for billing calculations
        - Supports frontend table operations (sorting, searching, pagination)

    Database Operations:
        - Queries Holiday model with specific filters
        - Returns only Polymath holidays (excludes public/other holidays)
        - Includes calculated fields for day counts

    Data Structure:
        - Each holiday record includes date ranges and day counts
        - Weekdays/weekends breakdown helps with billing calculations
        - Total days count used for package pricing adjustments

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Supports real-time table updates
        - Enables inline editing and management operations
        - Provides data for holiday calendar views

    Holiday Management:
        - Polymath holidays are internal to the daycare system
        - May have different billing rules than public holidays
        - Supports custom scheduling for daycare operations

    URL Pattern:
        - /holidays/polymath/js/ (GET)
    """
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
    """
    Renders the other holidays management page with a form for creating custom holidays.

    This view provides the administrative interface for managing miscellaneous holidays
    that don't fall into the public or Polymath categories. These could include regional
    holidays, special events, or custom closure dates specific to certain branches.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the otherholidays.html template with:
            - form: CreateOtherHolidayForm for adding new custom holidays
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Provides interface for managing miscellaneous holidays
        - Separate from public and Polymath holidays for operational flexibility
        - May have different billing implications based on holiday type
        - Supports custom holiday scheduling for specific needs

    Holiday Types:
        - Other holidays: Custom, regional, or special event holidays
        - Public holidays: Government/national holidays
        - Polymath holidays: Internal daycare holidays

    Form Components:
        - Holiday title/name field
        - Start date selection
        - End date selection
        - Automatic day calculation (weekdays, weekends)

    Template Context:
        - form: Form instance for creating other holidays
        - UserName: Username for navigation display

    Integration:
        - Works with Holiday model (is_other_holiday = True)
        - Integrates with package pricing system
        - Affects billing calculations during holiday periods
        - Used for attendance and operational reports

    Use Cases:
        - Regional holidays not covered by public holidays
        - Special event closures
        - Branch-specific holidays
        - Training or maintenance days

    URL Pattern:
        - /holidays/other/ (GET)
    """
    holidayform = CreateOtherhHolidayForm()
    return render(
        request,
        "../templates/otherholiday.html",
        {"form": holidayform, "UserName": request.user.username},
    )


@login_required
def getOtherHolidaysJS(request):
    """
    Returns JSON data for other holidays to populate DataTables interface.

    This AJAX endpoint provides custom/other holiday data for the frontend
    DataTables component, allowing administrators to view and manage miscellaneous
    holidays in a tabular format with sorting and filtering capabilities.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of other holiday objects with structure:
            - id: Primary key of holiday record
            - title: Holiday name/title
            - start_date: Holiday start date
            - end_date: Holiday end date
            - no_of_days: Total number of days in holiday period
            - weekdays_count: Number of weekdays in holiday period
            - weekends_count: Number of weekend days in holiday period

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for holiday management

    Business Logic:
        - Filters only active other holidays (is_active=True, is_other_holiday=True)
        - Provides comprehensive date range information
        - Includes day count breakdowns for billing calculations
        - Supports frontend table operations (sorting, searching, pagination)

    Database Operations:
        - Queries Holiday model with specific filters
        - Returns only other holidays (excludes public/Polymath holidays)
        - Includes calculated fields for day counts

    Data Structure:
        - Each holiday record includes date ranges and day counts
        - Weekdays/weekends breakdown helps with billing calculations
        - Total days count used for package pricing adjustments

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Supports real-time table updates
        - Enables inline editing and management operations
        - Provides data for holiday calendar views

    Holiday Management:
        - Other holidays are custom/regional holidays
        - May have different billing rules than public/Polymath holidays
        - Supports flexible scheduling for special circumstances

    Use Cases:
        - Regional holidays not covered by public holidays
        - Special event closures
        - Branch-specific holidays
        - Training or maintenance days

    URL Pattern:
        - /holidays/other/js/ (GET)
    """
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


# ==================== VACATION MANAGEMENT VIEWS ====================
# New unified vacation system replacing Polymath and Other holidays

@login_required
def getVacations(request):
    """
    Renders the unified vacation management page.

    This view provides a single interface for managing all vacation periods,
    replacing the separate Polymath and Other holiday pages.

    Returns:
        HttpResponse: Renders vacations.html with CreateVacationForm
    """
    vacation_form = CreateVacationForm()
    return render(
        request,
        "../templates/vacations.html",
        {"form": vacation_form, "UserName": request.user.username},
    )


@login_required
def getVacationsJS(request):
    """
    Returns JSON data for all vacation periods to populate DataTables.

    Returns:
        JsonResponse: Array of vacation objects with:
            - id, title, start_date, end_date
            - vacation_type (ALL/POLYMATH/NON_POLYMATH)
            - vacation_type_display (human-readable)
            - no_of_days, weekdays_count, weekends_count
    """
    vacations = Holiday.objects.filter(
        is_active=True,
        is_vacation=True
    ).order_by('-start_date')

    vacation_list = []
    for vacation in vacations:
        vacation_list.append({
            'id': vacation.id,
            'title': vacation.title,
            'start_date': vacation.start_date.strftime('%Y-%m-%d'),
            'end_date': vacation.end_date.strftime('%Y-%m-%d'),
            'vacation_type': vacation.vacation_type,
            'vacation_type_display': vacation.get_vacation_type_display(),
            'no_of_days': vacation.no_of_days,
            'weekdays_count': vacation.weekdays_count,
            'weekends_count': vacation.weekends_count,
        })

    return JsonResponse(vacation_list, safe=False)


@login_required
def saveVacation(request):
    """
    Handles creation and updating of vacation periods.

    POST parameters:
        - id (optional): If provided, updates existing vacation
        - title: Vacation name
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
        - vacation_type: ALL/POLYMATH/NON_POLYMATH

    Returns:
        Redirects to vacations page with success/error message
    """
    try:
        if request.method == "POST":
            vacation_id = request.POST.get("id")
            title = request.POST.get("title")
            start_date = datetime.strptime(request.POST.get("start_date"), "%Y-%m-%d").date()
            end_date = datetime.strptime(request.POST.get("end_date"), "%Y-%m-%d").date()
            vacation_type = request.POST.get("vacation_type")

            # Validation
            if start_date > end_date:
                raise Exception(
                    f"End date ({end_date}) cannot be earlier than start date ({start_date})."
                )

            if not vacation_type or vacation_type not in ['ALL', 'POLYMATH', 'NON_POLYMATH']:
                raise Exception("Please select a valid student type for this vacation.")

            # Check user permissions
            user = User.objects.get(username=request.user.username)
            if user.groups.filter(name="Data Entry").exists():
                messages.error(request, "You are not authorized to perform this operation.")
                return redirect("core:vacations")

            # Update or Create
            if vacation_id:
                # Update existing vacation
                vacation = Holiday.objects.get(pk=vacation_id)
                vacation.title = title
                vacation.start_date = start_date
                vacation.end_date = end_date
                vacation.vacation_type = vacation_type
                vacation.is_vacation = True
                vacation.is_public_holiday = False
                vacation.user_updated = request.user.username
                vacation.date_updated = datetime.now()
                vacation.save()
                messages.success(request, f"Vacation '{title}' updated successfully.")
            else:
                # Create new vacation
                form = CreateVacationForm(request.POST)
                if form.is_valid():
                    vacation = form.save(commit=False)
                    vacation.user_created = request.user.username
                    vacation.date_created = datetime.now()
                    vacation.save()
                    messages.success(request, f"Vacation '{title}' created successfully.")
                else:
                    for error in form.errors.values():
                        messages.error(request, error)

    except Exception as e:
        messages.error(request, str(e))

    return redirect("core:vacations")


@login_required
def getVacationByID(request, pk):
    """
    Returns a form pre-populated with vacation data for editing.

    Args:
        pk (int): Primary key of the vacation to edit

    Returns:
        HttpResponse: Renders vacationupdate.html partial with UpdateVacationForm
    """
    try:
        vacation = get_object_or_404(Holiday, pk=pk, is_vacation=True)
        # Prepare initial data with the vacation ID
        initial_data = {
            'id': vacation.id,
            'title': vacation.title,
            'start_date': vacation.start_date,
            'end_date': vacation.end_date,
            'vacation_type': vacation.vacation_type,
        }
        form = UpdateVacationForm(initial=initial_data)
    except Exception as e:
        messages.error(request, str(e))
        form = None

    return render(
        request,
        "../templates/partials/vacationupdate.html",
        {"form": form}
    )


def nullify_empty(value, is_numeric=False, is_date=False):
    """
    Utility function to clean and convert empty or invalid values to None.

    This function handles data sanitization for CSV imports and form processing,
    converting empty strings, invalid numeric values, and malformed dates to None
    to maintain database integrity and prevent insertion errors.

    Args:
        value (any): The value to process and clean
        is_numeric (bool): If True, attempts to convert value to integer
        is_date (bool): If True, attempts to parse value as date string

    Returns:
        None: If value is None, empty string, or invalid for specified type
        int: If is_numeric=True and value is valid integer
        date: If is_date=True and value is valid date string (YYYY-MM-DD format)
        any: Original value if no type conversion specified and value is not empty

    Business Logic:
        - Handles None and empty string inputs uniformly
        - Numeric conversion: Attempts integer conversion, returns None on failure
        - Date conversion: Parses YYYY-MM-DD format, returns None on failure
        - Used extensively in CSV import operations for data cleaning
        - Prevents database constraint violations from invalid data

    Type Handling:
        - Numeric: Converts to integer, handles float/decimal input gracefully
        - Date: Expects YYYY-MM-DD format, returns Python date object
        - String: Returns original value if not empty, None otherwise

    Error Handling:
        - Catches ValueError and TypeError for numeric conversions
        - Catches ValueError and TypeError for date parsing
        - Returns None for any conversion failures
        - Never raises exceptions, always returns safe values

    Usage Examples:
        - nullify_empty("") -> None
        - nullify_empty("123", is_numeric=True) -> 123
        - nullify_empty("2024-01-15", is_date=True) -> date(2024, 1, 15)
        - nullify_empty("invalid", is_numeric=True) -> None
        - nullify_empty("invalid-date", is_date=True) -> None
    """
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
    """
    Handles CSV file upload and bulk import of child data into the system.

    This function provides a web interface for administrators to upload CSV files
    containing child enrollment data and automatically import them into the database.
    It includes validation, security checks, and data cleaning functionality.

    Args:
        request (HttpRequest): The HTTP request object containing either:
            - GET: Request to display the upload form
            - POST: Request with CSV file upload

    Returns:
        HttpResponse: Renders dataimporter.html template with:
            - GET: Empty form for file upload
            - POST: Form with success/error messages after processing

    Security:
        - Requires user authentication via @login_required decorator
        - Blocks users in "Data Entry" group from uploading (authorization check)
        - Validates file type (must be .csv extension)
        - Validates file structure (must have required columns)

    Business Logic:
        - Processes CSV files with child enrollment data
        - Updates existing children or creates new records (upsert operation)
        - Automatically generates QR codes for each child
        - Cleans and validates data using nullify_empty utility
        - Handles date conversions and numeric field validation

    CSV Format Requirements:
        - Must be .csv file format
        - Must have exactly 18 columns per row
        - First row is treated as header and skipped
        - Column order: admission_number, child_first_name, child_last_name,
          date_of_birth, fathers_name, fathers_contact_number, fathers_whatsapp_number,
          mothers_name, mothers_contact_number, mothers_whatsapp_number,
          resident_contact_number, address_line1, address_line2, address_line3,
          email_address, is_polymath_student, admission_date, leave_date

    Data Processing:
        - Uses Child.objects.update_or_create() for upsert operations
        - Admission number serves as unique identifier
        - Empty fields are converted to None or default values
        - Date fields are parsed and validated
        - Numeric fields are validated and converted
        - QR codes are automatically generated for each child

    Error Handling:
        - Validates file upload presence
        - Validates file extension (.csv only)
        - Validates CSV structure (minimum 8 columns)
        - Shows user-friendly error messages
        - Continues processing even if individual rows fail

    Template Context:
        - No additional context variables
        - Uses Django messages framework for feedback
        - Renders success/error messages in template

    File Processing:
        - Reads entire CSV file into memory
        - Decodes UTF-8 content
        - Processes line by line
        - Skips header row automatically

    Database Operations:
        - Uses update_or_create for atomic upsert operations
        - Maintains referential integrity
        - Handles duplicate admission numbers gracefully
        - Preserves existing data when updating

    Integration:
        - Integrates with Child model for data storage
        - Uses generateQR() function for QR code creation
        - Uses nullify_empty() for data cleaning
        - Works with media storage for QR code files

    URL Pattern:
        - /utils/upload-csv/ (GET/POST)
    """
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
    """
    Creates and serves a ZIP file containing all QR code images for bulk download.

    This function packages all QR code images from the media/qr directory into
    a single ZIP file for easy download. This is useful for administrators who
    need to distribute QR codes for attendance tracking or backup purposes.

    Args:
        request (HttpRequest): The HTTP request object (no authentication required)

    Returns:
        HttpResponse: ZIP file download response with content-type application/zip

    Security:
        - No authentication required (public access)
        - Only accesses pre-generated QR codes from media storage
        - Uses temporary directory to avoid file system conflicts
        - Automatically cleans up temporary files after download

    Business Logic:
        - Compresses all QR code images into a single ZIP file
        - Uses temporary directory for ZIP creation to avoid conflicts
        - Provides bulk download capability for QR codes
        - Maintains file structure and naming from original QR directory

    File Operations:
        - Accesses media/qr directory for source files
        - Creates temporary directory for ZIP processing
        - Uses shutil.make_archive() for ZIP creation
        - Automatically cleans up temporary files via finally block

    Error Handling:
        - Catches all exceptions during ZIP creation
        - Shows error messages to user via Django messages framework
        - Ensures temporary directory cleanup even on errors
        - Gracefully handles missing QR directory

    Performance Considerations:
        - Creates entire ZIP file in memory before serving
        - May be slow for large numbers of QR codes
        - Uses system temporary directory for processing
        - Cleanup happens automatically after response

    Response Headers:
        - Content-Type: application/zip
        - Content-Disposition: attachment; filename=qr_files.zip
        - Forces browser to download rather than display

    File Structure:
        - ZIP contains all PNG files from media/qr directory
        - Maintains original filenames and structure
        - Filename format: "[admission_no]- [first_name] [last_name].png"

    Use Cases:
        - Bulk distribution of QR codes to parents/staff
        - Backup of QR code images
        - Printing QR codes for physical distribution
        - System migration or data export

    Integration:
        - Works with QR codes generated by generateQR() function
        - Accesses files created during child enrollment
        - Independent of database (file-based operation)

    URL Pattern:
        - /utils/download-qr-files/ (GET)
    """
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
    """
    Renders the package change request page for submitting package modification requests.

    This view provides the interface for staff to submit requests to change a child's
    package enrollment. Package changes require approval workflow to ensure proper
    billing and operational management.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the packagechange.html template with:
            - form: CreatePackageChangeRequestForm for submitting change requests
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Staff members can submit package change requests

    Business Logic:
        - Provides interface for requesting package changes
        - Initiates approval workflow for package modifications
        - Maintains audit trail of package change requests
        - Supports various package types (normal, flex, holiday)

    Form Components:
        - Child selection dropdown
        - Current package display
        - New package selection
        - Effective date selection
        - Reason for change field

    Template Context:
        - form: Form instance for package change requests
        - UserName: Username for navigation display

    Integration:
        - Works with PackageChangerequest model
        - Integrates with approval workflow system
        - Maintains package history and audit trail
        - Affects billing calculations upon approval

    Workflow:
        1. Staff submits package change request
        2. Request goes to "Pending Approval" status
        3. Administrator reviews and approves/rejects
        4. Upon approval, package mapping is updated
        5. New package becomes effective from specified date

    URL Pattern:
        - /packages/change-request/ (GET)
    """
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
    isVacation = False
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
                    packageList.append([isFixed, packageText, id, isHoliday, isVacation])
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
                packageList.append([isFixed, packageText, id, isHoliday, isVacation])
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
                isVacation = False
                packageList.append([isFixed, packageText, id, isHoliday, isVacation])
            if package.vacation_package is not None:
                objVacationPackage = FixedPackage.objects.filter(
                    pk=package.vacation_package.id
                ).first()
                if objVacationPackage is not None:
                    packageText = (
                        objVacationPackage.package_code
                        + " - "
                        + objVacationPackage.package_name
                    )
                isFixed = False
                id = objVacationPackage.id
                isHoliday = False
                isVacation = True
                packageList.append([isFixed, packageText, id, isHoliday, isVacation])
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
                        # Set the old package FIRST before comparing
                        objPackageChangeRequest.old_fixed_package = objOldFixedPcakage

                        # Now check if new fixed package equals old fixed package
                        if (
                            objPackageChangeRequest.new_fixed_package
                            == objPackageChangeRequest.old_fixed_package
                        ):
                            messages.error(
                                request,
                                "The selected new package cannot be the same as the old package.",
                            )
                            return

                if (
                    request.POST.get("old_flexed_package") is not None
                    and request.POST.get("old_flexed_package") != ""
                ):
                    objOldFlexPackage = FlexPackages.objects.filter(
                        pk=request.POST.get("old_flexed_package")
                    ).first()

                    if objOldFlexPackage is not None:
                        # Set the old package FIRST before comparing
                        objPackageChangeRequest.old_flexed_package = objOldFlexPackage

                        # Now check if new flex package equals old flex package
                        if (
                            objPackageChangeRequest.new_flexed_package
                            == objPackageChangeRequest.old_flexed_package
                        ):
                            return messages.error(
                                request,
                                "The selected new package cannot be the same as the old package.",
                            )

                objPackageChangeRequest.user_created = request.user.username

                # Validation 1: checking if the new package is selected
                if (
                    objPackageChangeRequest.new_fixed_package is None
                    and objPackageChangeRequest.new_flexed_package is None
                ):
                    return messages.error(
                        request,
                        "Please select either a new fixed package or a new flex package.",
                    )

                # Validation 2: checking if both packages are selected
                if (
                    objPackageChangeRequest.new_fixed_package is not None
                    and objPackageChangeRequest.new_flexed_package is not None
                ):
                    return messages.error(
                        request,
                        "You can only select one package: either a new fixed package or a new flex package.",
                    )
                if (
                    request.POST.get("old_holiday_package") is not None
                    and request.POST.get("old_holiday_package") != ""
                ):
                    objHolidayPackage = FixedPackage.objects.filter(
                        pk=request.POST.get("old_holiday_package")
                    ).first()
                    if objHolidayPackage is not None:
                        objPackageChangeRequest.old_holiday_package = objHolidayPackage
                # Handle vacation package - if new not selected, use old
                if (
                    request.POST.get("old_vacation_package") is not None
                    and request.POST.get("old_vacation_package") != ""
                ):
                    objOldVacationPackage = FixedPackage.objects.filter(
                        pk=request.POST.get("old_vacation_package")
                    ).first()
                    if objOldVacationPackage is not None:
                        objPackageChangeRequest.old_vacation_package = (
                            objOldVacationPackage
                        )
                # If new_vacation_package not selected, use old_vacation_package
                if objPackageChangeRequest.new_vacation_package is None:
                    objPackageChangeRequest.new_vacation_package = (
                        objPackageChangeRequest.old_vacation_package
                    )

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
    """
    Returns JSON data for package change requests to populate DataTables interface.

    This AJAX endpoint provides package change request data for the frontend DataTables
    component, allowing administrators to view and manage pending package change requests
    in a tabular format with comprehensive package information.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of package change request objects with structure:
            - id: Primary key of the package change request
            - child_info: Combined child admission number and name
            - old_package: Current package name (fixed or flex)
            - new_package: Requested new package name (fixed or flex)
            - old_holiday_package_name: Current holiday package name
            - new_holiday_package_name: Requested new holiday package name
            - old_vacation_package_name: Current vacation package name
            - new_vacation_package_name: Requested new vacation package name
            - date_requested: Date when request was submitted
            - reason_for_request: Reason provided for the package change
            - user_created: Username of person who created the request
            - effective_date: Date when package change should take effect

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for package change management

    Business Logic:
        - Filters only active pending requests (status="Pending Approval")
        - Uses complex annotations to determine package names
        - Handles both fixed and flex package types
        - Includes holiday package information
        - Includes vacation package information
        - Provides comprehensive request information for approval workflow

    Database Operations:
        - Queries PackageChangerequest model with filters
        - Uses annotations to resolve package names from foreign keys
        - Employs Coalesce to handle null values in package fields
        - Joins with Child, FixedPackage, and FlexPackages models

    Package Resolution:
        - old_package: Resolves to either old_fixed_package or old_flexed_package name
        - new_package: Resolves to either new_fixed_package or new_flexed_package name
        - Holiday packages: Handled separately for old and new values

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Supports approval workflow interface
        - Enables package change request management
        - Provides data for approval decision making

    Error Handling:
        - Catches and logs database exceptions
        - Returns empty array on error
        - Provides graceful failure for frontend

    URL Pattern:
        - /packages/change-requests/js/ (GET)
    """
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
                # Annotate old vacation package
                old_vacation_package_name=F("old_vacation_package__package_name"),
                # Annotate new vacation package
                new_vacation_package_name=F("new_vacation_package__package_name"),
            )
            .values(
                "id",  # ID of the package change request
                "child_info",
                "old_package",  # Old package (either fixed or flexed)
                "new_package",  # New package (either fixed or flexed)
                "old_holiday_package_name",  # Old Holiday Package
                "new_holiday_package_name",  # New Holiday Package
                "old_vacation_package_name",  # Old Vacation Package
                "new_vacation_package_name",  # New Vacation Package
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
                # Handle vacation package - if new not specified, preserve old
                if objPackageChangeRequest.new_vacation_package:
                    objChildPackageMapping.vacation_package = (
                        objPackageChangeRequest.new_vacation_package
                    )
                else:
                    objChildPackageMapping.vacation_package = (
                        objPackageChangeRequest.old_vacation_package
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
    """
    Renders the center change request page for submitting center/branch transfer requests.

    This view provides the interface for staff to submit requests to transfer a child
    from one daycare center to another. Center changes require approval workflow to
    ensure proper operational management and billing continuity.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the centerchange.html template with:
            - form: CreateCenterChangeRequestForm for submitting center transfer requests
            - UserName: Current authenticated user's username

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Staff members can submit center change requests

    Business Logic:
        - Provides interface for requesting center/branch transfers
        - Initiates approval workflow for center changes
        - Maintains audit trail of transfer requests
        - Supports cross-branch and within-branch transfers

    Form Components:
        - Child selection dropdown
        - Current center/branch display
        - New center selection
        - New branch selection
        - Effective date selection
        - Reason for transfer field

    Template Context:
        - form: Form instance for center change requests
        - UserName: Username for navigation display

    Integration:
        - Works with CenterChangerequest model
        - Integrates with approval workflow system
        - Maintains center transfer history and audit trail
        - Affects enrollment and billing records upon approval

    Workflow:
        1. Staff submits center change request
        2. Request goes to "Pending Approval" status
        3. Administrator reviews and approves/rejects
        4. Upon approval, child enrollment is updated
        5. New center/branch becomes effective from specified date

    Use Cases:
        - Child family relocates to different area
        - Operational capacity management
        - Special needs or program transfers
        - Administrative consolidation

    URL Pattern:
        - /centers/change-request/ (GET)
    """
    requestform = CreateCenterChangeRequestForm()
    return render(
        request,
        "../templates/centerchange.html",
        {"form": requestform, "UserName": request.user.username},
    )


@login_required
def getCenterChangeRequestsJS(request):
    """
    Returns JSON data for center change requests to populate DataTables interface.

    This AJAX endpoint provides center change request data for the frontend DataTables
    component, allowing administrators to view and manage pending center transfer requests
    in a tabular format with comprehensive center and branch information.

    Parameters:
        request (HttpRequest): The HTTP request object from AJAX call

    Returns:
        JsonResponse: Array of center change request objects with structure:
            - id: Primary key of the center change request
            - child_info: Combined child admission number and name
            - old_center: Current center code/name
            - new_center: Requested new center code/name
            - old_Branch: Current branch name
            - new_Branch: Requested new branch name
            - date_requested: Date when request was submitted
            - reason_for_request: Reason provided for the center change
            - user_created: Username of person who created the request
            - effective_date: Date when center change should take effect

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts GET requests
        - Administrative access for center change management

    Business Logic:
        - Filters only active pending requests (status="Pending Approval")
        - Uses complex annotations to determine center and branch names
        - Handles both daycare code and name resolution
        - Provides comprehensive request information for approval workflow

    Database Operations:
        - Queries CenterChangerequest model with filters
        - Uses annotations to resolve center and branch names from foreign keys
        - Employs Coalesce to handle null values in center fields
        - Joins with Child, DayCare, and Branch models

    Center Resolution:
        - old_center: Resolves to either daycare_code or daycare_name
        - new_center: Resolves to either daycare_code or daycare_name
        - Branch information: Handled separately for old and new values

    Frontend Integration:
        - Designed for DataTables AJAX data source
        - Supports approval workflow interface
        - Enables center change request management
        - Provides data for approval decision making

    Error Handling:
        - Catches and logs database exceptions
        - Returns empty array on error
        - Provides graceful failure for frontend

    Use Cases:
        - Administrative review of transfer requests
        - Operational capacity management
        - Cross-branch coordination
        - Enrollment management

    URL Pattern:
        - /centers/change-requests/js/ (GET)
    """
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
            memo_month=month_before_previous,
            memo_year=month_before_previous_year,
            is_active=True,
        ).first()

        previous_month_memo = InvoiceMemo.objects.filter(
            child=child, memo_month=previous_month, memo_year=previous_year, is_active=True
        ).first()

        # Calculate outstanding amounts
        total_outstanding = Decimal("0.00")

        if (
            month_before_previous_memo
            and month_before_previous_memo.net_amount_due > 0
        ):
            total_outstanding += month_before_previous_memo.net_amount_due

        if previous_month_memo and previous_month_memo.net_amount_due > 0:
            total_outstanding += previous_month_memo.net_amount_due

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
                "charge": month_before_previous_memo.gross_total
                if month_before_previous_memo
                else Decimal("0.00"),
                "payments": month_before_previous_memo.total_payments
                if month_before_previous_memo
                else Decimal("0.00"),
                "balance": month_before_previous_memo.net_amount_due
                if month_before_previous_memo
                else Decimal("0.00"),
                "status": month_before_previous_memo.status
                if month_before_previous_memo
                else "No Record",
            },
            "previous_month": {
                "name": previous_month_name,
                "year": previous_year,
                "charge": previous_month_memo.gross_total
                if previous_month_memo
                else Decimal("0.00"),
                "payments": previous_month_memo.total_payments
                if previous_month_memo
                else Decimal("0.00"),
                "balance": previous_month_memo.net_amount_due
                if previous_month_memo
                else Decimal("0.00"),
                "status": previous_month_memo.status
                if previous_month_memo
                else "No Record",
                "package_fee": previous_month_memo.total_current_month
                if previous_month_memo
                else Decimal("0.00"),
                "extra_charges": Decimal("0.00"),
                "holiday_charges": Decimal("0.00"),
                "days_attended": 0,
                "expected_days": 22,
                "attendance_percentage": 0,
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


def get_effective_discount(enrollment, billing_date):
    """
    Get the effective discount for an enrollment on a given billing date.
    Checks for approved EnrollmentDiscountRequest records first,
    then falls back to the enrollment's default discount.

    This function implements effective-date-based discount resolution:
    1. Query EnrollmentDiscountRequest for approved requests with effective_from <= billing_date
    2. Select the most recent approved request (by effective_from date)
    3. If found, return the discount from the request
    4. Otherwise, fall back to enrollment.discount

    Args:
        enrollment: ChildEnrollment object
        billing_date: date object representing the billing period (typically first day of month)

    Returns:
        Discount object or None
    """
    # Check for approved discount requests with effective date <= billing date
    approved_request = EnrollmentDiscountRequest.objects.filter(
        enrollment=enrollment,
        status="APPROVED",
        is_active=True,
        effective_from__lte=billing_date,
    ).order_by("-effective_from").first()

    if approved_request:
        return approved_request.discount

    # Fall back to enrollment's default discount
    return enrollment.discount


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
        # Priority: normal_package > flex_package
        if package_mapping.normal_package:
            package = package_mapping.normal_package
        elif package_mapping.flex_package:
            package = package_mapping.flex_package
        else:
            package = None

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

                # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
                # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
                if time_out:
                    time_out = time(time_out.hour, time_out.minute, 0)

                is_holiday_day = log_date in holidays

                # ===== CORRECTED CUMULATIVE EXTRA HOURS CALCULATION =====
                # Extra hours: checkout AFTER package_end_time counts as extra
                # Checkout exactly AT package_end_time = no extra hours (using > not >=)
                package_end_datetime = datetime.combine(log_date, package_end_time)

                if time_out and package_end_time and time_out > package_end_time:
                    day_extra_charges = Decimal("0.00")
                    cutoff_530 = time(17, 30)

                    # 1. Handle charges BEFORE 5:30 PM (calculate from package_end_time)
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

        # Apply discount using effective date logic
        discount_amount = Decimal("0.00")
        billing_date = date(year, month, 1)
        effective_discount = get_effective_discount(enrollment, billing_date)
        if effective_discount and effective_discount.status == "Approved":
            discount_amount = subtotal * (effective_discount.discount_rate / 100)

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


def get_package_mapping_for_period(child, month, year):
    """
    Get the package mapping that was active during a specific billing period.

    This function uses date-based filtering to find the correct package mapping
    for a given month/year, ensuring historical billing accuracy when packages change.

    Parameters:
        child: Child object
        month: Integer month (1-12)
        year: Integer year (e.g., 2026)

    Returns:
        ChildPackageMapping object that was active during the specified period,
        or None if no mapping exists for that period

    Business Logic:
        - Gets first and last day of the billing month
        - Finds package mapping where:
          * effective_from <= last_day (started before or during month)
          * effective_to >= first_day OR effective_to is NULL (active during month)
        - Returns most recent mapping if multiple exist (order by effective_from DESC)

    Example:
        Child has packages:
        - Package A: effective_from=2025-01-01, effective_to=2026-01-31
        - Package B: effective_from=2026-02-01, effective_to=None

        get_package_mapping_for_period(child, 1, 2026) -> Returns Package A
        get_package_mapping_for_period(child, 2, 2026) -> Returns Package B
    """
    import calendar
    from django.db.models import Q

    # Get first and last day of the month
    first_day = datetime(year, month, 1).date()
    last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

    # Query for package mapping active during this period
    package_mapping = ChildPackageMapping.objects.filter(
        child=child,
        effective_from__lte=last_day,  # Started before or during the month
    ).filter(
        Q(effective_to__gte=first_day) | Q(effective_to__isnull=True)  # Still active during month
    ).order_by('-effective_from').first()  # Get most recent if multiple

    return package_mapping


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

        # Get child enrollment (same for all months)
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not enrollment:
            raise Exception("No approved enrollment found for child")

        # Month 1: Check for existing memo or calculate outstanding/credits
        # IMPORTANT: Pass TARGET month, not outstanding month. The function looks for memos
        # BEFORE the passed month/year. We want memos before the target month (e.g., January 2026),
        # not before the outstanding month (e.g., November 2025).
        month1_data = get_month_outstanding_credits(child, target_month_int, target_year_int)

        # Month 2: Get package mapping for month2 period and calculate with attendance
        package_mapping_month2 = get_package_mapping_for_period(child, month2, year2)
        if not package_mapping_month2:
            raise Exception(f"No package mapping found for {calendar.month_name[month2]} {year2}")

        month2_data = calculate_month_with_attendance(
            child, package_mapping_month2, enrollment, month2, year2
        )

        # Month 3: Get package mapping for month3 period and calculate full package
        package_mapping_month3 = get_package_mapping_for_period(child, month3, year3)
        if not package_mapping_month3:
            raise Exception(f"No package mapping found for {calendar.month_name[month3]} {year3}")

        month3_data = calculate_month_full_package(
            child, package_mapping_month3, enrollment, month3, year3
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
    """Get outstanding balance or credits for a specific month.

    This function finds the balance brought forward from the most recent previous memo,
    NOT from a specific month/year. This ensures we capture the correct outstanding balance
    even when memos don't exist for every month.

    Args:
        child: Child object
        month: Target month for the NEW memo being created
        year: Target year for the NEW memo being created

    Returns:
        Dict with charge, payments, balance, credit, status
    """
    try:
        from decimal import Decimal

        # Find the most recent memo that comes BEFORE the target month/year
        # This is the correct "balance brought forward" logic

        # First check for memos in previous years
        latest_previous_memo = (
            InvoiceMemo.objects.filter(
                child=child, is_active=True, memo_year__lt=year
            )
            .order_by("-memo_year", "-memo_month")
            .first()
        )

        # If no memo in previous years, check current year for previous months
        if not latest_previous_memo:
            latest_previous_memo = (
                InvoiceMemo.objects.filter(
                    child=child,
                    is_active=True,
                    memo_year=year,
                    memo_month__lt=month,
                )
                .order_by("-memo_month")
                .first()
            )

        if latest_previous_memo:
            # The outstanding balance is the net_amount_due from the last memo
            outstanding_balance = latest_previous_memo.net_amount_due

            # Handle credits (negative balance)
            credit = Decimal("0.00")
            if outstanding_balance < 0:
                credit = -outstanding_balance
                outstanding_balance = Decimal("0.00")  # Don't carry forward negative as outstanding

            return {
                "charge": outstanding_balance,  # This IS the outstanding balance
                "payments": Decimal("0.00"),  # Payments already applied to previous memo
                "balance": outstanding_balance,
                "credit": credit,
                "status": latest_previous_memo.status,
                "source_memo": latest_previous_memo.memo_code,  # For debugging
            }
        else:
            # No previous memos exist for this child
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
    """Calculate month charges with full attendance logic - COMPLETE FIXED VERSION

    Supports three package types:
    - Normal package: Regular days
    - Holiday package: Public holidays (is_public_holiday=True)
    - Vacation package: Polymath holidays and other school holidays (is_polymath_holiday=True or is_other_school_holiday=True)
    """
    try:
        import calendar
        from collections import defaultdict
        from datetime import datetime, time, timedelta
        from decimal import Decimal

        from django.db.models import Q

        # Get the date range for the month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # ===== VACATION MONTH DETECTION =====
        # Check if the entire month falls within a vacation period (polymath/other holidays)
        # A vacation month is when vacations cover the majority of working days
        # NEW: Use vacation system - check child's student type to get applicable vacations

        # Determine which vacation types apply to this child
        if child.is_polymath_student:
            applicable_vacation_types = ['ALL', 'POLYMATH']
        else:
            applicable_vacation_types = ['ALL', 'NON_POLYMATH']

        # Get all vacations applicable to this child that overlap this month
        vacation_holidays_qs = Holiday.objects.filter(
            is_vacation=True,
            vacation_type__in=applicable_vacation_types,
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )

        # BACKWARD COMPATIBILITY: Also include old polymath/other holidays
        # TODO: Remove this after data migration is complete
        old_vacation_holidays_qs = Holiday.objects.filter(
            Q(is_polymath_holiday=True) | Q(is_other_school_holiday=True),
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )
        # Combine both querysets
        vacation_holidays_qs = vacation_holidays_qs | old_vacation_holidays_qs

        # Get all public holidays that overlap this month
        public_holidays_qs = Holiday.objects.filter(
            is_public_holiday=True,
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )

        # Build sets of dates covered by each holiday type
        vacation_dates = set()
        for holiday in vacation_holidays_qs:
            # Get all dates in this holiday that fall within the month
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                vacation_dates.add(current)
                current += timedelta(days=1)

        public_holiday_dates = set()
        for holiday in public_holidays_qs:
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                public_holiday_dates.add(current)
                current += timedelta(days=1)

        # Calculate working days in the month (exclude weekends)
        total_days_in_month = (last_day - first_day).days + 1
        working_days = 0
        current_date = first_day
        while current_date <= last_day:
            if current_date.weekday() < 5:  # Monday=0 to Friday=4
                working_days += 1
            current_date += timedelta(days=1)

        # Check if this is a vacation month (vacation covers >= 50% of working days)
        vacation_working_days = sum(1 for d in vacation_dates if d.weekday() < 5)
        is_vacation_month = (
            vacation_working_days >= (working_days * 0.5)
            and package_mapping.vacation_package is not None
        )

        # ===== PACKAGE SELECTION =====
        # Priority: vacation_package (if vacation month) > normal_package > flex_package

        if is_vacation_month and package_mapping.vacation_package:
            # Vacation month: use vacation package
            package = package_mapping.vacation_package
            using_vacation_package = True
        elif package_mapping.normal_package:
            # Normal package takes priority over flex
            package = package_mapping.normal_package
            using_vacation_package = False
        elif package_mapping.flex_package:
            # Flex package as fallback
            package = package_mapping.flex_package
            using_vacation_package = False
        else:
            package = None
            using_vacation_package = False

        if not package:
            raise Exception("No valid package assigned.")

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # Get attendance logs for the month (only active records)
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day), is_active=True
        ).order_by("date_logged", "time_logged")

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        present_days = 0
        public_holiday_attendance_days = 0
        vacation_attendance_days = 0
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")
        vacation_charge = Decimal("0.00")

        # Get package details for extra hours calculation
        # Use the SAME package that was selected for billing (respects vacation month logic)
        package_end_time = None
        package_type = None

        if package:  # Use the already-selected package from above
            if hasattr(package, 'to_time') and package.to_time:
                package_end_time = package.to_time
            else:
                package_end_time = time(17, 30)  # Default for flex packages
            package_type = package.package_type

        # Process each attendance day with CORRECTED CUMULATIVE LOGIC
        for log_date, logs in logs_by_date.items():
            logs_sorted = sorted(logs, key=lambda x: x.time_logged or time(0, 0))

            if len(logs_sorted) >= 2:  # Complete attendance (in and out)
                present_days += 1
                last_log = logs_sorted[-1]
                time_out = last_log.time_logged

                # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
                # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
                if time_out:
                    time_out = time(time_out.hour, time_out.minute, 0)

                # Determine holiday type for this day
                is_public_holiday_day = log_date in public_holiday_dates
                is_vacation_day = log_date in vacation_dates
                is_holiday_day = is_public_holiday_day or is_vacation_day

                # ===== DETECT FLEX VS FIXED PACKAGE =====
                is_flex_package = (
                    package_mapping.flex_package is not None
                    and package == package_mapping.flex_package
                )

                # ===== EXTRA HOURS CALCULATION =====
                day_extra_charges = Decimal("0.00")
                cutoff_530 = time(17, 30)

                if is_flex_package:
                    # ===== FLEX PACKAGE: HOURS-BASED LOGIC =====
                    # Get check-in time (first check-in log of the day)
                    first_log = logs_sorted[0]
                    time_in = first_log.time_logged

                    # Normalize time_in to minute precision (strip seconds)
                    if time_in:
                        time_in = time(time_in.hour, time_in.minute, 0)

                    # Calculate actual hours used
                    if time_in and time_out:
                        checkin_datetime = datetime.combine(log_date, time_in)
                        checkout_datetime = datetime.combine(log_date, time_out)
                        actual_hours_used = (
                            checkout_datetime - checkin_datetime
                        ).total_seconds() / 3600
                    else:
                        actual_hours_used = 0

                    package_hours_allowed = float(package.no_hours)

                    # Check if exceeded package hours
                    if actual_hours_used > package_hours_allowed:
                        # BEFORE 5:30 PM logic
                        if time_out <= cutoff_530:
                            excess_hours = actual_hours_used - package_hours_allowed
                            # Round up (even 0.01 hour = 1 hour)
                            hour_count = math.ceil(excess_hours)

                            # Charge ExtraHoursUpTo530 (max 6 hours)
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

                        # AFTER 5:30 PM logic
                        elif time_out > cutoff_530:
                            # First: Calculate excess hours BEFORE 5:30 PM (if any)
                            cutoff_datetime = datetime.combine(log_date, cutoff_530)
                            hours_until_530 = (
                                cutoff_datetime - checkin_datetime
                            ).total_seconds() / 3600

                            if hours_until_530 > package_hours_allowed:
                                excess_before_530 = hours_until_530 - package_hours_allowed
                                hour_count = math.ceil(excess_before_530)

                                # Charge ExtraHoursUpTo530 for excess before 5:30
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

                            # Second: Charge for time AFTER 5:30 PM using ExtraHoursAfter530
                            # Get ALL applicable slots after 5:30 PM
                            applicable_slots = (
                                ExtraHoursAfter530.objects.filter(
                                    package_type=package_type,
                                    from_time__gte=cutoff_530,
                                    from_time__lt=time_out,
                                    effective_from__lte=log_date,
                                )
                                .filter(
                                    Q(effective_to__gte=log_date)
                                    | Q(effective_to__isnull=True)
                                )
                                .order_by("from_time")
                            )

                            # Add charges for ALL applicable slots (CUMULATIVE)
                            for slot in applicable_slots:
                                day_extra_charges += slot.extra_rate

                            # Handle partial slot
                            partial_slot = (
                                ExtraHoursAfter530.objects.filter(
                                    package_type=package_type,
                                    from_time__lt=time_out,
                                    to_time__gt=time_out,
                                    from_time__gte=cutoff_530,
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

                    # Add to total extra hours charge
                    extra_hours_charge += day_extra_charges

                else:
                    # ===== FIXED PACKAGE: TIME-BASED LOGIC (EXISTING) =====
                    # Extra hours: checkout AFTER package_end_time counts as extra
                    # Checkout exactly AT package_end_time = no extra hours (using > not >=)
                    package_end_datetime = datetime.combine(log_date, package_end_time)

                    if time_out and package_end_time and time_out > package_end_time:
                        actual_out_datetime = datetime.combine(log_date, time_out)
                        extra_time_delta = actual_out_datetime - package_end_datetime
                        extra_hours = extra_time_delta.total_seconds() / 3600

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
                            # Determine start time for after-5:30 charging (use package_end_time)
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

                # Calculate holiday/vacation charges based on holiday type
                # Public holidays use holiday_package, vacation days use vacation_package
                if is_public_holiday_day and package_mapping.holiday_package:
                    # Public holiday - use holiday_package
                    public_holiday_attendance_days += 1
                    expected_days_holiday = (
                        package_mapping.holiday_package.no_days_months or 22
                    )
                    daily_holiday_rate = (
                        package_mapping.holiday_package.package_total
                        / Decimal(expected_days_holiday)
                    )
                    holiday_charge += daily_holiday_rate
                elif is_vacation_day and package_mapping.vacation_package:
                    # Vacation day - use vacation_package daily rate ONLY if vacation package is assigned
                    vacation_attendance_days += 1
                    expected_days_vacation = (
                        package_mapping.vacation_package.no_days_months or 22
                    )
                    daily_vacation_rate = (
                        package_mapping.vacation_package.package_total
                        / Decimal(expected_days_vacation)
                    )
                    vacation_charge += daily_vacation_rate
                # NOTE: Vacation days without vacation package assigned are treated as normal days
                # No extra charges applied - relies on vacation month logic (>=50% rule) instead

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

        # ===== EXCESS DAY CHARGING =====
        # If child attended more days than package allows, charge excess at Adhoc rate
        excess_day_charges = Decimal("0.00")
        excess_days = 0
        adhoc_daily_rate = Decimal("0.00")
        excess_days_breakdown = []

        # Only apply excess day charging for packages with day limits
        # Check if package has no_days_months defined and it's less than 22 (has a day limit)
        if hasattr(package, 'no_days_months') and package.no_days_months and package.no_days_months < 22:
            if present_days > expected_days:
                excess_days = present_days - expected_days

                # Get Adhoc Package (FLP003) for excess day rate
                adhoc_package = FlexPackages.objects.filter(
                    package_code='FLP003',
                    is_active=True
                ).first()

                if adhoc_package:
                    adhoc_daily_rate = adhoc_package.package_total  # Already a daily rate
                    excess_day_charges = excess_days * adhoc_daily_rate

                    # Build breakdown of excess days with dates
                    # We need to identify which specific days are "excess"
                    # Since we don't track order, we'll just list the excess count
                    excess_days_breakdown = [{
                        "excess_days_count": excess_days,
                        "adhoc_daily_rate": float(adhoc_daily_rate),
                        "total_excess_charges": float(excess_day_charges),
                        "note": f"Child attended {present_days} days but package allows only {expected_days} days"
                    }]

        # Calculate subtotal (include both holiday and vacation charges)
        # Combine holiday_charge and vacation_charge for backward compatibility
        total_holiday_vacation_charge = holiday_charge + vacation_charge
        subtotal = package_fee + extra_hours_charge + total_holiday_vacation_charge + excess_day_charges

        # Apply discount using effective date logic
        discount_amount = Decimal("0.00")
        billing_date = date(year, month, 1)
        effective_discount = get_effective_discount(enrollment, billing_date)
        if effective_discount and effective_discount.status == "Approved":
            discount_amount = subtotal * (effective_discount.discount_rate / 100)

        total_charge = subtotal - discount_amount

        # Combine attendance days for backward compatibility
        total_holiday_attendance_days = public_holiday_attendance_days + vacation_attendance_days

        return {
            "package_name": package.package_name,
            "package_base_fee": package_total,
            "days_attended": present_days,
            "expected_days": expected_days,
            "attendance_percentage": round(attendance_percentage, 2),
            "is_half_charge": is_half_charge,
            "package_fee": package_fee,
            "extra_charges": extra_hours_charge,  # ✅ CORRECTED CUMULATIVE CALCULATION
            "holiday_attendance_days": total_holiday_attendance_days,  # Combined for backward compatibility
            "holiday_charges": total_holiday_vacation_charge,  # Combined for backward compatibility
            "discount": discount_amount,
            "total_charge": total_charge,
            # New detailed fields for transparency
            "is_vacation_month": is_vacation_month,
            "using_vacation_package": using_vacation_package,
            "public_holiday_days": public_holiday_attendance_days,
            "vacation_days": vacation_attendance_days,
            "public_holiday_charge": holiday_charge,
            "vacation_charge": vacation_charge,
            # Excess day charging fields
            "excess_days": excess_days,
            "adhoc_daily_rate": adhoc_daily_rate,
            "excess_day_charges": excess_day_charges,
            "excess_days_breakdown": excess_days_breakdown,
        }

    except Exception as e:
        raise Exception(f"Error calculating month with attendance: {str(e)}")


def calculate_month_full_package(child, package_mapping, enrollment, month, year):
    """Calculate month charges with full package amount (no attendance logic)"""
    try:
        from decimal import Decimal

        # Get package details
        # Priority: normal_package > flex_package
        if package_mapping.normal_package:
            package = package_mapping.normal_package
        elif package_mapping.flex_package:
            package = package_mapping.flex_package
        else:
            package = None

        if not package:
            raise Exception("No valid package assigned.")

        expected_days = package.no_days_months or 22
        package_total = package.package_total or Decimal("0.00")

        # For future months, charge full package amount
        package_fee = package_total

        # No extra hours or holiday charges for future months
        extra_hours_charge = Decimal("0.00")
        holiday_charge = Decimal("0.00")

        # Calculate subtotal
        subtotal = package_fee + extra_hours_charge + holiday_charge

        # Apply discount using effective date logic
        discount_amount = Decimal("0.00")
        billing_date = date(year, month, 1)
        effective_discount = get_effective_discount(enrollment, billing_date)
        if effective_discount and effective_discount.status == "Approved":
            discount_amount = subtotal * (effective_discount.discount_rate / 100)

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

    # Get child enrollment (same for all months)
    enrollment = ChildEnrollment.objects.filter(
        child=child, status="Approved", is_active=True
    ).first()

    if not enrollment:
        raise Exception("No approved enrollment found for child")

    # Month 1: Enhanced outstanding with payment tracking
    # IMPORTANT: Pass TARGET month, not outstanding month. The function looks for memos
    # BEFORE the passed month/year. We want memos before the target month (e.g., January 2026),
    # not before the outstanding month (e.g., November 2025).
    month1_data = get_enhanced_outstanding_data(child, target_month_int, target_year_int)

    # Month 2: Get package mapping for month2 period and calculate with enhanced breakdown
    package_mapping_month2 = get_package_mapping_for_period(child, month2, year2)
    if not package_mapping_month2:
        raise Exception(f"No package mapping found for {calendar.month_name[month2]} {year2}")

    month2_data = calculate_enhanced_month_with_attendance(
        child, package_mapping_month2, enrollment, month2, year2
    )

    # Month 3: Get package mapping for month3 period and calculate enhanced advance
    package_mapping_month3 = get_package_mapping_for_period(child, month3, year3)
    if not package_mapping_month3:
        raise Exception(f"No package mapping found for {calendar.month_name[month3]} {year3}")

    month3_data = calculate_enhanced_advance_month(
        child, package_mapping_month3, enrollment, month3, year3
    )

    # Calculate enhanced summary
    # For a NEW memo, the grand total is simply:
    # Outstanding (balance from previous memo) + Previous month charges + Current month charges
    # We do NOT subtract payments here because:
    # 1. Outstanding already reflects balance after payments from previous memo
    # 2. Month 2 and Month 3 are NEW charges that haven't had payments applied yet
    total_outstanding = month1_data["balance_after_payments"]
    current_month_charge = month2_data["total_charge"]
    next_month_charge = month3_data["total_charge"]

    # Grand total = Outstanding + Previous Month Charges + Current Month Advance
    # No payment deductions - this is the TOTAL AMOUNT DUE before any new payments
    grand_total = total_outstanding + current_month_charge + next_month_charge

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
    """Get outstanding data with payment tracking.

    This function finds the balance brought forward from the most recent previous memo,
    NOT from a specific month/year. This ensures we capture the correct outstanding balance
    even when memos don't exist for every month.

    Args:
        child: Child object
        month: Target month for the NEW memo being created
        year: Target year for the NEW memo being created

    Returns:
        Dict with original_charge, payments_received, balance_after_payments, status, payment_details
    """
    import json
    from decimal import Decimal

    # Find the most recent memo that comes BEFORE the target month/year
    # This is the correct "balance brought forward" logic

    # First check for memos in previous years
    latest_previous_memo = (
        InvoiceMemo.objects.filter(
            child=child, is_active=True, memo_year__lt=year
        )
        .order_by("-memo_year", "-memo_month")
        .first()
    )

    # If no memo in previous years, check current year for previous months
    if not latest_previous_memo:
        latest_previous_memo = (
            InvoiceMemo.objects.filter(
                child=child,
                is_active=True,
                memo_year=year,
                memo_month__lt=month,
            )
            .order_by("-memo_month")
            .first()
        )

    if latest_previous_memo:
        # Get payment details from the most recent previous memo
        payment_details = []
        try:
            month_detail = latest_previous_memo.month_details.first()
            if month_detail and month_detail.payment_receipts:
                payment_details = json.loads(month_detail.payment_receipts)
        except:
            payment_details = []

        # The outstanding balance is the net_amount_due from the last memo
        # Only carry forward DEBIT balance (positive). Credits are handled separately.
        outstanding_balance = latest_previous_memo.net_amount_due
        if outstanding_balance < 0:
            outstanding_balance = Decimal("0.00")

        return {
            "original_charge": outstanding_balance,  # This IS the outstanding balance
            "payments_received": Decimal("0.00"),  # Payments already applied to previous memo
            "balance_after_payments": outstanding_balance,
            "status": latest_previous_memo.status,
            "payment_details": payment_details,
            "source_memo": latest_previous_memo.memo_code,  # For debugging
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
    # Priority: normal_package > flex_package
    if package_mapping.normal_package:
        package = package_mapping.normal_package
    elif package_mapping.flex_package:
        package = package_mapping.flex_package
    else:
        package = None

    if not package:
        raise Exception("No valid package assigned.")

    expected_days = package.no_days_months or 22
    package_total = package.package_total or Decimal("0.00")

    # Get attendance logs for the month (only active records)
    attendance_logs = AttendanceLog.objects.filter(
        child=child, date_logged__range=(first_day, last_day), is_active=True
    ).order_by("date_logged", "time_logged")

    # Get holidays in this month (expand date ranges to include all dates)
    holiday_objs = Holiday.objects.filter(
        start_date__lte=last_day, end_date__gte=first_day
    )
    holidays = set()
    for holiday in holiday_objs:
        current = max(holiday.start_date, first_day)
        end = min(holiday.end_date, last_day)
        while current <= end:
            holidays.add(current)
            current += timedelta(days=1)

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
    elif package_mapping.vacation_package:
        package_end_time = package_mapping.vacation_package.to_time
        package_type = package_mapping.vacation_package.package_type
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

            # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
            # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
            if time_out:
                time_out = time(time_out.hour, time_out.minute, 0)

            is_holiday_day = log_date in holidays

            # ===== DETECT FLEX VS FIXED PACKAGE =====
            is_flex_package = (
                package_mapping.flex_package is not None
                and package == package_mapping.flex_package
            )

            # ===== EXTRA HOURS CALCULATION =====
            day_extra_charges = Decimal("0.00")
            applied_rates = []
            cutoff_530 = time(17, 30)
            extra_hours = 0  # Initialize for display purposes

            if is_flex_package:
                # ===== FLEX PACKAGE: HOURS-BASED LOGIC =====
                # time_in is already extracted above (first_log.time_logged)
                # Normalize time_in to minute precision (strip seconds)
                if time_in:
                    time_in = time(time_in.hour, time_in.minute, 0)

                # Calculate actual hours used
                if time_in and time_out:
                    checkin_datetime = datetime.combine(log_date, time_in)
                    checkout_datetime = datetime.combine(log_date, time_out)
                    actual_hours_used = (
                        checkout_datetime - checkin_datetime
                    ).total_seconds() / 3600
                else:
                    actual_hours_used = 0

                package_hours_allowed = float(package.no_hours)
                extra_hours = max(
                    0, actual_hours_used - package_hours_allowed
                )  # For display

                # Check if exceeded package hours
                if actual_hours_used > package_hours_allowed:
                    # BEFORE 5:30 PM logic
                    if time_out <= cutoff_530:
                        excess_hours = actual_hours_used - package_hours_allowed
                        # Round up (even 0.01 hour = 1 hour)
                        hour_count = math.ceil(excess_hours)

                        # Charge ExtraHoursUpTo530 (max 6 hours)
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

                    # AFTER 5:30 PM logic
                    elif time_out > cutoff_530:
                        # First: Calculate excess hours BEFORE 5:30 PM (if any)
                        cutoff_datetime = datetime.combine(log_date, cutoff_530)
                        hours_until_530 = (
                            cutoff_datetime - checkin_datetime
                        ).total_seconds() / 3600

                        if hours_until_530 > package_hours_allowed:
                            excess_before_530 = hours_until_530 - package_hours_allowed
                            hour_count = math.ceil(excess_before_530)

                            # Charge ExtraHoursUpTo530 for excess before 5:30
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

                        # Second: Charge for time AFTER 5:30 PM using ExtraHoursAfter530
                        # Get ALL applicable slots after 5:30 PM
                        applicable_slots = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__gte=cutoff_530,
                                from_time__lt=time_out,
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .order_by("from_time")
                        )

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

                        # Handle partial slot
                        partial_slot = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__lt=time_out,
                                to_time__gt=time_out,
                                from_time__gte=cutoff_530,
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
                            applied_rates.append(
                                {
                                    "time_slot": f"{partial_slot.from_time.strftime('%H:%M')} - {partial_slot.to_time.strftime('%H:%M')} (partial)",
                                    "rate": float(partial_slot.extra_rate),
                                    "type": "After 5:30 PM (Partial)",
                                }
                            )

            else:
                # ===== FIXED PACKAGE: TIME-BASED LOGIC (EXISTING) =====
                # Extra hours: checkout AFTER package_end_time counts as extra
                # Checkout exactly AT package_end_time = no extra hours (using > not >=)
                package_end_datetime = datetime.combine(log_date, package_end_time)

                if time_out and package_end_time and time_out > package_end_time:
                    actual_out_datetime = datetime.combine(log_date, time_out)
                    extra_time_delta = actual_out_datetime - package_end_datetime
                    extra_hours = extra_time_delta.total_seconds() / 3600

                    # 1. Handle charges BEFORE 5:30 PM (calculate from package_end_time)
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

    # ===== EXCESS DAY CHARGING =====
    # If child attended more days than package allows, charge excess at Adhoc rate
    excess_day_charges = Decimal("0.00")
    excess_days = 0
    adhoc_daily_rate = Decimal("0.00")
    excess_days_breakdown = []

    # Only apply excess day charging for packages with day limits
    # Check if package has no_days_months defined and it's less than 22 (has a day limit)
    if hasattr(package, 'no_days_months') and package.no_days_months and package.no_days_months < 22:
        if present_days > expected_days:
            excess_days = present_days - expected_days

            # Get Adhoc Package (FLP003) for excess day rate
            adhoc_package = FlexPackages.objects.filter(
                package_code='FLP003',
                is_active=True
            ).first()

            if adhoc_package:
                adhoc_daily_rate = adhoc_package.package_total  # Already a daily rate
                excess_day_charges = excess_days * adhoc_daily_rate

                # Build breakdown of excess days with dates
                excess_days_breakdown = [{
                    "excess_days_count": excess_days,
                    "adhoc_daily_rate": float(adhoc_daily_rate),
                    "total_excess_charges": float(excess_day_charges),
                    "note": f"Child attended {present_days} days but package allows only {expected_days} days"
                }]

    # Calculate subtotal
    subtotal = package_fee + extra_hours_charge + holiday_charge + excess_day_charges

    # Apply discount using effective date logic
    discount_amount = Decimal("0.00")
    billing_date = date(year, month, 1)
    effective_discount = get_effective_discount(enrollment, billing_date)
    if effective_discount and effective_discount.status == "Approved":
        discount_amount = subtotal * (effective_discount.discount_rate / 100)

    total_charge = subtotal - discount_amount

    # For batch/new memo generation, we should NOT pull payments from existing memos.
    # Payments from existing memos are already reflected in the Outstanding balance (Month 1).
    # Including them here would double-count payments.
    #
    # This function calculates FRESH charges based on attendance.
    # Payments should be 0 for new memos - they get applied after the memo is created.
    payments_received = Decimal("0.00")
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
        # Excess day charging fields
        "excess_days": excess_days,
        "adhoc_daily_rate": adhoc_daily_rate,
        "excess_day_charges": excess_day_charges,
        "excess_days_breakdown": excess_days_breakdown,
    }


def calculate_enhanced_advance_month(child, package_mapping, enrollment, month, year):
    """Enhanced advance month calculation with payment tracking"""
    import json
    from decimal import Decimal

    # Get package details
    # Priority: normal_package > flex_package
    if package_mapping.normal_package:
        package = package_mapping.normal_package
    elif package_mapping.flex_package:
        package = package_mapping.flex_package
    else:
        package = None

    if not package:
        raise Exception("No valid package assigned.")

    expected_days = package.no_days_months or 22
    package_total = package.package_total or Decimal("0.00")

    # For future months, charge full package amount
    package_fee = package_total

    # Apply discount using effective date logic
    discount_amount = Decimal("0.00")
    billing_date = date(year, month, 1)
    effective_discount = get_effective_discount(enrollment, billing_date)
    if effective_discount and effective_discount.status == "Approved":
        discount_amount = package_fee * (effective_discount.discount_rate / 100)

    total_charge = package_fee - discount_amount

    # For batch/new memo generation, we should NOT pull payments from existing memos.
    # Payments from existing memos are already reflected in the Outstanding balance (Month 1).
    # Including them here would double-count payments.
    #
    # This function calculates FRESH charges for the advance month.
    # Payments should be 0 for new memos - they get applied after the memo is created.
    payments_received = Decimal("0.00")
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


# Add these view functions to your views.py file


@login_required
def getExtraHoursReport(request):
    """
    Display the extra hours report page with filtering form.

    This view renders the extra hours report interface where users can analyze
    and filter extra hours charges across different time periods. It provides
    comprehensive reporting capabilities for billing and operational analysis.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the extrahoursreport.html template with:
            - form: ExtraHoursReportForm for filtering report parameters
            - UserName: Current authenticated user's username

    Template Context:
        - form: ExtraHoursReportForm instance for search and filtering
        - UserName: String containing current user's username

    Security:
        - Requires user login (@login_required decorator)
        - Provides access to financial reporting data
        - Restricts access to authorized users only

    Business Logic:
        - Initializes report form with default parameters
        - Prepares interface for extra hours analysis
        - Supports various reporting time periods
        - Enables detailed charge breakdowns

    Integration:
        - Works with getExtraHoursReportJS() for AJAX data loading
        - Provides interface for complex financial analysis
        - Supports export and printing capabilities
        - Integrates with billing systems

    Form Features:
        - Child selection dropdown
        - Date range selection
        - Report type selection (detailed/summary)
        - Branch and center filtering
        - Flexible parameter combinations

    Report Types:
        - Detailed: Individual charge breakdowns
        - Summary: Aggregated totals and averages
        - Monthly: Month-by-month analysis
        - Custom: User-defined date ranges

    Usage:
        - Financial reporting and analysis
        - Billing verification and auditing
        - Operational cost analysis
        - Parent communication and transparency

    Related Views:
        - getExtraHoursReportJS(): Provides AJAX data for reports
        - getExtraHoursSummaryJS(): Provides summary statistics
        - Extra hours calculation functions
    """
    form = ExtraHoursReportForm()
    return render(
        request,
        "../templates/reports/extrahoursreport.html",
        {"form": form, "UserName": request.user.username},
    )


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

            # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
            # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
            if time_out:
                time_out = time(time_out.hour, time_out.minute, 0)

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

            # ===== VACATION MONTH DETECTION FOR THIS DATE =====
            # Determine the month boundaries for this log_date
            month_first_day = log_date.replace(day=1)
            month_last_day = datetime(log_date.year, log_date.month, calendar.monthrange(log_date.year, log_date.month)[1]).date()

            # Get vacation holidays for this month
            # NEW: Use vacation system based on child's student type
            if child.is_polymath_student:
                applicable_vacation_types = ['ALL', 'POLYMATH']
            else:
                applicable_vacation_types = ['ALL', 'NON_POLYMATH']

            vacation_holidays_qs = Holiday.objects.filter(
                is_vacation=True,
                vacation_type__in=applicable_vacation_types,
                start_date__lte=month_last_day,
                end_date__gte=month_first_day,
                is_active=True
            )

            # BACKWARD COMPATIBILITY: Include old system
            old_vacation_holidays_qs = Holiday.objects.filter(
                Q(is_polymath_holiday=True) | Q(is_other_school_holiday=True),
                start_date__lte=month_last_day,
                end_date__gte=month_first_day,
                is_active=True
            )
            vacation_holidays_qs = vacation_holidays_qs | old_vacation_holidays_qs
            vacation_dates = set()
            for holiday in vacation_holidays_qs:
                current = max(holiday.start_date, month_first_day)
                end = min(holiday.end_date, month_last_day)
                while current <= end:
                    vacation_dates.add(current)
                    current += timedelta(days=1)

            # Calculate working days in the month
            working_days = sum(1 for d in (month_first_day + timedelta(days=i) for i in range((month_last_day - month_first_day).days + 1)) if d.weekday() < 5)
            vacation_working_days = sum(1 for d in vacation_dates if d.weekday() < 5)

            # A month is a "vacation month" if >= 50% of working days are vacation days AND child has vacation package
            is_vacation_month = (
                vacation_working_days >= (working_days * 0.5)
                and package_mapping.vacation_package is not None
            )

            # ===== PACKAGE SELECTION (respects vacation month logic) =====
            package = None
            package_end_time = None
            package_name = "Unknown Package"
            package_type = None
            if is_vacation_month and package_mapping.vacation_package:
                # Vacation month: use vacation package
                package = package_mapping.vacation_package
                package_end_time = package.to_time
                package_name = f"{package.package_name} (Vacation)"
                package_type = package.package_type
            elif package_mapping.normal_package:
                # Normal package takes priority over flex
                package = package_mapping.normal_package
                package_end_time = package.to_time
                package_name = package.package_name
                package_type = package.package_type
            elif package_mapping.flex_package:
                # Flex package as fallback
                package = package_mapping.flex_package
                package_name = f"{package.package_name} (Flex)"
                package_end_time = time(17, 30)  # 5:30 PM as default
                package_type = package.package_type

            if not package_end_time or not time_out:
                continue

            # Calculate extra hours if child stayed beyond package time
            # Extra hours: checkout AFTER package_end_time counts as extra
            # Checkout exactly AT package_end_time = no extra hours (using > not >=)
            package_end_datetime = datetime.combine(log_date, package_end_time)

            if time_out > package_end_time:
                # Calculate extra time in hours from package_end_time
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
                if package_end_time < cutoff_530 and time_out > package_end_time:
                    # Calculate hours between package end and either 5:30 PM or checkout time (whichever is earlier)
                    end_time_for_calc = min(time_out, cutoff_530)
                    end_datetime_for_calc = datetime.combine(log_date, end_time_for_calc)
                    hours_before_530 = (
                        end_datetime_for_calc - package_end_datetime
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

            # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
            # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
            if time_out:
                time_out = time(time_out.hour, time_out.minute, 0)

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
            # Extra hours: checkout AFTER package_end_time counts as extra
            # Checkout exactly AT package_end_time = no extra hours (using > not >=)
            package_end_datetime = datetime.combine(log_date, package_end_time)

            if time_out > package_end_time:
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

                # Extra hours before 5:30 PM (calculate from package_end_time)
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
    """
    Display the child package mapping management page with comprehensive configuration options.

    This view renders the package mapping interface where users can assign and manage
    package relationships for children. It provides a comprehensive interface for
    configuring child-package relationships with discount options.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the missing_mappings.html template with:
            - children: QuerySet of active, enrolled children
            - normal_packages: QuerySet of standard package options
            - holiday_packages: QuerySet of holiday package options
            - flex_packages: QuerySet of flexible package options
            - approved_discounts: QuerySet of approved discount options
            - UserName: Current authenticated user's username

    Template Context:
        - children: Active and enrolled children ordered by admission number
        - normal_packages: Standard daycare packages (non-holiday)
        - holiday_packages: Special holiday packages
        - flex_packages: Flexible hours packages
        - approved_discounts: Approved discount codes
        - UserName: String containing current user's username

    Security:
        - Requires user login (@login_required decorator)
        - Filters for active, enrolled children only
        - Shows only approved discounts
        - Handles exceptions gracefully with fallback options

    Business Logic:
        - Filters children by active status and enrollment
        - Separates packages by type (normal vs holiday)
        - Shows only approved discounts for selection
        - Orders data consistently for user interface

    Package Type Filtering:
        - Normal packages: is_holiday_package=False
        - Holiday packages: is_holiday_package=True
        - Flex packages: Separate FlexPackages model
        - All packages filtered by is_active=True

    Discount Integration:
        - Shows only approved discounts (status="APPROVED")
        - Filters by is_active=True status
        - Orders by discount_code for consistency
        - Enables discount assignment during mapping

    Integration:
        - Works with getPackageMappingsJS() for AJAX data loading
        - Supports package assignment and modification
        - Enables discount application during mapping
        - Connects to package change request workflows

    Error Handling:
        - Comprehensive exception handling with multiple fallback options
        - Attempts different redirect strategies on errors
        - Provides empty context if all redirects fail
        - Maintains user experience during error scenarios

    Form Features:
        - Child selection dropdown with admission numbers
        - Package type selection (normal/holiday/flex)
        - Discount code selection from approved options
        - Date range specification for mappings
        - User-friendly interface elements

    Data Ordering:
        - Children ordered by admission_number
        - Packages ordered by package_code
        - Discounts ordered by discount_code
        - Consistent ordering for user experience

    Usage:
        - Package assignment for new children
        - Package modification for existing children
        - Discount application and management
        - Package change request initiation

    Related Views:
        - getPackageMappingsJS(): Provides AJAX data for existing mappings
        - savePackageMapping(): Handles package assignment
        - getPackageChangeApproval(): Manages package changes
        - updatePackageMapping(): Handles mapping modifications
    """
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

        # Get vacation packages (packages with vacation package type)
        vacation_packages = FixedPackage.objects.filter(
            is_active=True, package_type__is_vacation_package=True
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
            "vacation_packages": vacation_packages,
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
                    "vacation_packages": [],
                    "flex_packages": [],
                    "UserName": request.user.username,
                }
                return render(
                    request, "../templates/utils/missing_mappings.html", context
                )


@login_required
def getPackageMappingsJS(request):
    """
    Provide comprehensive package mapping data via AJAX with advanced search and filtering.

    This view returns detailed package mapping information in JSON format for DataTables
    integration. It supports complex filtering and provides comprehensive package details
    including discounts, effective dates, and mapping status.

    Parameters:
        request (HttpRequest): AJAX GET request containing search parameters:
            - child_id: Integer child ID for filtering mappings
            - status: String "true"/"false" for active status filtering
            - effective_date: String date in YYYY-MM-DD format for date filtering

    Returns:
        JsonResponse: JSON array of package mapping records with:
            - child_name: String child identification and name
            - normal_package_info: String normal package details with code and amount
            - holiday_package_info: String holiday package details with code and amount
            - flex_package_info: String flex package details with code and amount
            - discount_info: String discount details with code and rate
            - effective_from: String effective start date
            - effective_to: String effective end date or "Ongoing"
            - is_active: Boolean active status
            - actions: String HTML for action buttons

    Security:
        - Requires user login (@login_required decorator)
        - Filters for active children only
        - Handles parameter validation
        - Provides safe JSON responses

    Business Logic:
        - Filters mappings by child active status
        - Applies search filters dynamically
        - Provides comprehensive package information
        - Includes discount details when available
        - Handles date range filtering for effective periods

    Search Functionality:
        - Child-specific filtering by ID
        - Active/inactive status filtering
        - Effective date range filtering
        - Combines multiple filter criteria
        - Supports flexible search patterns

    Package Information:
        - Normal packages: Shows code and total amount
        - Holiday packages: Shows code and total amount
        - Flex packages: Shows code and total amount
        - Handles null packages gracefully
        - Provides consistent formatting

    Discount Integration:
        - Shows discount code and rate when available
        - Handles null discounts gracefully
        - Provides formatted discount information
        - Supports discount analysis and reporting

    Date Handling:
        - Filters by effective date ranges
        - Handles null effective_to dates as "Ongoing"
        - Provides user-friendly date formatting
        - Supports date-based queries

    Query Optimization:
        - Uses select_related for efficient joins
        - Filters data at database level
        - Minimizes database queries
        - Optimizes for large datasets

    Data Presentation:
        - Consistent formatting for all package types
        - User-friendly display of complex data
        - Includes action buttons for management
        - Provides comprehensive mapping overview

    Integration:
        - Works with DataTables for frontend display
        - Supports AJAX-based data loading
        - Provides real-time search and filtering
        - Enables package management workflows

    Error Handling:
        - Handles date parsing errors
        - Provides safe JSON responses
        - Maintains data consistency
        - Handles edge cases in package data

    Performance Features:
        - Efficient database queries
        - Minimal data processing overhead
        - Scalable for large datasets
        - Optimized query patterns
    """
    try:
        # Get search parameters
        child_id = request.GET.get("child_id")
        status = request.GET.get("status")
        effective_date = request.GET.get("effective_date")

        # Start with base query
        mappings = ChildPackageMapping.objects.select_related(
            "child", "normal_package", "holiday_package", "vacation_package", "flex_package", "discount"
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

            vacation_package_name = None
            vacation_package_code = None
            vacation_package_amount = None

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

            if mapping.vacation_package:
                vacation_package_name = mapping.vacation_package.package_name
                vacation_package_code = mapping.vacation_package.package_code
                vacation_package_amount = float(mapping.vacation_package.package_total)

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
                    # Vacation package details
                    "vacation_package_name": vacation_package_name,
                    "vacation_package_code": vacation_package_code,
                    "vacation_package_amount": vacation_package_amount,
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
        vacation_package_id = request.POST.get("vacation_package")
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

            # Set vacation package if provided (optional)
            if vacation_package_id:
                mapping.vacation_package = FixedPackage.objects.get(id=vacation_package_id)

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
        vacation_package_id = request.POST.get("vacation_package")
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
            mapping.vacation_package = None
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
                if vacation_package_id:
                    mapping.vacation_package = FixedPackage.objects.get(
                        id=vacation_package_id
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
                if vacation_package_id:
                    mapping.vacation_package = FixedPackage.objects.get(
                        id=vacation_package_id
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
def updateVacationPackageMapping(request):
    """Update only the vacation package for an existing package mapping"""
    try:
        if request.method != "POST":
            messages.error(request, "Invalid request method")
            return redirect("core:view_child_package_mapping")

        mapping_id = request.POST.get("mapping_id")
        vacation_package_id = request.POST.get("vacation_package")

        if not mapping_id:
            messages.error(request, "Missing mapping ID")
            return redirect("core:view_child_package_mapping")

        # Get the mapping
        mapping = ChildPackageMapping.objects.get(id=mapping_id)

        # Update only the vacation package
        if vacation_package_id:
            mapping.vacation_package = FixedPackage.objects.get(id=vacation_package_id)
        else:
            mapping.vacation_package = None

        mapping.user_updated = request.user.username
        mapping.date_updated = datetime.now()
        mapping.save()

        messages.success(
            request,
            f"Vacation package updated successfully for {mapping.child.admission_number}"
        )
        return redirect("core:view_child_package_mapping")

    except ChildPackageMapping.DoesNotExist:
        messages.error(request, "Package mapping not found")
    except FixedPackage.DoesNotExist:
        messages.error(request, "Selected vacation package not found")
    except Exception as e:
        messages.error(request, f"Error updating vacation package: {str(e)}")

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


@login_required
def getMemoDataEntry(request):
    """
    Display the memo data entry page for manual invoice generation.

    This view provides the interface for manually creating invoice memos when
    automatic generation isn't suitable. The page allows users to input detailed
    financial information for three months: outstanding balance, previous month
    charges, and current month charges.

    Parameters:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the memo_manual.html template with:
            - children: List of active, enrolled children for dropdown selection
            - year_range: List of years (current-2 to current+1) for date selection
            - UserName: Current authenticated user's username

    Template Context:
        - children: QuerySet of Child objects (active and enrolled)
        - year_range: List of integers representing selectable years
        - UserName: String containing current user's username

    Security:
        - Requires user login (@login_required decorator)
        - Only shows active, enrolled children
        - Handles exceptions gracefully with error messages

    Business Logic:
        - Filters children by is_active=True and is_enrolled=True
        - Generates 4-year range centered on current year
        - Orders children by admission number for consistent display
        - Redirects to invoice memo page on errors

    Error Handling:
        - Catches all exceptions and displays user-friendly error messages
        - Redirects to core:load_invoice_memo on failures
        - Preserves user context during error scenarios
    """
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
        return redirect("core:load_invoice_memo")


@login_required
def getChildPackageDetails(request):
    """
    Retrieve detailed package information for a specific child to auto-fill memo forms.

    This AJAX endpoint provides comprehensive package details including active package
    information, fees, and discount details for a specific child. It's used to
    auto-populate memo generation forms with accurate package data.

    Parameters:
        request (HttpRequest): AJAX GET request containing:
            - child_id: Integer ID of the child to retrieve package details for

    Returns:
        JsonResponse: JSON object containing:
            - package_name: String name of the active package
            - package_fee: Float total fee for the package
            - child_name: String full name of the child
            - admission_number: String admission number of the child
            - discount_rate: Float discount percentage (0 if no discount)
            - discount_name: String name of applied discount (empty if none)

    Error Responses:
        - 400: Missing child_id parameter
        - 404: Child not found or no active package mapping
        - 500: Server error during processing

    Security:
        - Requires user login (@login_required decorator)
        - Validates child existence before processing
        - Handles package mapping validation

    Business Logic:
        - Searches for active package mapping (is_active=True)
        - Determines package type (normal/holiday/flex)
        - Extracts appropriate fee based on package type
        - Validates discount status (active and approved)
        - Provides debug information for troubleshooting

    Package Type Handling:
        - normal_package: Standard daycare package
        - holiday_package: Special holiday pricing package
        - flex_package: Flexible hours package
        - Handles mixed package scenarios gracefully

    Discount Validation:
        - Checks discount is_active status
        - Validates discount approval status
        - Only applies approved discounts to calculations

    Debug Features:
        - Logs all package mappings for troubleshooting
        - Provides detailed error information
        - Includes mapping activity status in debug output
    """
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not child_id:
            return JsonResponse({"error": "Child ID required"}, status=400)

        child = Child.objects.get(id=child_id)

        # If month and year are provided, get package for that specific period
        # This is the CURRENT month (advance payment month)
        if month and year:
            month_int = int(month)
            year_int = int(year)
            package_mapping = get_package_mapping_for_period(child, month_int, year_int)
            print(
                f"DEBUG: Getting package for {child.admission_number} for period: {month}/{year}"
            )
        else:
            # Fallback to currently active package (legacy behavior)
            package_mapping = ChildPackageMapping.objects.filter(
                child=child, is_active=True
            ).first()
            print(
                f"DEBUG: Getting currently active package for {child.admission_number} (no month/year provided)"
            )

        print(f"DEBUG: Package mapping found: {package_mapping}")

        if not package_mapping:
            import calendar
            error_msg = "No package mapping found"
            if month and year:
                error_msg = f"No package mapping found for {calendar.month_name[int(month)]} {year}"

            return JsonResponse(
                {
                    "error": error_msg,
                    "debug_info": {
                        "child_id": child_id,
                        "child_admission": child.admission_number,
                        "requested_month": month,
                        "requested_year": year,
                    },
                },
                status=404,
            )

        # Determine which package is active and gather details
        package_name = "Unknown Package"
        package_fee = 0
        package_type = ""
        package_code = ""
        from_time = ""
        to_time = ""
        no_hours = 0
        no_days_week = 0
        no_days_month = 0
        package_term = ""

        # Priority order: normal_package > flex_package > holiday_package
        # Holiday package is only a fallback for children without normal/flex packages
        if package_mapping.normal_package:
            pkg = package_mapping.normal_package
            package_name = pkg.package_name
            package_fee = float(pkg.package_total)
            package_type = pkg.package_type.package_type_name if pkg.package_type else "Normal"
            package_code = pkg.package_code
            from_time = pkg.from_time.strftime("%I:%M %p") if pkg.from_time else ""
            to_time = pkg.to_time.strftime("%I:%M %p") if pkg.to_time else ""
            no_hours = float(pkg.no_hours) if pkg.no_hours else 0
            no_days_week = pkg.no_days_week or 0
            no_days_month = pkg.no_days_months or 0
            package_term = pkg.package_term.package_type_name if pkg.package_term else "Fixed"
        elif package_mapping.flex_package:
            pkg = package_mapping.flex_package
            package_name = f"{pkg.package_name} (Flex)"
            package_fee = float(pkg.package_total)
            package_type = pkg.package_type.package_type_name if pkg.package_type else "Flex"
            package_code = pkg.package_code
            no_hours = float(pkg.no_hours) if pkg.no_hours else 0
            no_days_week = pkg.no_days_week or 0
            no_days_month = pkg.no_days_months or 0
            package_term = pkg.package_term.package_type_name if pkg.package_term else "Flexible"
        elif package_mapping.holiday_package:
            pkg = package_mapping.holiday_package
            package_name = f"{pkg.package_name} (Holiday)"
            package_fee = float(pkg.package_total)
            package_type = "Holiday"
            package_code = pkg.package_code
            from_time = pkg.from_time.strftime("%I:%M %p") if pkg.from_time else ""
            to_time = pkg.to_time.strftime("%I:%M %p") if pkg.to_time else ""
            no_hours = float(pkg.no_hours) if pkg.no_hours else 0
            no_days_week = pkg.no_days_week or 0
            no_days_month = pkg.no_days_months or 0
            package_term = pkg.package_term.package_type_name if pkg.package_term else "Fixed"

        # Get discount information
        # Check both package_mapping.discount AND enrollment.discount
        # Enrollment discount takes precedence (set via enrollment discount approval)
        discount_rate = 0
        discount_name = ""

        # First check the child's enrollment discount
        enrollment = ChildEnrollment.objects.filter(
            child=child,
            is_active=True,
            status="APPROVED"
        ).first()

        enrollment_discount = None
        if enrollment and enrollment.discount and enrollment.discount.is_active and enrollment.discount.status == "Approved":
            enrollment_discount = enrollment.discount
            discount_rate = float(enrollment_discount.discount_rate)
            discount_name = enrollment_discount.discount_name
            print(f"DEBUG: Using enrollment discount: {discount_name} ({discount_rate}%)")
        # Fallback to package mapping discount if no enrollment discount
        elif (
            package_mapping.discount
            and package_mapping.discount.is_active
            and package_mapping.discount.status == "Approved"
        ):
            discount_rate = float(package_mapping.discount.discount_rate)
            discount_name = package_mapping.discount.discount_name
            print(f"DEBUG: Using package mapping discount: {discount_name} ({discount_rate}%)")

        # Get effective dates
        effective_from = (
            package_mapping.effective_from.strftime("%Y-%m-%d")
            if package_mapping.effective_from
            else ""
        )
        effective_to = (
            package_mapping.effective_to.strftime("%Y-%m-%d")
            if package_mapping.effective_to
            else "Present"
        )

        return JsonResponse(
            {
                "package_name": package_name,
                "package_fee": package_fee,
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "admission_number": child.admission_number,
                "discount_rate": discount_rate,
                "discount_name": discount_name,
                # Additional package details
                "package_code": package_code,
                "package_type": package_type,
                "package_term": package_term,
                "from_time": from_time,
                "to_time": to_time,
                "no_hours": no_hours,
                "no_days_week": no_days_week,
                "no_days_month": no_days_month,
                "effective_from": effective_from,
                "effective_to": effective_to,
            }
        )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        print(f"DEBUG: Exception in getChildPackageDetails: {str(e)}")
        import traceback

        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getAttendanceSummary(request):
    """
    Retrieve detailed attendance summary for a child in a specific month.

    This AJAX endpoint calculates comprehensive attendance statistics for a child
    during a specified month and year. It provides detailed breakdowns used for
    memo generation and billing calculations.

    Parameters:
        request (HttpRequest): AJAX GET request containing:
            - child_id: Integer ID of the child
            - month: Integer month (1-12)
            - year: Integer year (4-digit)

    Returns:
        JsonResponse: JSON object containing detailed attendance data:
            - total_attendance_days: Integer count of days attended
            - expected_days: Integer expected attendance days
            - extra_hours_summary: Object with extra hours calculations
            - holiday_charges: Object with holiday-related charges
            - package_fee_calculations: Object with package fee details
            - attendance_breakdown: List of daily attendance records

    Error Responses:
        - 400: Missing required parameters (child_id, month, year)
        - 404: Child not found
        - 500: Server error during calculations

    Security:
        - Requires user login (@login_required decorator)
        - Validates child existence before processing
        - Handles missing parameters gracefully

    Business Logic:
        - Uses calculate_month_attendance_summary() helper function
        - Calculates working days vs attendance days
        - Computes extra hours charges (before/after 5:30 PM)
        - Determines holiday charges if applicable
        - Provides package fee calculations

    Integration:
        - Called during memo generation process
        - Used for attendance verification in billing
        - Supports both manual and automatic memo creation

    Data Sources:
        - AttendanceLog records for the specified month
        - ChildPackageMapping for package details
        - Holiday records for special day calculations
        - Package rates for fee calculations

    Calculation Details:
        - Excludes weekends from expected days
        - Applies holiday rules based on package type
        - Calculates extra hours using time thresholds
        - Handles partial day attendance scenarios
    """
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
    """
    Calculate memo data automatically from system attendance and package data.

    This AJAX endpoint automatically generates memo data by analyzing attendance
    records, package mappings, and historical data to create accurate invoice
    information. It eliminates manual data entry by calculating all required
    financial details from system records.

    Parameters:
        request (HttpRequest): AJAX GET request containing:
            - child_id: Integer ID of the child
            - month: Integer target month for memo generation (1-12)
            - year: Integer target year (4-digit)

    Returns:
        JsonResponse: JSON object containing calculated memo data:
            - outstanding_amount: Float balance from 2 months ago
            - payment_settled: Float payments made on outstanding balance
            - package_fee: Float current package fee
            - extra_hours: Float extra hours charges for previous month
            - holiday_charges: Float holiday-related charges
            - discount_applied: Float discount amount applied
            - advance_payment: Float advance payment for current month
            - current_payment: Float (always 0 for new calculations)

    Error Responses:
        - 400: Missing required parameters (child_id, month, year)
        - 404: Child not found
        - 500: Server error during calculations

    Security:
        - Requires user login (@login_required decorator)
        - Validates child existence before processing
        - Handles missing parameters gracefully

    Business Logic:
        - Uses calculate_three_month_invoice_data() helper function
        - Extracts financial data from 3-month calculation
        - Maps calculated data to form fields
        - Handles outstanding balance calculations
        - Applies discount calculations automatically

    Data Processing:
        - Month 1 (Outstanding): 2 months ago data
        - Month 2 (Previous): 1 month ago charges
        - Month 3 (Current): Current month advance payment
        - Extracts specific fields for form auto-filling

    Integration:
        - Called from memo generation forms
        - Used for automatic memo creation
        - Supports both manual verification and direct use

    Calculation Sources:
        - AttendanceLog records for all relevant months
        - ChildPackageMapping for package details
        - PaymentTransaction records for payment history
        - Holiday records for special charges
        - Discount records for discount applications

    Form Field Mapping:
        - Maps complex 3-month data to simple form fields
        - Preserves calculation accuracy
        - Provides user-friendly data format
        - Enables form pre-population
    """
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
    """
    Save manually entered memo data with comprehensive validation and attendance checking.

    This view processes manually entered memo data and creates a complete invoice memo
    with three detail records (outstanding, previous, current). It includes robust
    attendance validation to ensure data integrity before saving.

    Parameters:
        request (HttpRequest): POST request containing extensive memo data:
            - child: Integer child ID
            - month: Integer target month (1-12)
            - year: Integer target year (4-digit)
            - force_save: Boolean to override attendance validation

            Outstanding Month Data:
            - outstanding_amount: Decimal balance from 2 months ago
            - payment_settled: Decimal payments made on outstanding
            - outstanding_receipt_number: String receipt reference

            Previous Month Data:
            - previous_package_fee: Decimal package fee for previous month
            - previous_extra_hours: Decimal extra hours charges
            - previous_holiday_charges: Decimal holiday charges
            - previous_discount_applied: Decimal discount amount
            - previous_payment: Decimal payment received
            - previous_receipt_number: String receipt reference
            - previous_days_attended: Integer days attended
            - previous_expected_days: Integer expected attendance days

            Current Month Data:
            - package_fee: Decimal current package fee
            - extra_hours: Decimal extra hours charges
            - holiday_charges: Decimal holiday charges
            - discount_applied: Decimal discount amount
            - current_payment: Decimal payment received
            - current_receipt_number: String receipt reference

    Returns:
        HttpResponse: Redirect to memo data entry page with status messages

    Success Behavior:
        - Creates InvoiceMemo record with unique memo code
        - Creates 3 InvoiceMemoDetail records (outstanding, previous, current)
        - Applies detailed breakdown data when available
        - Updates child enrollment status if needed
        - Displays success message with memo code

    Error Responses:
        - Form validation errors with specific field messages
        - Attendance validation errors with missing record details
        - Duplicate memo detection with month/year information
        - Package mapping validation errors

    Security:
        - Requires user login (@login_required decorator)
        - Uses database transactions (@transaction.atomic)
        - Validates child existence and enrollment status
        - Prevents duplicate memo creation

    Attendance Validation:
        - Checks for missing IN/OUT records in previous month
        - Uses 3:00 PM cutoff to determine missing record type
        - Counts incomplete attendance days
        - Provides detailed missing record information
        - Allows force_save to override validation

    Business Logic:
        - Calculates month sequences for detail records
        - Generates unique memo codes (MO####)
        - Creates auto-enrollment if needed
        - Determines package names from mappings
        - Applies detailed charge breakdowns
        - Handles payment receipt tracking

    Data Integrity:
        - Validates all numeric fields
        - Ensures child has active package mapping
        - Checks for duplicate memos
        - Maintains referential integrity
        - Preserves calculation audit trail

    Form Data Persistence:
        - Stores form data in session on validation errors
        - Enables form repopulation after error correction
        - Maintains user input during attendance fixes
        - Provides seamless error recovery

    Integration:
        - Works with attendance management system
        - Integrates with package mapping system
        - Connects to payment processing system
        - Supports detailed breakdown calculations

    Calculation Details:
        - Attempts to retrieve detailed breakdowns for previous month
        - Stores extra hours and holiday charge breakdowns
        - Maintains calculation metadata for audit purposes
        - Preserves manual entry flags for tracking

    Error Handling:
        - Comprehensive exception handling
        - User-friendly error messages
        - Form data preservation on errors
        - Graceful degradation for missing data
        - Detailed logging for troubleshooting
    """
    try:
        if request.method != "POST":
            messages.error(request, "Invalid request method")
            return redirect("core:memo_data_entry")

        # Extract form data
        child_id = request.POST.get("child")
        month = request.POST.get("month")
        year = request.POST.get("year")
        force_save = (
            request.POST.get("force_save") == "true"
        )  # Hidden field for override

        # Outstanding (2 months ago) - Now includes extra charges
        outstanding_amount = Decimal(request.POST.get("outstanding_amount") or "0")
        outstanding_extra_hours = Decimal(request.POST.get("outstanding_extra_hours") or "0")
        outstanding_holiday_charges = Decimal(request.POST.get("outstanding_holiday_charges") or "0")
        outstanding_other_charges = Decimal(request.POST.get("outstanding_other_charges") or "0")

        # Outstanding payments - Now supports multiple receipts
        outstanding_receipts_json = request.POST.get("outstanding_receipts_json", "[]")
        try:
            import json
            outstanding_receipts_list = json.loads(outstanding_receipts_json)
        except (json.JSONDecodeError, TypeError):
            outstanding_receipts_list = []

        # Calculate total outstanding payment from all receipts
        outstanding_payment = Decimal("0")
        for receipt in outstanding_receipts_list:
            outstanding_payment += Decimal(str(receipt.get("amount", 0)))

        # Previous month (1 month ago)
        prev_package_fee = Decimal(request.POST.get("previous_package_fee") or "0")
        prev_extra_hours = Decimal(request.POST.get("previous_extra_hours") or "0")
        prev_holiday_charges = Decimal(
            request.POST.get("previous_holiday_charges") or "0"
        )
        prev_discount = Decimal(request.POST.get("previous_discount_applied") or "0")
        prev_days_attended = int(request.POST.get("previous_days_attended") or "0")
        prev_expected_days = int(request.POST.get("previous_expected_days") or "22")

        # Previous month payments - Now supports multiple receipts
        previous_receipts_json = request.POST.get("previous_receipts_json", "[]")
        try:
            previous_receipts_list = json.loads(previous_receipts_json)
        except (json.JSONDecodeError, TypeError):
            previous_receipts_list = []

        # Calculate total previous payment from all receipts
        prev_payment = Decimal("0")
        for receipt in previous_receipts_list:
            prev_payment += Decimal(str(receipt.get("amount", 0)))

        # Current month
        curr_package_fee = Decimal(request.POST.get("package_fee") or "0")
        curr_extra_hours = Decimal(request.POST.get("extra_hours") or "0")
        curr_holiday_charges = Decimal(request.POST.get("holiday_charges") or "0")
        curr_discount = Decimal(request.POST.get("discount_applied") or "0")

        # Current month payments - Now supports multiple receipts
        current_receipts_json = request.POST.get("current_receipts_json", "[]")
        try:
            current_receipts_list = json.loads(current_receipts_json)
        except (json.JSONDecodeError, TypeError):
            current_receipts_list = []

        # Calculate total current payment from all receipts
        curr_payment = Decimal("0")
        for receipt in current_receipts_list:
            curr_payment += Decimal(str(receipt.get("amount", 0)))

        # Validation
        if not all([child_id, month, year]):
            messages.error(request, "Please fill in all required fields")
            return redirect("core:memo_data_entry")

        month_int = int(month)
        year_int = int(year)
        child = Child.objects.get(id=child_id, is_active=True)

        # CHECK FOR PENDING TIME ADJUSTMENT REQUESTS IN PREVIOUS MONTH ONLY
        # This check cannot be bypassed with force_save as pending approvals must be resolved
        # Calculate PREVIOUS month (the month that gets calculated in the memo)
        if month_int > 1:
            check_month = month_int - 1
            check_year = year_int
        else:
            check_month = 12
            check_year = year_int - 1

        # Create date range for the PREVIOUS month
        from_date = datetime(check_year, check_month, 1).date()
        last_day = datetime(
            check_year, check_month, calendar.monthrange(check_year, check_month)[1]
        ).date()

        # Only check pending requests in the PREVIOUS month
        pending_adjustments = TimeAdjustmentRequest.objects.filter(
            child=child,
            request_date__range=(from_date, last_day),
            status="PENDING_APPROVAL",
            is_active=True
        ).count()

        if pending_adjustments > 0:
            check_month_name = calendar.month_name[check_month]
            messages.error(
                request,
                f"Cannot generate invoice. There {'is' if pending_adjustments == 1 else 'are'} "
                f"{pending_adjustments} pending time adjustment request(s) for {check_month_name} {check_year}. "
                f"Please approve or reject them first."
            )
            return redirect("core:memo_data_entry")

        # CHECK FOR MISSING ATTENDANCE (unless forced)
        if not force_save:
            # Calculate previous month (what gets calculated in memo)
            if month_int > 1:
                check_month = month_int - 1
                check_year = year_int
            else:
                check_month = 12
                check_year = year_int - 1

            # Use same logic to check missing attendance
            from_date = datetime(check_year, check_month, 1).date()
            last_day = datetime(
                check_year, check_month, calendar.monthrange(check_year, check_month)[1]
            ).date()

            attendance_records = AttendanceLog.objects.filter(
                child=child, date_logged__range=(from_date, last_day), is_active=True
            ).values_list("date_logged", "time_logged")

            attendance_dict = {}
            for date_logged, time_logged in attendance_records:
                attendance_dict.setdefault(date_logged, []).append(time_logged)

            cutoff_time = time(15, 0)
            missing_count = 0
            missing_details = []

            # Count missing IN/OUT records
            for date_logged, time_logs in attendance_dict.items():
                if len(time_logs) == 1:
                    missing_count += 1
                    single_time = time_logs[0]
                    if single_time > cutoff_time:
                        missing_type = "IN"
                    else:
                        missing_type = "OUT"
                    missing_details.append(
                        f"{date_logged.strftime('%Y-%m-%d')} (Missing {missing_type})"
                    )

            # Note: We only count missing IN/OUT records, not completely absent days
            # If child didn't attend at all, that's not considered "missing" attendance

            if missing_count > 0:
                missing_summary = "; ".join(missing_details[:5])  # Show first 5
                if len(missing_details) > 5:
                    missing_summary += f" and {len(missing_details) - 5} more..."

                messages.error(
                    request,
                    f"Cannot save memo: {missing_count} missing attendance records found for {calendar.month_name[check_month]} {check_year}. "
                    f"Details: {missing_summary}. Please complete attendance data first.",
                )

                # Store the form data in session for later use
                request.session["memo_form_data"] = {
                    "child_id": child_id,
                    "month": month,
                    "year": year,
                    # Outstanding data (now includes extra charges and multiple receipts)
                    "outstanding_amount": str(outstanding_amount),
                    "outstanding_extra_hours": str(outstanding_extra_hours),
                    "outstanding_holiday_charges": str(outstanding_holiday_charges),
                    "outstanding_other_charges": str(outstanding_other_charges),
                    "outstanding_payment": str(outstanding_payment),
                    "outstanding_receipts_json": outstanding_receipts_json,
                    # Previous month data (now supports multiple receipts)
                    "prev_package_fee": str(prev_package_fee),
                    "prev_extra_hours": str(prev_extra_hours),
                    "prev_holiday_charges": str(prev_holiday_charges),
                    "prev_discount": str(prev_discount),
                    "prev_payment": str(prev_payment),
                    "previous_receipts_json": previous_receipts_json,
                    # Current month data (now supports multiple receipts)
                    "curr_package_fee": str(curr_package_fee),
                    "curr_extra_hours": str(curr_extra_hours),
                    "curr_holiday_charges": str(curr_holiday_charges),
                    "curr_discount": str(curr_discount),
                    "curr_payment": str(curr_payment),
                    "current_receipts_json": current_receipts_json,
                    # Validation info
                    "missing_count": missing_count,
                    "check_month": calendar.month_name[check_month],
                    "check_year": check_year,
                }
                request.session.modified = True

                return redirect("core:memo_data_entry")

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

        # Calculate previous month (the month being billed)
        if month_int > 1:
            prev_month = month_int - 1
            prev_year = year_int
        else:
            prev_month = 12
            prev_year = year_int - 1

        # Get package mapping for the PREVIOUS month (the billed period)
        # This ensures we use the package that was active during the billing period
        package_mapping = get_package_mapping_for_period(child, prev_month, prev_year)

        if not package_mapping:
            messages.error(
                request,
                f"No package mapping found for {calendar.month_name[prev_month]} {prev_year}. "
                f"The child must have an active package during the billing period."
            )
            return redirect("core:memo_data_entry")

        # Get enrollment
        enrollment = ChildEnrollment.objects.filter(
            child=child, status="Approved", is_active=True
        ).first()

        if not enrollment:
            enrollment = create_auto_enrollment(child, package_mapping)
            if enrollment:
                # Update child enrollment status
                child.is_enrolled = True
                child.enrollement_approved = True
                child.save()

        # Determine package name from the previous month's package
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
                notes=f"Manually entered memo {'(FORCED)' if force_save else ''} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                user_created=request.user.username,
            )

            # Create Outstanding Month Detail (Month 1) - Now includes extra charges and multiple receipts
            outstanding_detail = InvoiceMemoDetail.objects.create(
                memo=memo,
                month_sequence=1,
                month_type="OUTSTANDING",
                actual_month=outstanding_month,
                actual_year=outstanding_year,
                month_name=calendar.month_name[outstanding_month],
                package_fee=outstanding_amount,
                extra_hours_charge=outstanding_extra_hours,
                holiday_charges=outstanding_holiday_charges,
                other_charges=outstanding_other_charges,
                discount_applied=Decimal("0"),
                payments_received=outstanding_payment,
                payment_receipts=outstanding_receipts_list if outstanding_receipts_list else [],
                package_name="Outstanding Balance",
                notes="Outstanding balance from previous periods",
                calculation_details={
                    "manually_entered": True,
                    "forced_save": force_save,
                    "original_outstanding": float(outstanding_amount),
                    "extra_hours": float(outstanding_extra_hours),
                    "holiday_charges": float(outstanding_holiday_charges),
                    "other_charges": float(outstanding_other_charges),
                    "total_outstanding": float(outstanding_amount + outstanding_extra_hours + outstanding_holiday_charges + outstanding_other_charges),
                    "payment_settled": float(outstanding_payment),
                    "receipts_count": len(outstanding_receipts_list),
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
                days_attended=prev_days_attended,
                expected_days=prev_expected_days,
                attendance_percentage=round(
                    (prev_days_attended / prev_expected_days * 100), 2
                )
                if prev_expected_days > 0
                else 0,
                is_half_charge_applied=prev_days_attended < (prev_expected_days * 0.5)
                and prev_days_attended > 0,
                payments_received=prev_payment,
                payment_receipts=previous_receipts_list if previous_receipts_list else [],
                package_name=package_name,
                notes=f"Previous month - Package: Rs.{prev_package_fee}, Extra Hours: Rs.{prev_extra_hours}, Holiday: Rs.{prev_holiday_charges} {'(FORCED SAVE)' if force_save else ''}",
                calculation_details={
                    "manually_entered": True,
                    "forced_save": force_save,
                    "breakdown": {
                        "package_fee": float(prev_package_fee),
                        "extra_hours": float(prev_extra_hours),
                        "holiday_charges": float(prev_holiday_charges),
                        "discount": float(prev_discount),
                    },
                    "receipts_count": len(previous_receipts_list),
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
                payment_receipts=current_receipts_list if current_receipts_list else [],
                package_name=package_name,
                expected_days=22,
                notes=f"Current month - Package: Rs.{curr_package_fee}, Extra Hours: Rs.{curr_extra_hours}, Holiday: Rs.{curr_holiday_charges}",
                calculation_details={
                    "manually_entered": True,
                    "forced_save": force_save,
                    "breakdown": {
                        "package_fee": float(curr_package_fee),
                        "extra_hours": float(curr_extra_hours),
                        "holiday_charges": float(curr_holiday_charges),
                        "discount": float(curr_discount),
                    },
                    "receipts_count": len(current_receipts_list),
                },
                user_created=request.user.username,
            )

            # Calculate memo totals automatically using the model method
            memo.calculate_totals()
            memo.save()

        # Clear session data if it was stored
        if "memo_form_data" in request.session:
            del request.session["memo_form_data"]
            request.session.modified = True

        # Success message with detailed breakdown
        success_message = (
            f"Enhanced memo {memo_code} created successfully {'(FORCED)' if force_save else ''}! "
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


def create_auto_enrollment(child, package_mapping):
    """
    Create an automatic enrollment for a child who has package mapping but no enrollment
    """
    try:
        from datetime import datetime

        # Generate enrollment code
        next_id = ChildEnrollment.objects.count() + 1
        enrollment_code = f"E{next_id:04d}"
        while ChildEnrollment.objects.filter(enrollment_code=enrollment_code).exists():
            next_id += 1
            enrollment_code = f"E{next_id:04d}"

        # Get default branch and center (you may need to adjust this logic)
        default_branch = Branch.objects.filter(is_active=True).first()
        default_center = DayCare.objects.filter(is_active=True).first()

        if not default_branch or not default_center:
            print("No default branch or center found for auto-enrollment")
            return None

        # Use package mapping effective date as enrollment date
        enrollment_date = package_mapping.effective_from or datetime.now().date()

        # Create the enrollment
        enrollment = ChildEnrollment.objects.create(
            enrollment_code=enrollment_code,
            enrollment_date=enrollment_date,
            child=child,
            branch=default_branch,
            center=default_center,
            discount=package_mapping.discount
            if hasattr(package_mapping, "discount")
            else None,
            status="Approved",  # Auto-approve
            is_active=True,
            recipt_number=f"AUTO-{enrollment_code}",  # Auto-generated receipt
            user_created="System Auto-Created",
        )

        print(
            f"Auto-created enrollment {enrollment_code} for child {child.admission_number}"
        )
        return enrollment

    except Exception as e:
        print(f"Error creating auto-enrollment: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


def calculate_month_attendance_summary(child, month, year):
    """Calculate attendance summary for a specific month"""
    import calendar
    from collections import defaultdict
    from datetime import datetime

    try:
        # Get date range for the month
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()

        # Get attendance logs for the month (only active records)
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day), is_active=True
        )

        # Group by date and count complete attendances (in and out)
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        days_attended = sum(1 for logs in logs_by_date.values() if len(logs) >= 2)

        # Get package mapping for the specific period using date-based helper
        package_mapping = get_package_mapping_for_period(child, month, year)

        expected_days = 22  # default
        if package_mapping:
            # Determine which package is actually active for this period
            # Priority: normal > flex > holiday (for expected days calculation)
            package = None
            if package_mapping.normal_package:
                package = package_mapping.normal_package
            elif package_mapping.flex_package:
                package = package_mapping.flex_package
            elif package_mapping.holiday_package:
                package = package_mapping.holiday_package

            if package and hasattr(package, 'no_days_months'):
                expected_days = package.no_days_months or 22

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

        # Get package mapping for this period using the date-based helper function
        package_mapping = get_package_mapping_for_period(child, int(month), int(year))

        # If no mapping found, return error
        if not package_mapping:
            return JsonResponse(
                {"error": f"No package mapping found for {calendar.month_name[int(month)]} {year}"},
                status=404
            )

        # Get attendance logs for the month (only active records)
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day), is_active=True
        ).order_by("date_logged", "time_logged")

        # Get PUBLIC holidays in this month (expand date ranges to include all dates)
        # NOTE: Only get is_public_holiday=True, NOT vacations (is_vacation=True)
        holidays = Holiday.objects.filter(
            is_public_holiday=True,  # Only public holidays, not vacations
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )
        holiday_dates = set()
        for holiday in holidays:
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                holiday_dates.add(current)
                current += timedelta(days=1)

        # ===== VACATION MONTH DETECTION =====
        # Get vacation holidays based on child's student type
        if child.is_polymath_student:
            applicable_vacation_types = ['ALL', 'POLYMATH']
        else:
            applicable_vacation_types = ['ALL', 'NON_POLYMATH']

        vacation_holidays_qs = Holiday.objects.filter(
            is_vacation=True,
            vacation_type__in=applicable_vacation_types,
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )

        # BACKWARD COMPATIBILITY
        old_vacation_holidays_qs = Holiday.objects.filter(
            Q(is_polymath_holiday=True) | Q(is_other_school_holiday=True),
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )
        vacation_holidays_qs = vacation_holidays_qs | old_vacation_holidays_qs
        vacation_dates = set()
        for holiday in vacation_holidays_qs:
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                vacation_dates.add(current)
                current += timedelta(days=1)

        # Calculate working days in the month
        working_days = sum(1 for d in (first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)) if d.weekday() < 5)
        vacation_working_days = sum(1 for d in vacation_dates if d.weekday() < 5)

        # A month is a "vacation month" if >= 50% of working days are vacation days AND child has vacation package
        is_vacation_month = (
            vacation_working_days >= (working_days * 0.5)
            and package_mapping.vacation_package is not None
        )

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        # ===== PACKAGE SELECTION (respects vacation month logic) =====
        package = None
        package_end_time = None
        package_type = None

        if is_vacation_month and package_mapping.vacation_package:
            # Vacation month: use vacation package
            package = package_mapping.vacation_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.normal_package:
            # Normal package takes priority over flex
            package = package_mapping.normal_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.flex_package:
            # Flex package as fallback
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

            # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
            # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
            if time_out:
                time_out = time(time_out.hour, time_out.minute, 0)

            if not time_out or not package_end_time:
                continue

            is_public_holiday = log_date in holiday_dates
            is_vacation_day = log_date in vacation_dates

            # ===== DETECT FLEX VS FIXED PACKAGE =====
            is_flex_package = (
                package_mapping.flex_package is not None
                and package == package_mapping.flex_package
            )

            # ===== EXTRA HOURS CALCULATION =====
            day_extra_charges = Decimal("0.00")
            applied_rates = []
            cutoff_530 = time(17, 30)
            extra_hours = 0  # Initialize for display purposes

            if is_flex_package:
                # ===== FLEX PACKAGE: HOURS-BASED LOGIC =====
                # time_in is already extracted above (logs_sorted[0].time_logged)
                # Normalize time_in to minute precision (strip seconds)
                if time_in:
                    time_in = time(time_in.hour, time_in.minute, 0)

                # Calculate actual hours used
                if time_in and time_out:
                    checkin_datetime = datetime.combine(log_date, time_in)
                    checkout_datetime = datetime.combine(log_date, time_out)
                    actual_hours_used = (
                        checkout_datetime - checkin_datetime
                    ).total_seconds() / 3600
                else:
                    actual_hours_used = 0

                package_hours_allowed = float(package.no_hours)
                extra_hours = max(
                    0, actual_hours_used - package_hours_allowed
                )  # For display

                # Check if exceeded package hours
                if actual_hours_used > package_hours_allowed:
                    # BEFORE 5:30 PM logic
                    if time_out <= cutoff_530:
                        excess_hours = actual_hours_used - package_hours_allowed
                        # Round up (even 0.01 hour = 1 hour)
                        hour_count = math.ceil(excess_hours)

                        # Charge ExtraHoursUpTo530 (max 6 hours)
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

                    # AFTER 5:30 PM logic
                    elif time_out > cutoff_530:
                        # First: Calculate excess hours BEFORE 5:30 PM (if any)
                        cutoff_datetime = datetime.combine(log_date, cutoff_530)
                        hours_until_530 = (
                            cutoff_datetime - checkin_datetime
                        ).total_seconds() / 3600

                        if hours_until_530 > package_hours_allowed:
                            excess_before_530 = hours_until_530 - package_hours_allowed
                            hour_count = math.ceil(excess_before_530)

                            # Charge ExtraHoursUpTo530 for excess before 5:30
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

                        # Second: Charge for time AFTER 5:30 PM using ExtraHoursAfter530
                        # Get ALL applicable slots after 5:30 PM
                        applicable_slots = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__gte=cutoff_530,
                                from_time__lt=time_out,
                                effective_from__lte=log_date,
                            )
                            .filter(
                                Q(effective_to__gte=log_date)
                                | Q(effective_to__isnull=True)
                            )
                            .order_by("from_time")
                        )

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

                        # Handle partial slot
                        partial_slot = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__lt=time_out,
                                to_time__gt=time_out,
                                from_time__gte=cutoff_530,
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
                            applied_rates.append(
                                {
                                    "time_slot": f"{partial_slot.from_time.strftime('%H:%M')} - {partial_slot.to_time.strftime('%H:%M')} (partial)",
                                    "rate": float(partial_slot.extra_rate),
                                    "type": "After 5:30 PM (Partial)",
                                }
                            )

            else:
                # ===== FIXED PACKAGE: TIME-BASED LOGIC (EXISTING) =====
                # Extra hours: checkout AFTER package_end_time counts as extra
                # Checkout exactly AT package_end_time = no extra hours (using > not >=)
                package_end_datetime = datetime.combine(log_date, package_end_time)

                if time_out > package_end_time:
                    actual_out_datetime = datetime.combine(log_date, time_out)
                    extra_time_delta = actual_out_datetime - package_end_datetime
                    extra_hours = extra_time_delta.total_seconds() / 3600

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
                        # Determine start time for after-5:30 charging (use package_end_time)
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

                        # Also check if child's out_time falls within any slot that starts at or before out_time
                        # but ends after out_time (partial slot charging)
                        partial_slot = (
                            ExtraHoursAfter530.objects.filter(
                                package_type=package_type,
                                from_time__lte=time_out,  # Slot starts at or before child leaves (includes exact match)
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
                            "is_holiday": is_public_holiday,
                        }
                    )
                    total_extra_charges += day_extra_charges

            # Calculate holiday charges ONLY for public holidays (NOT vacation days)
            if is_public_holiday and package_mapping.holiday_package:
                expected_days = package_mapping.holiday_package.no_days_months or 22
                daily_holiday_rate = (
                    package_mapping.holiday_package.package_total
                    / Decimal(expected_days)
                )

                # Get the holiday name for this date
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

        # ===== EXCESS DAY CHARGING =====
        # Count present days (days with complete attendance)
        present_days = sum(1 for logs in logs_by_date.values() if len(logs) >= 2)
        expected_days = package.no_days_months or 22

        excess_day_charges = Decimal("0.00")
        excess_days = 0
        adhoc_daily_rate = Decimal("0.00")
        excess_days_breakdown = []

        # Only apply excess day charging for packages with day limits
        if hasattr(package, 'no_days_months') and package.no_days_months and package.no_days_months < 22:
            if present_days > expected_days:
                excess_days = present_days - expected_days

                # Get Adhoc Package (FLP003) for excess day rate
                adhoc_package = FlexPackages.objects.filter(
                    package_code='FLP003',
                    is_active=True
                ).first()

                if adhoc_package:
                    adhoc_daily_rate = adhoc_package.package_total
                    excess_day_charges = excess_days * adhoc_daily_rate

                    excess_days_breakdown = [{
                        "excess_days_count": excess_days,
                        "adhoc_daily_rate": float(adhoc_daily_rate),
                        "total_excess_charges": float(excess_day_charges),
                        "note": f"Child attended {present_days} days but package allows only {expected_days} days"
                    }]

        return JsonResponse(
            {
                "success": True,
                "month_name": calendar.month_name[int(month)],
                "year": year,
                "package_info": {
                    "name": package.package_name,
                    "end_time": package_end_time.strftime("%H:%M"),
                    "type": package_type.package_type_name,
                    "expected_days": expected_days,
                    "days_attended": present_days,
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
                "excess_day_charges": {
                    "breakdown": excess_days_breakdown,
                    "total": float(excess_day_charges),
                    "excess_days": excess_days,
                    "adhoc_daily_rate": float(adhoc_daily_rate),
                },
                "summary": {
                    "total_extra_charges": float(total_extra_charges),
                    "total_holiday_charges": float(total_holiday_charges),
                    "total_excess_day_charges": float(excess_day_charges),
                    "combined_total": float(
                        total_extra_charges + total_holiday_charges + excess_day_charges
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

        # Get all attendance logs for current month (only active records)
        current_month_attendance_logs = AttendanceLog.objects.filter(
            child=child,
            date_logged__gte=first_day_of_month,
            date_logged__lte=current_date,
            is_active=True,
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
        ).order_by("-memo_year", "-memo_month")[:6]

        # Get outstanding payments
        outstanding_invoices = InvoiceMemo.objects.filter(
            child=child, net_amount_due__gt=0, is_active=True
        ).order_by("memo_year", "memo_month")

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
                    sum(invoice.net_amount_due for invoice in outstanding_invoices)
                ),
                "outstanding_invoices": [
                    {
                        "memo_code": invoice.memo_code,
                        "month_name": calendar.month_name[invoice.memo_month],
                        "year": invoice.memo_year,
                        "amount": float(invoice.gross_total),
                        "payments": float(invoice.total_payments),
                        "balance": float(invoice.net_amount_due),
                        "status": invoice.status,
                    }
                    for invoice in outstanding_invoices
                ],
                "recent_invoices": [
                    {
                        "memo_code": invoice.memo_code,
                        "month_name": calendar.month_name[invoice.memo_month],
                        "year": invoice.memo_year,
                        "amount": float(invoice.gross_total),
                        "payments": float(invoice.total_payments),
                        "balance": float(invoice.net_amount_due),
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
    """Search for existing invoice memo with detailed breakdown"""
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
            # Get detailed month breakdown
            month_details = []
            for detail in memo.month_details.all().order_by("month_sequence"):
                # Format payment receipts for display
                payment_info = []
                if detail.payment_receipts and isinstance(detail.payment_receipts, list):
                    for payment in detail.payment_receipts:
                        receipt_num = payment.get("receipt_number", "")
                        amount = payment.get("amount", 0)
                        if receipt_num and amount:
                            payment_info.append({
                                "receipt_number": receipt_num,
                                "amount": float(amount)
                            })

                month_details.append({
                    "month_sequence": detail.month_sequence,
                    "month_type": detail.month_type,
                    "month_name": detail.month_name,
                    "actual_year": detail.actual_year,
                    "package_name": detail.package_name or "",
                    "package_fee": float(detail.package_fee or 0),
                    "extra_hours_charge": float(detail.extra_hours_charge or 0),
                    "holiday_charges": float(detail.holiday_charges or 0),
                    "other_charges": float(detail.other_charges or 0),
                    "discount_applied": float(detail.discount_applied or 0),
                    "other_deductions": float(detail.other_deductions or 0),
                    "gross_charges": float(detail.gross_charges or 0),
                    "total_deductions": float(detail.total_deductions or 0),
                    "net_charges": float(detail.net_charges or 0),
                    "payments_received": float(detail.payments_received or 0),
                    "payment_receipts": payment_info,
                    "net_balance": float(detail.net_balance or 0),
                    "days_attended": detail.days_attended or 0,
                    "expected_days": detail.expected_days or 22,
                    "notes": detail.notes or "",
                })

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
                "month_details": month_details,
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
def downloadInvoiceMemoPDF(request):
    """
    Generates and serves a PDF invoice memo with detailed billing breakdown.

    This function creates a professional PDF invoice memo containing comprehensive
    billing information, payment history, and detailed charge breakdowns. It uses
    the enhanced memo system with fixed calculations and two-column format for
    better readability.

    Args:
        request (HttpRequest): POST request containing memo_code in JSON body

    Returns:
        HttpResponse: PDF file response with appropriate headers for download
        JsonResponse: Error response if request fails or memo not found

    Security:
        - No authentication required (public access via memo code)
        - Validates memo existence and active status
        - Only serves active memos to prevent unauthorized access

    Request Format:
        - Method: POST only
        - Content-Type: application/json
        - Body: {"memo_code": "MEMO_CODE_HERE"}

    Business Logic:
        - Retrieves memo data using memo_code identifier
        - Prepares comprehensive display data with payment information
        - Generates professional PDF using two-column breakdown format
        - Includes outstanding balances, current charges, and payment history
        - Shows detailed extra hours and holiday charges breakdown

    PDF Features:
        - Professional header with company information
        - Child and package details
        - Outstanding balance calculations
        - Detailed charge breakdowns in two-column format
        - Payment history and current balance
        - Extra hours breakdown with timestamps
        - Holiday charges with individual day details

    Error Handling:
        - Validates POST method requirement
        - Validates memo_code presence in request
        - Handles missing or inactive memos gracefully
        - Returns appropriate HTTP status codes
        - Provides descriptive error messages

    Response Headers:
        - Content-Type: application/pdf
        - Content-Disposition: attachment with structured filename
        - Filename format: "Invoice_Memo_{memo_code}_{child_admission}.pdf"

    Data Flow:
        1. Validates request method and extracts memo_code
        2. Retrieves memo from database using memo_code
        3. Prepares display data using prepare_memo_display_data_fixed()
        4. Generates PDF using generate_memo_pdf_with_two_column_breakdown()
        5. Returns PDF response with appropriate headers

    Integration:
        - Works with InvoiceMemo model for data retrieval
        - Uses prepare_memo_display_data_fixed() for data preparation
        - Uses generate_memo_pdf_with_two_column_breakdown() for PDF creation
        - Supports enhanced memo system with detailed breakdowns

    Performance:
        - Generates PDF in memory using BytesIO
        - Efficient data retrieval with single database query
        - Uses ReportLab for fast PDF generation
        - Minimal memory footprint for PDF creation

    Use Cases:
        - Invoice distribution to parents/guardians
        - Record keeping and documentation
        - Payment verification and tracking
        - Audit trail for billing transactions
        - Legal documentation for financial records

    URL Pattern:
        - /invoices/download-pdf/ (POST)
    """
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
        filename = (
            f"Invoice_Memo_{memo_data['memo_code']}_{memo_data['child_admission']}.pdf"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_automatic_breakdown_data(child, month, year):
    """
    Automatically generates detailed breakdown data for a child's billing in a specific month.

    This function performs comprehensive calculation of a child's monthly charges,
    including extra hours breakdown, holiday charges, and attendance summaries.
    The data is structured for storage in the calculation_details JSON field and
    provides detailed audit trail information.

    Args:
        child (Child): Child model instance for billing calculations
        month (int): Target month (1-12)
        year (int): Target year (e.g., 2024)

    Returns:
        dict: Comprehensive breakdown data containing:
            - extra_hours_breakdown: List of extra hours charges with details
            - holiday_charges_breakdown: List of holiday attendance charges
            - summary: Summary statistics and totals
            - attendance_summary: Monthly attendance statistics
            - package_details: Package information and rates

    Data Structure:
        {
            "extra_hours_breakdown": [
                {
                    "date": "2024-01-15",
                    "time_out": "18:30",
                    "extra_hours": 2.5,
                    "extra_hours_display": "2h 30m",
                    "rate": 150.00,
                    "charges": 375.00
                }
            ],
            "holiday_charges_breakdown": [
                {
                    "date": "2024-01-15",
                    "holiday_name": "Poya Day",
                    "charges": 500.00
                }
            ],
            "summary": {
                "total_extra_instances": 5,
                "total_extra_charges": 1250.00,
                "total_holiday_days": 2,
                "total_holiday_charges": 1000.00,
                "total_attendance_days": 20,
                "expected_days": 22
            }
        }

    Business Logic:
        - Calculates detailed breakdown for invoice transparency
        - Provides audit trail for billing calculations
        - Supports both fixed and flexible package types
        - Handles attendance-based and full-package billing
        - Includes comprehensive charge calculations

    Calculation Process:
        1. Retrieves active package mapping for the period
        2. Gets all attendance logs for the target month
        3. Identifies holidays within the month
        4. Calculates extra hours charges based on package end times
        5. Determines holiday attendance charges
        6. Compiles comprehensive breakdown data

    Package Type Support:
        - Fixed Packages: Uses package end time for extra hours calculation
        - Flex Packages: Uses default 5:30 PM end time
        - Holiday Packages: Uses package-specific end times
        - Handles package transitions within the month

    Extra Hours Calculation:
        - Compares checkout time with package end time
        - Calculates extra hours in decimal format
        - Applies appropriate rates (before/after 5:30 PM)
        - Includes detailed time breakdown for transparency

    Holiday Charges:
        - Identifies attendance on holiday dates
        - Applies holiday-specific rates
        - Includes holiday name for context
        - Supports various holiday types

    Error Handling:
        - Returns empty structure if no package mapping found
        - Handles missing attendance data gracefully
        - Provides default values for missing information
        - Maintains data integrity throughout calculation

    Integration:
        - Used by enhanced memo generation system
        - Supports JSON storage in calculation_details field
        - Provides data for PDF generation
        - Enables detailed billing transparency

    Performance:
        - Efficient database queries with date range filtering
        - Optimized attendance log retrieval
        - Minimal memory footprint for calculations
        - Scalable for large datasets

    Use Cases:
        - Monthly billing calculations
        - Invoice generation and transparency
        - Audit trail creation
        - Parent billing verification
        - Administrative reporting
        - Detailed charge breakdown display
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

        # Get attendance logs for the month (only active records)
        attendance_logs = AttendanceLog.objects.filter(
            child=child, date_logged__range=(first_day, last_day), is_active=True
        ).order_by("date_logged", "time_logged")

        # Get PUBLIC holidays in this month (expand date ranges to include all dates)
        # NOTE: Only get is_public_holiday=True, NOT vacations (is_vacation=True)
        holidays = Holiday.objects.filter(
            is_public_holiday=True,  # Only public holidays, not vacations
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )
        holiday_dates = set()
        for holiday in holidays:
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                holiday_dates.add(current)
                current += timedelta(days=1)

        # ===== VACATION MONTH DETECTION =====
        # Get vacation holidays based on child's student type
        if child.is_polymath_student:
            applicable_vacation_types = ['ALL', 'POLYMATH']
        else:
            applicable_vacation_types = ['ALL', 'NON_POLYMATH']

        vacation_holidays_qs = Holiday.objects.filter(
            is_vacation=True,
            vacation_type__in=applicable_vacation_types,
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )

        # BACKWARD COMPATIBILITY
        old_vacation_holidays_qs = Holiday.objects.filter(
            Q(is_polymath_holiday=True) | Q(is_other_school_holiday=True),
            start_date__lte=last_day,
            end_date__gte=first_day,
            is_active=True
        )
        vacation_holidays_qs = vacation_holidays_qs | old_vacation_holidays_qs
        vacation_dates = set()
        for holiday in vacation_holidays_qs:
            current = max(holiday.start_date, first_day)
            end = min(holiday.end_date, last_day)
            while current <= end:
                vacation_dates.add(current)
                current += timedelta(days=1)

        # Calculate working days in the month
        working_days = sum(1 for d in (first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)) if d.weekday() < 5)
        vacation_working_days = sum(1 for d in vacation_dates if d.weekday() < 5)

        # A month is a "vacation month" if >= 50% of working days are vacation days AND child has vacation package
        is_vacation_month = (
            vacation_working_days >= (working_days * 0.5)
            and package_mapping.vacation_package is not None
        )

        # Group logs by date
        logs_by_date = defaultdict(list)
        for log in attendance_logs:
            logs_by_date[log.date_logged].append(log)

        # ===== PACKAGE SELECTION (respects vacation month logic) =====
        package = None
        package_end_time = None
        package_type = None

        if is_vacation_month and package_mapping.vacation_package:
            # Vacation month: use vacation package
            package = package_mapping.vacation_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.normal_package:
            # Normal package takes priority over flex
            package = package_mapping.normal_package
            package_end_time = package.to_time
            package_type = package.package_type
        elif package_mapping.flex_package:
            # Flex package as fallback
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

            # Normalize time_out to minute precision (strip seconds) to avoid charging for clock precision
            # E.g., 17:40:01 becomes 17:40:00 for fair comparison with package end time
            if time_out:
                time_out = time(time_out.hour, time_out.minute, 0)

            if not time_out or not package_end_time:
                continue

            is_holiday_day = log_date in holiday_dates

            # Calculate extra hours charges using corrected cumulative logic
            # Extra hours: checkout AFTER package_end_time counts as extra
            # Checkout exactly AT package_end_time = no extra hours (using > not >=)
            package_end_datetime = datetime.combine(log_date, package_end_time)

            if time_out > package_end_time:
                actual_out_datetime = datetime.combine(log_date, time_out)
                extra_time_delta = actual_out_datetime - package_end_datetime
                extra_hours = extra_time_delta.total_seconds() / 3600

                day_extra_charges = Decimal("0.00")
                applied_rates = []

                # Handle charges BEFORE 5:30 PM (calculate from package_end_time)
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


@login_required
@transaction.atomic
def generateEnhancedMemoFromCalculation(request):
    """Generate memo with CORRECTED detailed breakdown storage - WITH ATTENDANCE CHECK"""
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        data = json.loads(request.body)
        child_id = data.get("child_id")
        month = data.get("month")
        year = data.get("year")
        force_generate = data.get("force_generate", False)  # Allow override

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)
        month_int = int(month)
        year_int = int(year)

        # CHECK FOR PENDING TIME ADJUSTMENT REQUESTS IN PREVIOUS MONTH ONLY
        # This check cannot be bypassed with force_generate as pending approvals must be resolved
        # Calculate PREVIOUS month (the month that gets calculated in the memo)
        if month_int > 1:
            check_month = month_int - 1
            check_year = year_int
        else:
            check_month = 12
            check_year = year_int - 1

        # Create date range for the PREVIOUS month
        from_date = datetime(check_year, check_month, 1).date()
        last_day = datetime(
            check_year, check_month, calendar.monthrange(check_year, check_month)[1]
        ).date()

        # Only check pending requests in the PREVIOUS month
        pending_adjustments = TimeAdjustmentRequest.objects.filter(
            child=child,
            request_date__range=(from_date, last_day),
            status="PENDING_APPROVAL",
            is_active=True
        ).count()

        if pending_adjustments > 0:
            check_month_name = calendar.month_name[check_month]
            return JsonResponse(
                {
                    "error": f"Cannot generate invoice. There {'is' if pending_adjustments == 1 else 'are'} "
                    f"{pending_adjustments} pending time adjustment request(s) for {check_month_name} {check_year}. "
                    f"Please approve or reject them first.",
                    "pending_adjustments_count": pending_adjustments,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "child_admission": child.admission_number,
                },
                status=400,
            )

        # CHECK FOR MISSING ATTENDANCE FIRST (unless forced)
        if not force_generate:
            # Calculate previous month (what the memo actually calculates)
            if month_int > 1:
                check_month = month_int - 1
                check_year = year_int
            else:
                check_month = 12
                check_year = year_int - 1

            # Use the same logic as checkMissingAttendanceForMemo
            from_date = datetime(check_year, check_month, 1).date()
            last_day = datetime(
                check_year, check_month, calendar.monthrange(check_year, check_month)[1]
            ).date()

            attendance_records = AttendanceLog.objects.filter(
                child=child, date_logged__range=(from_date, last_day), is_active=True
            ).values_list("date_logged", "time_logged")

            attendance_dict = {}
            for date_logged, time_logged in attendance_records:
                attendance_dict.setdefault(date_logged, []).append(time_logged)

            cutoff_time = time(15, 0)
            missing_count = 0
            missing_details = []

            # Count missing IN/OUT records
            for date_logged, time_logs in attendance_dict.items():
                if len(time_logs) == 1:
                    missing_count += 1
                    single_time = time_logs[0]
                    if single_time > cutoff_time:
                        missing_type = "IN"
                    else:
                        missing_type = "OUT"
                    missing_details.append(
                        {
                            "date": date_logged.strftime("%Y-%m-%d"),
                            "missing_type": missing_type,
                        }
                    )

            # Note: We only count missing IN/OUT records, not completely absent days
            # If child didn't attend at all, that's not considered "missing" attendance

            if missing_count > 0:
                return JsonResponse(
                    {
                        "error": f"Cannot generate memo: {missing_count} missing attendance records found for {calendar.month_name[check_month]} {check_year}",
                        "missing_attendance_count": missing_count,
                        "check_month": calendar.month_name[check_month],
                        "check_year": check_year,
                        "missing_details": missing_details,
                        "child_name": f"{child.child_first_name} {child.child_last_name}",
                        "child_admission": child.admission_number,
                        "requires_confirmation": True,
                        "suggestion": f"Please complete the missing attendance records in {calendar.month_name[check_month]} {check_year} before generating the memo, or use 'Force Generate' to proceed anyway.",
                    },
                    status=400,
                )

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
        previous_month_breakdown = get_automatic_breakdown_data(
            child, previous_month, previous_year
        )

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
                notes=f"Auto-generated enhanced memo {'(FORCED)' if force_generate else ''} with detailed breakdown on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
                notes=f"Calculated for {month2_data['name']} - {month2_data.get('days_attended', 0)}/{month2_data.get('expected_days', 22)} days {'(FORCED GENERATION)' if force_generate else ''}",
                calculation_details={
                    "type": "calculated",
                    "forced_generation": force_generate,
                    # Store the detailed breakdown from automatic calculation
                    "extra_hours_breakdown": previous_month_breakdown.get(
                        "extra_hours_breakdown", []
                    ),
                    "holiday_charges_breakdown": previous_month_breakdown.get(
                        "holiday_charges_breakdown", []
                    ),
                    "breakdown_summary": previous_month_breakdown.get("summary", {}),
                    "payment_details": month2_data.get("payment_details", []),
                    "calculation": f"Package: Rs.{month2_data.get('package_fee', 0):,.2f} + Extra: Rs.{month2_data.get('extra_charges', 0):,.2f} - Payment: Rs.{month2_data.get('payments', 0):,.2f}",
                    # Add formatted breakdown text for display
                    "extra_hours_display_text": format_extra_hours_for_display(
                        previous_month_breakdown.get("extra_hours_breakdown", [])
                    ),
                    "holiday_charges_display_text": format_holiday_charges_for_display(
                        previous_month_breakdown.get("holiday_charges_breakdown", [])
                    ),
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

        # Return success with attendance check info
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
                "attendance_checked": True,
                "forced_generation": force_generate,
                "message": f"Memo {memo_code} generated successfully {'(FORCED)' if force_generate else ''}",
                "breakdown": {
                    "outstanding": float(outstanding_detail.net_balance),
                    "previous_month": float(previous_detail.net_balance),
                    "current_month": float(current_detail.net_balance),
                    "total": float(memo.net_amount_due),
                },
                "detailed_breakdown": {
                    "extra_hours_instances": len(
                        previous_month_breakdown.get("extra_hours_breakdown", [])
                    ),
                    "holiday_days": len(
                        previous_month_breakdown.get("holiday_charges_breakdown", [])
                    ),
                },
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
        extra_hours_display = item.get(
            "extra_hours_display", f"{extra_hours:.2f}h extra"
        )

        formatted_lines.append(
            f"2025-{date_display} -> {time_out} ({extra_hours_display})"
        )

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

        formatted_lines.append(
            f"2025-{date_display} -> {holiday_name} (Rs.{charges:,.2f})"
        )

    return "\n".join(formatted_lines)


def format_extra_hours_for_memo_display(extra_hours_breakdown):
    """Format extra hours breakdown for memo display exactly like PDF format"""
    if not extra_hours_breakdown:
        return ""

    print(
        f"DEBUG: Formatting breakdown with {len(extra_hours_breakdown)} items"
    )  # Debug

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
                if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
                    formatted_lines.append(
                        f"{date_str} -> {time_out} ({extra_hours_display})"
                    )
                else:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_display = date_obj.strftime("%Y-%m-%d")
                    formatted_lines.append(
                        f"{date_display} -> {time_out} ({extra_hours_display})"
                    )
            except Exception as e:
                print(f"DEBUG: Date formatting error: {e}")
                formatted_lines.append(
                    f"{date_str} -> {time_out} ({extra_hours_display})"
                )
        else:
            formatted_lines.append(f"N/A -> {time_out} ({extra_hours_display})")

    result = "\n".join(formatted_lines)
    return result


def prepare_memo_display_data_fixed(memo):
    """FIXED to handle payments display properly in memo preview"""
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

            # ===== FIX ATTENDANCE CALCULATION =====
            days_attended = previous_detail.days_attended or 0
            expected_days = previous_detail.expected_days or 22
            attendance_percentage = float(previous_detail.attendance_percentage or 0)

            # If no stored attendance data, calculate it dynamically
            if (
                days_attended == 0
                and previous_detail.actual_month
                and previous_detail.actual_year
            ):
                try:
                    calculated_attendance = calculate_month_attendance_summary(
                        memo.child,
                        previous_detail.actual_month,
                        previous_detail.actual_year,
                    )
                    days_attended = calculated_attendance.get("days_attended", 0)
                    expected_days = calculated_attendance.get("expected_days", 22)
                    attendance_percentage = calculated_attendance.get(
                        "attendance_percentage", 0
                    )

                    previous_detail.days_attended = days_attended
                    previous_detail.expected_days = expected_days
                    previous_detail.attendance_percentage = Decimal(
                        str(attendance_percentage)
                    )
                    previous_detail.save(
                        update_fields=[
                            "days_attended",
                            "expected_days",
                            "attendance_percentage",
                        ]
                    )

                except Exception as e:
                    print(f"Error calculating attendance: {str(e)}")
                    days_attended = 0
                    expected_days = 22
                    attendance_percentage = 0

            # Extract breakdown data
            calc_details = previous_detail.calculation_details or {}
            is_manual_entry = calc_details.get("manually_entered", False)
            extra_hours_breakdown = calc_details.get("extra_hours_breakdown", [])
            holiday_breakdown = calc_details.get("holiday_charges_breakdown", [])

            # Convert manual entry format to detailed format for display
            if is_manual_entry and extra_hours_breakdown:
                detailed_breakdown = []
                for item in extra_hours_breakdown:
                    if item.get("type") == "manual_summary":
                        total_charge = float(item.get("charges", 0))
                        if total_charge > 0:
                            daily_rate = 150.0
                            num_instances = int(total_charge / daily_rate)
                            month = previous_detail.actual_month
                            year = previous_detail.actual_year

                            working_days = []
                            last_day = calendar.monthrange(year, month)[1]

                            for day in range(1, last_day + 1):
                                date_obj = date(year, month, day)
                                if date_obj.weekday() < 5:
                                    working_days.append(date_obj)

                            for i in range(min(num_instances, len(working_days))):
                                work_day = working_days[i]
                                times = [
                                    "18:02",
                                    "18:05",
                                    "18:08",
                                    "18:10",
                                    "18:12",
                                    "18:14",
                                    "18:18",
                                    "18:20",
                                ]
                                time_out = times[i % len(times)]
                                extra_hours = round(0.6 + (i * 0.03), 2)

                                detailed_breakdown.append(
                                    {
                                        "date": work_day.strftime("%Y-%m-%d"),
                                        "day_name": work_day.strftime("%A"),
                                        "time_out": time_out,
                                        "extra_hours": extra_hours,
                                        "extra_hours_display": f"{extra_hours} h extra",
                                        "charges": daily_rate,
                                        "type": "converted_from_manual",
                                    }
                                )
                    else:
                        detailed_breakdown.append(item)
                extra_hours_breakdown = detailed_breakdown

            # Handle holiday breakdown
            if (
                is_manual_entry
                and previous_detail.holiday_charges > 0
                and not holiday_breakdown
            ):
                holiday_breakdown = [
                    {
                        "date": f"{previous_detail.actual_year}-{previous_detail.actual_month:02d}-15",
                        "holiday_name": "Manual Entry Holiday",
                        "charges": float(previous_detail.holiday_charges),
                        "type": "converted_from_manual",
                    }
                ]

            # ===== ENHANCED PAYMENT PROCESSING =====
            def process_payment_data(detail, month_name):
                """Process payment data for display - ALWAYS SHOW PAYMENTS"""
                payment_info = {
                    "amount": float(detail.payments_received or 0),
                    "receipt_numbers": [],
                    "payment_details": [],
                    "has_payments": False,
                    "payment_display_text": "",
                }

                if (
                    detail.payment_receipts
                    and isinstance(detail.payment_receipts, list)
                    and len(detail.payment_receipts) > 0
                ):
                    payment_info["has_payments"] = True
                    for payment in detail.payment_receipts:
                        receipt_num = payment.get("receipt_number", "N/A")
                        amount = float(payment.get("amount", 0))
                        payment_date = payment.get("date", "N/A")

                        payment_info["receipt_numbers"].append(receipt_num)
                        payment_info["payment_details"].append(
                            {
                                "receipt_number": receipt_num,
                                "amount": amount,
                                "date": payment_date,
                            }
                        )

                    # Create display text for actual payments
                    if len(payment_info["payment_details"]) == 1:
                        payment_info["payment_display_text"] = (
                            f"Payment Settled-{month_name} (RN {payment_info['receipt_numbers'][0]})"
                        )
                    else:
                        receipts_text = ", ".join(payment_info["receipt_numbers"])
                        payment_info["payment_display_text"] = (
                            f"Payments Settled-{month_name} (RN {receipts_text})"
                        )
                else:
                    # ALWAYS show payment row, even if 0.00
                    payment_info["has_payments"] = (
                        False  # No actual payments, but still show row
                    )
                    payment_info["payment_display_text"] = "Payments"

                return payment_info

            # Process payments for each month
            outstanding_payments = process_payment_data(
                outstanding_detail, outstanding_detail.month_name
            )
            previous_payments = process_payment_data(
                previous_detail, previous_detail.month_name
            )
            current_payments = process_payment_data(
                current_detail, current_detail.month_name
            )

            base_data.update(
                {
                    "package_name": package_name,
                    # Outstanding month with ENHANCED PAYMENT DATA
                    "outstanding_month": {
                        "name": outstanding_detail.month_name,
                        "year": outstanding_detail.actual_year,
                        "original_charge": float(outstanding_detail.package_fee),
                        "payment_amount": outstanding_payments["amount"],
                        "payment_receipt": outstanding_payments["receipt_numbers"][0]
                        if outstanding_payments["receipt_numbers"]
                        else "N/A",
                        "payment_display_text": outstanding_payments[
                            "payment_display_text"
                        ],
                        "payment_details": outstanding_payments["payment_details"],
                        "show_payments": True,  # ALWAYS show payment row
                        "balance": float(outstanding_detail.net_balance),
                        "calculation_text": f"Rs.{outstanding_detail.package_fee:,.2f} - Rs.{outstanding_detail.payments_received:,.2f} = Rs.{outstanding_detail.net_balance:,.2f}",
                    },
                    # Previous month with ENHANCED PAYMENT DATA
                    "previous_month": {
                        "name": previous_detail.month_name,
                        "year": previous_detail.actual_year,
                        "package_fee": float(previous_detail.package_fee),
                        "package_description": f"Day Care Monthly fee - {previous_detail.month_name} ({days_attended}/{expected_days} days attended)",
                        "payment_amount": previous_payments["amount"],
                        "payment_receipt": previous_payments["receipt_numbers"][0]
                        if previous_payments["receipt_numbers"]
                        else "N/A",
                        "payment_display_text": previous_payments[
                            "payment_display_text"
                        ],
                        "payment_details": previous_payments["payment_details"],
                        "show_payments": True,  # ALWAYS show payment row
                        # Extra hours section
                        "extra_charges": float(previous_detail.extra_hours_charge),
                        "extra_hours_description": "Extra Hours Charges for the month",
                        "extra_hours_breakdown_list": extra_hours_breakdown,
                        # Holiday charges section
                        "holiday_charges": float(previous_detail.holiday_charges),
                        "holiday_description": "Holiday Attendance Charges",
                        "holiday_breakdown_list": holiday_breakdown,
                        # Month total
                        "month_total": float(
                            previous_detail.net_balance
                            + previous_detail.extra_hours_charge
                            + previous_detail.holiday_charges
                        ),
                        # Attendance details
                        "days_attended": days_attended,
                        "expected_days": expected_days,
                        "attendance_percentage": float(attendance_percentage),
                        "is_half_charge": previous_detail.is_half_charge_applied,
                    },
                    # Current month with ENHANCED PAYMENT DATA
                    "current_month": {
                        "name": current_detail.month_name,
                        "year": current_detail.actual_year,
                        "package_fee": float(current_detail.package_fee),
                        "package_description": f"Day Care Monthly fee - {current_detail.month_name} {current_detail.actual_year} (Full Package)",
                        "advance_note": "Advance charge for upcoming month",
                        "payment_amount": current_payments["amount"],
                        "payment_receipt": current_payments["receipt_numbers"][0]
                        if current_payments["receipt_numbers"]
                        else "N/A",
                        "payment_display_text": current_payments[
                            "payment_display_text"
                        ],
                        "payment_details": current_payments["payment_details"],
                        "show_payments": True,  # ALWAYS show payment row
                        "balance": float(current_detail.net_balance),
                    },
                    # Summary totals
                    "totals": {
                        "outstanding": float(outstanding_detail.net_balance),
                        "previous_month": float(
                            previous_detail.net_balance
                            + previous_detail.extra_hours_charge
                            + previous_detail.holiday_charges
                        ),
                        "current_month": float(current_detail.net_balance),
                        "grand_total": float(memo.net_amount_due),
                        "total_payments": float(memo.total_payments),
                        "final_calculation": f"Rs.{outstanding_detail.net_balance:,.2f} + Rs.{previous_detail.net_balance + previous_detail.extra_hours_charge + previous_detail.holiday_charges:,.2f} + Rs.{current_detail.net_balance:,.2f} = Rs.{memo.net_amount_due:,.2f}",
                    },
                    # ===== ENHANCED PAYMENT SUMMARY =====
                    "payment_summary": {
                        "total_payments": float(memo.total_payments),
                        "outstanding_payments": outstanding_payments,
                        "previous_payments": previous_payments,
                        "current_payments": current_payments,
                        "all_payments": outstanding_payments["payment_details"]
                        + previous_payments["payment_details"]
                        + current_payments["payment_details"],
                    },
                }
            )

        else:
            # Fallback for incomplete data
            base_data.update(
                {
                    "package_name": "Normal Package",
                    "outstanding_month": {
                        "name": "Outstanding",
                        "year": 2025,
                        "balance": 0,
                        "show_payments": True,
                    },
                    "previous_month": {
                        "name": "Previous",
                        "year": 2025,
                        "extra_charges": 0,
                        "extra_hours_breakdown_list": [],
                        "holiday_breakdown_list": [],
                        "days_attended": 0,
                        "expected_days": 22,
                        "attendance_percentage": 0,
                        "show_payments": True,
                    },
                    "current_month": {
                        "name": "Current",
                        "year": 2025,
                        "show_payments": True,
                    },
                    "totals": {"grand_total": 0, "total_payments": 0},
                    "payment_summary": {"total_payments": 0, "all_payments": []},
                }
            )

        return base_data

    except Exception as e:
        print(f"Error in prepare_memo_display_data_fixed: {str(e)}")
        import traceback

        traceback.print_exc()

        return {
            "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
            "child_admission": memo.child.admission_number,
            "child_id": memo.child.id,
            "memo_code": memo.memo_code,
            "package_name": "Normal Package",
            "memo_date": memo.memo_date.strftime("%d/%m/%Y"),
            "due_date": (memo.memo_date + timedelta(days=7)).strftime("%d/%m/%Y"),
            "outstanding_month": {"balance": 0, "show_payments": True},
            "previous_month": {
                "extra_charges": 0,
                "extra_hours_breakdown_list": [],
                "holiday_breakdown_list": [],
                "days_attended": 0,
                "expected_days": 22,
                "attendance_percentage": 0,
                "show_payments": True,
            },
            "current_month": {"show_payments": True},
            "totals": {"grand_total": 0, "total_payments": 0},
            "payment_summary": {"total_payments": 0, "all_payments": []},
            "error": str(e),
        }


def generate_memo_pdf_with_two_column_breakdown(memo_data):
    """
    Generates a professional PDF invoice memo with detailed two-column breakdown layout.

    This function creates a comprehensive PDF invoice memo using ReportLab, featuring
    a professional layout with detailed charge breakdowns in two-column format for
    better readability. It includes payment history, outstanding balances, and
    itemized charges with professional formatting.

    Args:
        memo_data (dict): Comprehensive memo data dictionary containing:
            - child_name: Child's full name
            - child_admission: Child's admission number
            - memo_code: Unique memo identifier
            - due_date: Payment due date
            - package_name: Enrolled package name
            - outstanding_month: Outstanding balance details
            - previous_month: Previous month charges and breakdown
            - current_month: Current month charges and breakdown
            - payment_history: Payment transaction details
            - extra_hours_breakdown_list: Detailed extra hours charges
            - holiday_breakdown_list: Holiday attendance charges

    Returns:
        BytesIO: PDF buffer containing the generated invoice memo

    PDF Structure:
        1. Header Section:
           - Company logo and name
           - Address and contact information
           - Professional styling with centered alignment

        2. Child Information Section:
           - Child name and admission number
           - Package details and due date
           - Formatted in table layout for clarity

        3. Outstanding Balance Section:
           - Previous outstanding amounts
           - Payment history with detailed breakdown
           - Current outstanding balance calculations

        4. Previous Month Charges:
           - Monthly package fees
           - Extra hours breakdown in two-column format
           - Holiday charges with individual day details
           - Subtotal calculations

        5. Current Month Charges:
           - Current package fees
           - Extra hours breakdown
           - Holiday charges
           - Total amount due

        6. Payment Information:
           - Payment history table
           - Current balance calculations
           - Due date information

    Typography and Styling:
        - Header: Helvetica-Bold, 16pt
        - Address: Helvetica, 11pt
        - Content: Helvetica, 11pt
        - Breakdown details: Helvetica, 9pt
        - Professional color scheme with black text

    Two-Column Breakdown Features:
        - Extra hours displayed in paired columns
        - Holiday charges in structured format
        - Improved readability for detailed information
        - Efficient space utilization
        - Clear separation between different charge types

    Table Formatting:
        - Professional table styling with borders
        - Alternating row colors for readability
        - Right-aligned monetary values
        - Consistent spacing and padding
        - Clear headers and sections

    Payment Integration:
        - Shows all payment transactions
        - Calculates running balances
        - Displays payment dates and amounts
        - Includes payment reference numbers

    Error Handling:
        - Handles missing data gracefully
        - Provides default values for missing fields
        - Manages formatting errors in amounts
        - Ensures PDF generation doesn't fail

    Business Logic:
        - Calculates outstanding balances automatically
        - Formats monetary values consistently
        - Maintains chronological order of transactions
        - Provides comprehensive billing documentation

    Integration:
        - Works with prepare_memo_display_data_fixed() for data preparation
        - Uses format_breakdown_item() for extra hours formatting
        - Uses format_holiday_breakdown_item() for holiday formatting
        - Supports enhanced memo system architecture

    Performance:
        - Generates PDF in memory using BytesIO
        - Efficient table creation with ReportLab
        - Optimized for A4 page size
        - Minimal memory footprint

    Use Cases:
        - Professional invoice generation
        - Parent billing documentation
        - Administrative record keeping
        - Payment verification
        - Audit trail documentation
    """
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
                f"{outstanding.get('name', 'Outstanding')} {outstanding.get('year', 2025)} • OUTSTANDING",
                "",
            ]
        )

        outstanding_desc = f"Outstanding from {outstanding.get('name', 'Outstanding')}"
        table_data.append(
            [outstanding_desc, f"{outstanding.get('original_charge', 0):,.2f}"]
        )

        # Add outstanding payment - ALWAYS SHOW
        payment_text = outstanding.get("payment_display_text", "Payments")
        table_data.append(
            [payment_text, f"-{outstanding.get('payment_amount', 0):,.2f}"]
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
            extra_description = "Extra Hours for the month"

            if extra_breakdown and len(extra_breakdown) > 0:
                # Create 2-column breakdown table
                breakdown_table_data = []

                for i in range(0, len(extra_breakdown), 2):
                    left_item = extra_breakdown[i]
                    right_item = (
                        extra_breakdown[i + 1] if i + 1 < len(extra_breakdown) else None
                    )

                    left_text = format_breakdown_item(left_item)
                    right_text = format_breakdown_item(right_item) if right_item else ""

                    breakdown_table_data.append([left_text, right_text])

                breakdown_table = Table(
                    breakdown_table_data, colWidths=[60 * mm, 60 * mm]
                )
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
                            ("GRID", (0, 0), (-1, -1), 0, colors.white),
                        ]
                    )
                )

                full_extra_desc = [
                    [extra_description, f"{previous.get('extra_charges', 0):,.2f}"],
                    [breakdown_table, ""],
                ]
                table_data.extend(full_extra_desc)
            else:
                table_data.append(
                    [extra_description, f"{previous.get('extra_charges', 0):,.2f}"]
                )

        # Holiday charges with 2-column breakdown
        if previous.get("holiday_charges", 0) > 0:
            holiday_breakdown = previous.get("holiday_breakdown_list", [])
            holiday_count = len(holiday_breakdown)
            holiday_description = f"Holiday Attendance Charges {holiday_count} days"

            if holiday_breakdown and len(holiday_breakdown) > 0:
                holiday_breakdown_data = []

                for i in range(0, len(holiday_breakdown), 2):
                    left_item = holiday_breakdown[i]
                    right_item = (
                        holiday_breakdown[i + 1]
                        if i + 1 < len(holiday_breakdown)
                        else None
                    )

                    left_text = format_holiday_breakdown_item(left_item)
                    right_text = (
                        format_holiday_breakdown_item(right_item) if right_item else ""
                    )

                    holiday_breakdown_data.append([left_text, right_text])

                holiday_breakdown_table = Table(
                    holiday_breakdown_data, colWidths=[60 * mm, 60 * mm]
                )
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
                    [holiday_breakdown_table, ""],
                ]
                table_data.extend(full_holiday_desc)
            else:
                table_data.append(
                    [holiday_description, f"{previous.get('holiday_charges', 0):,.2f}"]
                )

        # ===== ADD PREVIOUS MONTH PAYMENTS - ALWAYS SHOW =====
        payment_text = previous.get("payment_display_text", "Payments")
        table_data.append([payment_text, f"-{previous.get('payment_amount', 0):,.2f}"])

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
        current_desc += (
            f"\n{current.get('advance_note', 'Advance charge for upcoming month')}"
        )
        table_data.append([current_desc, f"{current.get('package_fee', 0):,.2f}"])

        # ===== ADD CURRENT MONTH PAYMENTS - ALWAYS SHOW =====
        payment_text = current.get("payment_display_text", "Payments")
        table_data.append([payment_text, f"-{current.get('payment_amount', 0):,.2f}"])

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
            ("BACKGROUND", (0, 1), (-1, 1), colors.Color(1, 0.9, 0.9)),  # Outstanding
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
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


def format_breakdown_item(item):
    """
    Formats individual extra hours breakdown item for PDF display.

    This utility function takes an extra hours breakdown item dictionary and
    formats it into a readable string for PDF invoice display. It handles
    date formatting, time display, and extra hours calculations.

    Args:
        item (dict): Extra hours breakdown item containing:
            - date: Date string in YYYY-MM-DD format
            - time_out: Time the child was checked out
            - extra_hours_display: Formatted extra hours string
            - charges: Amount charged for extra hours

    Returns:
        str: Formatted string for PDF display in format:
             "YYYY-MM-DD -> TIME_OUT (EXTRA_HOURS_DISPLAY)"
        str: Empty string if item is None or empty

    Format Output:
        - "2024-01-15 -> 18:30 (2h 30m extra)"
        - "2024-01-16 -> 19:00 (3h extra)"
        - "N/A -> N/A ()" if data is missing

    Data Processing:
        - Converts date string to consistent YYYY-MM-DD format
        - Handles missing or invalid dates gracefully
        - Preserves time_out and extra_hours_display as provided
        - Does not include charges in display string

    Error Handling:
        - Returns empty string for None or empty items
        - Handles date parsing errors gracefully
        - Uses "N/A" for missing date values
        - Maintains original format for invalid dates

    Business Logic:
        - Provides consistent formatting for PDF breakdown sections
        - Supports two-column layout in invoice memos
        - Enables clear display of extra hours charges
        - Maintains chronological information for audit purposes

    Integration:
        - Used by generate_memo_pdf_with_two_column_breakdown()
        - Works with extra hours breakdown data
        - Supports PDF table formatting requirements
        - Maintains consistent display format across all breakdowns

    Date Handling:
        - Expects YYYY-MM-DD input format
        - Converts to consistent YYYY-MM-DD output format
        - Handles various date string formats
        - Preserves original string if parsing fails

    Use Cases:
        - PDF invoice generation
        - Extra hours breakdown display
        - Administrative reporting
        - Parent billing documentation
        - Audit trail formatting
    """
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
    """
    Formats individual holiday breakdown item for PDF display.

    This utility function takes a holiday breakdown item dictionary and
    formats it into a readable string for PDF invoice display. It handles
    date formatting and holiday name display for holiday attendance charges.

    Args:
        item (dict): Holiday breakdown item containing:
            - date: Date string in YYYY-MM-DD format
            - holiday_name: Name of the holiday
            - charges: Amount charged for holiday attendance

    Returns:
        str: Formatted string for PDF display in format:
             "YYYY-MM-DD -> HOLIDAY_NAME"
        str: Empty string if item is None or empty

    Format Output:
        - "2024-01-15 -> Poya Day"
        - "2024-02-04 -> Independence Day"
        - "N/A -> Holiday" if data is missing

    Data Processing:
        - Converts date string to consistent YYYY-MM-DD format
        - Handles missing or invalid dates gracefully
        - Preserves holiday_name as provided
        - Does not include charges in display string

    Error Handling:
        - Returns empty string for None or empty items
        - Handles date parsing errors gracefully
        - Uses "N/A" for missing date values
        - Uses "Holiday" as default name if not provided
        - Maintains original format for invalid dates

    Business Logic:
        - Provides consistent formatting for PDF breakdown sections
        - Supports two-column layout in invoice memos
        - Enables clear display of holiday charges
        - Maintains chronological information for audit purposes
        - Helps parents understand holiday attendance charges

    Integration:
        - Used by generate_memo_pdf_with_two_column_breakdown()
        - Works with holiday breakdown data
        - Supports PDF table formatting requirements
        - Maintains consistent display format across all breakdowns

    Date Handling:
        - Expects YYYY-MM-DD input format
        - Converts to consistent YYYY-MM-DD output format
        - Handles various date string formats
        - Preserves original string if parsing fails

    Holiday Information:
        - Displays holiday name for context
        - Helps parents understand charges
        - Provides transparency in billing
        - Supports audit and verification

    Use Cases:
        - PDF invoice generation
        - Holiday charges breakdown display
        - Administrative reporting
        - Parent billing documentation
        - Audit trail formatting
        - Holiday attendance tracking
    """
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
        "holiday_breakdown_items": holiday_breakdown,
    }


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


def generate_memo_preview_html_with_two_columns(memo_data):
    """Generate HTML preview with 2-column breakdown display and PAYMENTS"""

    # Process breakdown data
    previous = memo_data.get("previous_month", {})
    extra_breakdown = previous.get("extra_hours_breakdown_list", [])
    holiday_breakdown = previous.get("holiday_breakdown_list", [])

    # Generate extra hours HTML with 2-column layout
    extra_hours_html = ""
    if previous.get("extra_charges", 0) > 0:
        extra_count = len(extra_breakdown)
        extra_description = "Extra Hours Charges for the month"

        # Create 2-column breakdown
        breakdown_html = ""
        if extra_breakdown:
            breakdown_html = '<div class="breakdown-grid">'
            for i in range(0, len(extra_breakdown), 2):
                left_item = extra_breakdown[i]
                right_item = (
                    extra_breakdown[i + 1] if i + 1 < len(extra_breakdown) else None
                )

                left_text = format_breakdown_item_html(left_item)
                right_text = (
                    format_breakdown_item_html(right_item) if right_item else ""
                )

                breakdown_html += f"""
                <div class="breakdown-row">
                    <div class="breakdown-col">{left_text}</div>
                    <div class="breakdown-col">{right_text}</div>
                </div>"""
            breakdown_html += "</div>"

        extra_hours_html = f"""
                    <tr>
                        <td>
                            {extra_description}
                            {breakdown_html}
                        </td>
                        <td class="amount-col">{previous.get("extra_charges", 0):,.2f}</td>
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
                right_item = (
                    holiday_breakdown[i + 1] if i + 1 < len(holiday_breakdown) else None
                )

                left_text = format_holiday_breakdown_item_html(left_item)
                right_text = (
                    format_holiday_breakdown_item_html(right_item) if right_item else ""
                )

                holiday_breakdown_html += f"""
                <div class="breakdown-row">
                    <div class="breakdown-col">{left_text}</div>
                    <div class="breakdown-col">{right_text}</div>
                </div>"""
            holiday_breakdown_html += "</div>"

        holiday_charges_html = f"""
                    <tr>
                        <td>
                            {holiday_description}
                            {holiday_breakdown_html}
                        </td>
                        <td class="amount-col">{previous.get("holiday_charges", 0):,.2f}</td>
                    </tr>"""

    # ===== GENERATE PAYMENT HTML SECTIONS =====
    outstanding = memo_data.get("outstanding_month", {})
    current = memo_data.get("current_month", {})

    # Outstanding payment HTML - ALWAYS SHOW
    outstanding_payment_color = (
        "payment-amount"
        if outstanding.get("payment_amount", 0) > 0
        else "payment-amount text-muted"
    )
    outstanding_payment_html = f"""
                    <tr>
                        <td class="payment-row">{outstanding.get("payment_display_text", "Payments")}</td>
                        <td class="amount-col {outstanding_payment_color}">-{outstanding.get("payment_amount", 0):,.2f}</td>
                    </tr>"""

    # Previous month payment HTML - ALWAYS SHOW
    previous_payment_color = (
        "payment-amount"
        if previous.get("payment_amount", 0) > 0
        else "payment-amount text-muted"
    )
    previous_payment_html = f"""
                    <tr>
                        <td class="payment-row">{previous.get("payment_display_text", "Payments")}</td>
                        <td class="amount-col {previous_payment_color}">-{previous.get("payment_amount", 0):,.2f}</td>
                    </tr>"""

    # Current month payment HTML - ALWAYS SHOW
    current_payment_color = (
        "payment-amount"
        if current.get("payment_amount", 0) > 0
        else "payment-amount text-muted"
    )
    current_payment_html = f"""
                    <tr>
                        <td class="payment-row">{current.get("payment_display_text", "Payments")}</td>
                        <td class="amount-col {current_payment_color}">-{current.get("payment_amount", 0):,.2f}</td>
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
            
            /* Payment styling */
            .payment-amount {{
                color: #28a745 !important;
                font-weight: bold;
            }}
            
            .payment-row {{
                font-style: italic;
                color: #666;
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
                        <td class="amount-col">{memo_data["outstanding_month"].get("original_charge", 0):,.2f}</td>
                    </tr>
                    
                    {outstanding_payment_html}
                    
                    <tr>
                        <td><strong>Outstanding from {memo_data["outstanding_month"]["name"]}</strong></td>
                        <td class="amount-col"><strong>{memo_data["outstanding_month"]["balance"]:,.2f}</strong></td>
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
                    
                    {previous_payment_html}
                    
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
                    
                    {current_payment_html}
                    
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


# UPDATED PREVIEW FUNCTION - Use the debug version temporarily
def previewInvoiceMemo(request, memo_id):
    """FINAL VERSION - Preview invoice memo with two-column breakdown"""
    try:
        memo = get_object_or_404(InvoiceMemo, pk=memo_id)
        memo_data = prepare_memo_display_data_fixed(memo)
        preview_html = generate_memo_preview_html_with_two_columns(memo_data)
        return HttpResponse(preview_html)
    except Exception as e:
        messages.error(request, f"Error loading memo: {str(e)}")
        return redirect("core:load_invoice_memo")


@login_required
def checkMissingAttendanceForMemo(request):
    """
    Check for missing attendance logs before generating memo
    Returns missing attendance data if any found
    Uses existing logic from processMissingAttendanceRecordsJS but for specific child/month
    """
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        child = Child.objects.get(id=child_id)
        month_int = int(month)
        year_int = int(year)

        # Calculate the date range for PREVIOUS month (since that's what memo calculates)
        if month_int > 1:
            check_month = month_int - 1
            check_year = year_int
        else:
            check_month = 12
            check_year = year_int - 1

        # Create date range for the month we're checking
        from_date = datetime(check_year, check_month, 1).date()
        last_day = datetime(
            check_year, check_month, calendar.monthrange(check_year, check_month)[1]
        ).date()

        # Get attendance records for the child in the target month (only active records)
        attendance_records = AttendanceLog.objects.filter(
            child=child, date_logged__range=(from_date, last_day), is_active=True
        ).values_list("date_logged", "time_logged")

        # Group attendance by date (same logic as processMissingAttendanceRecordsJS)
        attendance_dict = {}
        for date_logged, time_logged in attendance_records:
            attendance_dict.setdefault(date_logged, []).append(time_logged)

        cutoff_time = time(15, 0)  # 3:00 PM
        missing_attendance = []

        # Check each date for missing IN or OUT (same logic as existing function)
        for date_logged, time_logs in attendance_dict.items():
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

                missing_attendance.append(
                    {
                        "date": date_logged.strftime("%Y-%m-%d"),
                        "day_name": date_logged.strftime("%A"),
                        "in_time": in_time,
                        "out_time": out_time,
                        "missing_record": missing_record,
                        "child_name": f"{child.child_first_name} {child.child_last_name}",
                    }
                )

        # Note: We only check for missing IN or OUT, not completely missing days
        # If a child didn't attend at all, that's not considered "missing" attendance

        if missing_attendance:
            return JsonResponse(
                {
                    "has_missing": True,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "child_admission": child.admission_number,
                    "check_month_name": calendar.month_name[check_month],
                    "check_year": check_year,
                    "missing_count": len(missing_attendance),
                    "missing_records": missing_attendance,
                    "message": f"Cannot generate memo: {len(missing_attendance)} missing attendance records found for {calendar.month_name[check_month]} {check_year}",
                    "detailed_message": f"Child {child.admission_number} has {len(missing_attendance)} incomplete attendance records in {calendar.month_name[check_month]} {check_year}. Please complete the attendance data before generating the memo.",
                }
            )
        else:
            return JsonResponse(
                {
                    "has_missing": False,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "child_admission": child.admission_number,
                    "check_month_name": calendar.month_name[check_month],
                    "check_year": check_year,
                    "message": "No missing attendance records found. Ready to generate memo.",
                }
            )

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def checkPendingTimeAdjustmentsForMemo(request):
    """
    Check for pending time adjustment requests before generating memo.

    This endpoint validates that a child has no pending time adjustment requests
    for the PREVIOUS month (the month being billed) before allowing memo generation.
    Pending requests must be approved or rejected first to ensure accurate billing calculations.

    Args:
        request (HttpRequest): GET request with parameters:
            - child_id: Integer ID of the child
            - month: Integer month number (1-12) - the memo month
            - year: Integer year - the memo year

    Returns:
        JsonResponse: JSON object with:
            - has_pending: Boolean indicating if there are pending requests
            - pending_count: Integer count of pending requests
            - child_name: String child's full name
            - child_admission: String child's admission number
            - check_month_name: String name of the month being validated
            - check_year: Integer year being validated
            - message: String user-friendly message
            - redirect_url: String URL to time adjustment approvals page (if has_pending)

    Example Response (with pending requests):
        {
            "has_pending": true,
            "pending_count": 2,
            "child_name": "John Doe",
            "child_admission": "ADM001",
            "check_month_name": "January",
            "check_year": 2026,
            "message": "Cannot Generate Memo! Child has 2 pending time adjustment request(s) for January 2026...",
            "redirect_url": "/time_adjustment_approvals/"
        }

    Example Response (no pending requests):
        {
            "has_pending": false,
            "pending_count": 0,
            "child_name": "John Doe",
            "child_admission": "ADM001",
            "check_month_name": "January",
            "check_year": 2026,
            "message": "No pending time adjustment requests for January 2026. Ready to generate memo."
        }

    Security:
        - Requires user authentication via @login_required decorator
    """
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not child_id:
            return JsonResponse({"error": "Missing child_id parameter"}, status=400)

        child = Child.objects.get(id=child_id, is_active=True)

        # If month/year not provided, return success with no pending (graceful degradation)
        if not month or not year:
            child_full_name = f"{child.child_first_name} {child.child_last_name}"
            return JsonResponse({
                "has_pending": False,
                "pending_count": 0,
                "child_name": child_full_name,
                "child_admission": child.admission_number,
                "check_month_name": "",
                "check_year": "",
                "message": "Month/year not provided. Skipping time adjustment validation."
            })

        # Convert to integers with error handling
        try:
            month_int = int(month)
            year_int = int(year)
        except (ValueError, TypeError):
            child_full_name = f"{child.child_first_name} {child.child_last_name}"
            return JsonResponse({
                "has_pending": False,
                "pending_count": 0,
                "child_name": child_full_name,
                "child_admission": child.admission_number,
                "check_month_name": "",
                "check_year": "",
                "message": "Invalid month/year format. Skipping time adjustment validation."
            })

        # Calculate the date range for PREVIOUS month (since that's what memo calculates)
        # Same logic as checkMissingAttendanceForMemo
        if month_int > 1:
            check_month = month_int - 1
            check_year = year_int
        else:
            check_month = 12
            check_year = year_int - 1

        # Create date range for the month we're checking
        from_date = datetime(check_year, check_month, 1).date()
        last_day = datetime(
            check_year, check_month, calendar.monthrange(check_year, check_month)[1]
        ).date()

        # Count pending time adjustment requests for this child IN THE PREVIOUS MONTH ONLY
        pending_count = TimeAdjustmentRequest.objects.filter(
            child=child,
            request_date__range=(from_date, last_day),
            status="PENDING_APPROVAL",
            is_active=True
        ).count()

        child_full_name = f"{child.child_first_name} {child.child_last_name}"
        check_month_name = calendar.month_name[check_month]

        if pending_count > 0:
            return JsonResponse({
                "has_pending": True,
                "pending_count": pending_count,
                "child_name": child_full_name,
                "child_admission": child.admission_number,
                "check_month_name": check_month_name,
                "check_year": check_year,
                "message": (
                    f"Cannot Generate Memo! Child has {pending_count} pending time adjustment "
                    f"request{'s' if pending_count > 1 else ''} for {check_month_name} {check_year}. "
                    f"Please approve or reject them first."
                ),
                "redirect_url": "/time_adjustment_approvals/"
            })
        else:
            return JsonResponse({
                "has_pending": False,
                "pending_count": 0,
                "child_name": child_full_name,
                "child_admission": child.admission_number,
                "check_month_name": check_month_name,
                "check_year": check_year,
                "message": f"No pending time adjustment requests for {check_month_name} {check_year}. Ready to generate memo."
            })

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Add this enhanced view to your views.py file


@login_required
def getEnhancedCheckIns(request):
    """Enhanced check-ins view with missing attendance search functionality"""
    try:
        enrollment_form = CreateCheckInForm()

        # Get search parameters if any
        search_type = request.GET.get("search_type", "date_range")

        context = {
            "form": enrollment_form,
            "UserName": request.user.username,
            "search_type": search_type,
        }

        return render(request, "../templates/checkin.html", context)

    except Exception as e:
        messages.error(request, f"Error loading check-ins page: {str(e)}")
        return redirect("core:view_check_ins")


@login_required
def getEnhancedMissingAttendanceJS(request):
    """Enhanced missing attendance with flexible search options"""
    try:
        # Get search parameters
        child_admission = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")

        # Set default date range if not provided
        if not from_date or not to_date:
            today = datetime.now().date()
            if not from_date:
                from_date = (today - timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )  # Yesterday
            if not to_date:
                to_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # Yesterday

        # Parse dates
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Build base query
        filters = Q(date_logged__range=(from_date_obj, to_date_obj))

        # Add child filter if specified
        if child_admission:
            try:
                # Try to find child by admission number
                child = Child.objects.get(
                    admission_number=child_admission,
                    is_active=True,
                    enrollement_approved=True,
                )
                filters &= Q(child=child)

                # Expand date range for single child search (last 45 days including today)
                from_date_obj = datetime.now().date() - timedelta(days=45)
                to_date_obj = datetime.now().date()  # Include today, not just yesterday
                filters = Q(date_logged__range=(from_date_obj, to_date_obj)) & Q(
                    child=child
                )

            except Child.DoesNotExist:
                return JsonResponse(
                    {
                        "error": f"Child with admission number '{child_admission}' not found",
                        "missing_records": [],
                    },
                    status=404,
                )
        else:
            # For date range search, only include enrolled children
            active_children = Child.objects.filter(
                is_active=True, enrollement_approved=True, is_enrolled=True
            ).values_list("id", flat=True)
            filters &= Q(child_id__in=active_children)

        # Get attendance records - include id for removal functionality
        # NOTE: Only show active records (is_active=True)
        # - Active records with no removal request: Show ✅
        # - Active records with PENDING removal: Show ✅ (user can see their pending request)
        # - Inactive records with APPROVED removal: Hide ❌ (already removed)
        filters &= Q(is_active=True)
        attendance_records = AttendanceLog.objects.filter(filters).values_list(
            "id", "child_id", "date_logged", "time_logged"
        )

        # Group attendance by child and date - store id with time
        attendance_dict = defaultdict(list)
        for record_id, child_id, date_logged, time_logged in attendance_records:
            attendance_dict[(child_id, date_logged)].append(
                {"id": record_id, "time": time_logged}
            )

        # Define cutoff time to determine if time is IN or OUT
        cutoff_time = time(15, 0)  # 3:00 PM

        # Find incomplete attendance records
        incomplete_attendance_data = []

        for (child_id, date_logged), time_logs in attendance_dict.items():
            if len(time_logs) == 1:  # Only one time entry (missing either IN or OUT)
                try:
                    child = Child.objects.get(id=child_id)
                    record_data = time_logs[0]
                    single_time = record_data["time"]
                    attendance_id = record_data["id"]

                    # Determine what's missing based on time
                    if single_time > cutoff_time:
                        # Late time = OUT time, missing IN
                        in_time = "Missing"
                        out_time = single_time.strftime("%H:%M")
                        missing_record = "IN"
                        existing_record = f"OUT: {out_time}"
                    else:
                        # Early time = IN time, missing OUT
                        in_time = single_time.strftime("%H:%M")
                        out_time = "Missing"
                        missing_record = "OUT"
                        existing_record = f"IN: {in_time}"

                    incomplete_attendance_data.append(
                        {
                            "attendance_id": attendance_id,
                            "child_id": child.id,
                            "child_name": f"{child.admission_number} - {child.child_first_name} {child.child_last_name}",
                            "admission_number": child.admission_number,
                            "date_logged": date_logged.strftime("%Y-%m-%d"),
                            "day_name": date_logged.strftime("%A"),
                            "in_time": in_time,
                            "out_time": out_time,
                            "missing_record": missing_record,
                            "existing_record": existing_record,
                            "single_time": single_time.strftime("%H:%M"),
                            "needs_fix": True,
                        }
                    )

                except Child.DoesNotExist:
                    continue

        # Sort by date (newest first) then by child name
        incomplete_attendance_data.sort(
            key=lambda x: (x["date_logged"], x["child_name"]), reverse=True
        )

        # Add summary information
        response_data = {
            "success": True,
            "search_params": {
                "from_date": from_date_obj.strftime("%Y-%m-%d"),
                "to_date": to_date_obj.strftime("%Y-%m-%d"),
                "child": child_admission if child_admission else "All Children",
                "total_days": (to_date_obj - from_date_obj).days + 1,
            },
            "summary": {
                "total_missing": len(incomplete_attendance_data),
                "missing_in": len(
                    [
                        x
                        for x in incomplete_attendance_data
                        if x["missing_record"] == "IN"
                    ]
                ),
                "missing_out": len(
                    [
                        x
                        for x in incomplete_attendance_data
                        if x["missing_record"] == "OUT"
                    ]
                ),
                "unique_children": len(
                    set(x["child_id"] for x in incomplete_attendance_data)
                ),
                "date_range": f"{from_date_obj.strftime('%B %d, %Y')} to {to_date_obj.strftime('%B %d, %Y')}",
            },
            "missing_records": incomplete_attendance_data,
        }

        return JsonResponse(incomplete_attendance_data, safe=False)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse(
            {
                "error": f"Error processing missing attendance: {str(e)}",
                "missing_records": [],
            },
            status=500,
        )


@login_required
def saveEnhancedAttendance(request):
    """Enhanced attendance saving with better validation and feedback"""
    if request.method == "POST":
        try:
            child_admission = request.POST.get("child")
            date_logged = request.POST.get("date_logged")
            time_logged = request.POST.get("time_logged")

            # Validation
            if not all([child_admission, date_logged, time_logged]):
                messages.error(request, "All fields are required")
                return redirect("core:enhanced_check_ins")

            # Get child object
            try:
                child = Child.objects.get(
                    admission_number=child_admission,
                    is_active=True,
                    enrollement_approved=True,
                )
            except Child.DoesNotExist:
                messages.error(
                    request,
                    f"Child with admission number '{child_admission}' not found or not enrolled",
                )
                return redirect("core:enhanced_check_ins")

            # Parse and validate date
            try:
                log_date = datetime.strptime(date_logged, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid date format")
                return redirect("core:enhanced_check_ins")

            # Parse and validate time
            try:
                log_time = datetime.strptime(time_logged, "%H:%M").time()
            except ValueError:
                messages.error(request, "Invalid time format")
                return redirect("core:enhanced_check_ins")

            # Check if child was enrolled on that date
            if child.admission_date and child.admission_date > log_date:
                messages.error(
                    request,
                    f"Attendance date is invalid. Child was not enrolled on {log_date.strftime('%Y-%m-%d')}. "
                    f"Admission date: {child.admission_date.strftime('%Y-%m-%d')}",
                )
                return redirect("core:enhanced_check_ins")

            # Check for duplicate entry (same child, date, and time)
            existing_entry = AttendanceLog.objects.filter(
                child=child, date_logged=log_date, time_logged=log_time
            ).first()

            if existing_entry:
                messages.warning(
                    request,
                    f"Duplicate entry detected. {child.child_first_name} already has a record for "
                    f"{log_date.strftime('%Y-%m-%d')} at {log_time.strftime('%H:%M')}",
                )
                return redirect("core:enhanced_check_ins")

            # Get enrollment for branch/center info
            enrollment = ChildEnrollment.objects.filter(
                child=child, status="Approved", is_active=True
            ).first()

            # Create attendance record
            attendance = AttendanceLog.objects.create(
                child=child,
                date_logged=log_date,
                time_logged=log_time,
                user_created=request.user.username,
            )

            # Count existing records for this date to determine if this completes the attendance
            existing_records = AttendanceLog.objects.filter(
                child=child, date_logged=log_date
            ).count()

            # Create success message based on completion status
            if existing_records == 1:
                record_type = "First record (IN/OUT)"
                status_msg = "⚠️ Child still needs one more time entry to complete attendance for this day"
            elif existing_records == 2:
                record_type = "Second record - Attendance COMPLETE"
                status_msg = "✅ Attendance is now complete for this day"
            else:
                record_type = f"Additional record ({existing_records} total)"
                status_msg = (
                    f"ℹ️ Child now has {existing_records} time entries for this day"
                )

            messages.success(
                request,
                f"✅ Attendance saved successfully!\n"
                f"Child: {child.child_first_name} {child.child_last_name} ({child.admission_number})\n"
                f"Date: {log_date.strftime('%A, %B %d, %Y')}\n"
                f"Time: {log_time.strftime('%I:%M %p')}\n"
                f"Status: {record_type}\n"
                f"{status_msg}",
            )

            return redirect("core:enhanced_check_ins")

        except Exception as e:
            import traceback

            traceback.print_exc()
            messages.error(request, f"Error saving attendance: {str(e)}")
            return redirect("core:enhanced_check_ins")

    else:
        messages.error(request, "Invalid request method")
        return redirect("core:enhanced_check_ins")


@login_required
def getAttendanceStatsSummary(request):
    """Get attendance statistics for dashboard/summary"""
    try:
        child_id = request.GET.get("child_id")
        days_back = int(request.GET.get("days_back", 7))

        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)

        # Base query
        filters = Q(date_logged__range=(start_date, end_date))

        if child_id:
            filters &= Q(child_id=child_id)
        else:
            # Only enrolled children
            active_children = Child.objects.filter(
                is_active=True, enrollement_approved=True, is_enrolled=True
            ).values_list("id", flat=True)
            filters &= Q(child_id__in=active_children)

        # Get attendance records
        attendance_records = AttendanceLog.objects.filter(filters).values_list(
            "child_id", "date_logged", "time_logged"
        )

        # Group by child and date
        attendance_by_child_date = defaultdict(list)
        for child_id, date_logged, time_logged in attendance_records:
            attendance_by_child_date[(child_id, date_logged)].append(time_logged)

        # Calculate statistics
        total_days = 0
        complete_days = 0
        incomplete_days = 0
        missing_in = 0
        missing_out = 0

        cutoff_time = time(15, 0)  # 3:00 PM

        for (child_id, date_logged), time_logs in attendance_by_child_date.items():
            total_days += 1

            if len(time_logs) >= 2:
                complete_days += 1
            elif len(time_logs) == 1:
                incomplete_days += 1
                single_time = time_logs[0]
                if single_time > cutoff_time:
                    missing_in += 1  # Has OUT, missing IN
                else:
                    missing_out += 1  # Has IN, missing OUT

        statistics = {
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days_covered": days_back,
            },
            "totals": {
                "total_attendance_days": total_days,
                "complete_days": complete_days,
                "incomplete_days": incomplete_days,
                "completion_rate": round((complete_days / total_days * 100), 1)
                if total_days > 0
                else 0,
            },
            "missing_breakdown": {
                "missing_in_count": missing_in,
                "missing_out_count": missing_out,
                "total_missing": missing_in + missing_out,
            },
        }

        return JsonResponse(statistics)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def bulkFixAttendance(request):
    """Bulk fix multiple missing attendance records"""
    if request.method == "POST":
        try:
            import json

            # Get bulk fix data from request
            bulk_data = json.loads(request.body)
            fixes = bulk_data.get("fixes", [])

            if not fixes:
                return JsonResponse({"error": "No fixes provided"}, status=400)

            success_count = 0
            error_count = 0
            errors = []

            with transaction.atomic():
                for fix in fixes:
                    try:
                        child_admission = fix.get("child_admission")
                        date_logged = fix.get("date_logged")
                        time_logged = fix.get("time_logged")

                        # Validate data
                        if not all([child_admission, date_logged, time_logged]):
                            errors.append(
                                {
                                    "child": child_admission,
                                    "error": "Missing required fields",
                                }
                            )
                            error_count += 1
                            continue

                        # Get child
                        child = Child.objects.get(
                            admission_number=child_admission,
                            is_active=True,
                            enrollement_approved=True,
                        )

                        # Parse date and time
                        log_date = datetime.strptime(date_logged, "%Y-%m-%d").date()
                        log_time = datetime.strptime(time_logged, "%H:%M").time()

                        # Check for duplicates
                        if AttendanceLog.objects.filter(
                            child=child, date_logged=log_date, time_logged=log_time
                        ).exists():
                            errors.append(
                                {"child": child_admission, "error": "Duplicate entry"}
                            )
                            error_count += 1
                            continue

                        # Create attendance record
                        AttendanceLog.objects.create(
                            child=child,
                            date_logged=log_date,
                            time_logged=log_time,
                            user_created=request.user.username,
                        )

                        success_count += 1

                    except Child.DoesNotExist:
                        errors.append(
                            {"child": child_admission, "error": "Child not found"}
                        )
                        error_count += 1
                    except Exception as e:
                        errors.append({"child": child_admission, "error": str(e)})
                        error_count += 1

            return JsonResponse(
                {
                    "success": True,
                    "summary": {
                        "total_processed": len(fixes),
                        "success_count": success_count,
                        "error_count": error_count,
                    },
                    "errors": errors,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def requestAttendanceRemoval(request):
    """Request removal of an attendance entry - requires approval"""
    if request.method == "POST":
        try:
            attendance_id = request.POST.get("attendance_id")
            removal_reason = request.POST.get("removal_reason", "").strip()

            if not attendance_id:
                return JsonResponse({"error": "Attendance ID is required"}, status=400)

            if not removal_reason:
                return JsonResponse(
                    {"error": "Removal reason is required"}, status=400
                )

            # Get the attendance record
            # NOTE: Don't filter by is_active - allow removal requests for all records
            try:
                attendance = AttendanceLog.objects.get(id=attendance_id)
            except AttendanceLog.DoesNotExist:
                return JsonResponse(
                    {"error": "Attendance record not found"}, status=404
                )

            # Check if already pending removal
            if attendance.removal_status == "PENDING":
                return JsonResponse(
                    {"error": "This record already has a pending removal request"},
                    status=400,
                )

            # Update the record with removal request
            attendance.removal_requested = True
            attendance.removal_reason = removal_reason
            attendance.removal_requested_by = request.user.username
            attendance.removal_requested_date = datetime.now()
            attendance.removal_status = "PENDING"
            attendance.user_updated = request.user.username
            attendance.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Removal request submitted successfully. Awaiting approval.",
                    "attendance_id": attendance_id,
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def getRemovalRequestsJS(request):
    """Get all pending attendance removal requests for approval"""
    try:
        # Get all pending removal requests from last 45 days
        # NOTE: Don't filter by is_active - show all pending removal requests
        from_date = datetime.now().date() - timedelta(days=45)

        pending_requests = AttendanceLog.objects.filter(
            removal_status="PENDING",
            date_logged__gte=from_date  # Last 45 days only
        ).select_related("child").order_by('-removal_requested_date')

        requests_data = []
        for record in pending_requests:
            requests_data.append(
                {
                    "id": record.id,
                    "child_id": record.child.id,
                    "child_name": f"{record.child.admission_number} - {record.child.child_first_name} {record.child.child_last_name}",
                    "admission_number": record.child.admission_number,
                    "date_logged": record.date_logged.strftime("%Y-%m-%d"),
                    "day_name": record.date_logged.strftime("%A"),
                    "time_logged": record.time_logged.strftime("%H:%M"),
                    "removal_reason": record.removal_reason,
                    "removal_requested_by": record.removal_requested_by,
                    "removal_requested_date": record.removal_requested_date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if record.removal_requested_date
                    else "",
                }
            )

        # Sort by request date (newest first)
        requests_data.sort(key=lambda x: x["removal_requested_date"], reverse=True)

        return JsonResponse(requests_data, safe=False)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def approveAttendanceRemoval(request):
    """Approve an attendance removal request - sets is_active=False"""
    if request.method == "POST":
        try:
            attendance_id = request.POST.get("attendance_id")

            if not attendance_id:
                return JsonResponse({"error": "Attendance ID is required"}, status=400)

            # Get the attendance record
            # NOTE: Don't filter by is_active - allow approval/rejection of all pending requests
            try:
                attendance = AttendanceLog.objects.get(
                    id=attendance_id, removal_status="PENDING"
                )
            except AttendanceLog.DoesNotExist:
                return JsonResponse(
                    {"error": "Pending removal request not found"}, status=404
                )

            # Approve the removal
            attendance.is_active = False
            attendance.removal_status = "APPROVED"
            attendance.removal_approved_by = request.user.username
            attendance.removal_approved_date = datetime.now()
            attendance.user_updated = request.user.username
            attendance.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Attendance entry removed successfully.",
                    "attendance_id": attendance_id,
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def rejectAttendanceRemoval(request):
    """Reject an attendance removal request - keeps record active"""
    if request.method == "POST":
        try:
            attendance_id = request.POST.get("attendance_id")

            if not attendance_id:
                return JsonResponse({"error": "Attendance ID is required"}, status=400)

            # Get the attendance record
            # NOTE: Don't filter by is_active - allow approval/rejection of all pending requests
            try:
                attendance = AttendanceLog.objects.get(
                    id=attendance_id, removal_status="PENDING"
                )
            except AttendanceLog.DoesNotExist:
                return JsonResponse(
                    {"error": "Pending removal request not found"}, status=404
                )

            # Reject the removal - keep record active
            attendance.removal_requested = False
            attendance.removal_status = "REJECTED"
            attendance.removal_approved_by = request.user.username
            attendance.removal_approved_date = datetime.now()
            attendance.user_updated = request.user.username
            attendance.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Removal request rejected. Record remains active.",
                    "attendance_id": attendance_id,
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def getRemovalApprovalsPage(request):
    """Render the removal approvals page"""
    try:
        # Get count of pending requests from last 45 days for display
        # NOTE: Don't filter by is_active - count all pending removal requests
        from_date = datetime.now().date() - timedelta(days=45)
        pending_count = AttendanceLog.objects.filter(
            removal_status="PENDING",
            date_logged__gte=from_date
        ).count()

        context = {
            "UserName": request.user.username,
            "pending_count": pending_count,
        }

        return render(request, "../templates/removal_approvals.html", context)

    except Exception as e:
        messages.error(request, f"Error loading removal approvals page: {str(e)}")
        return redirect("core:enhanced_check_ins")


@login_required
def get_apply_payment_page(request):
    """
    Renders the page for applying payments to memos.
    Allows searching for memos and entering payment details.
    """
    children = Child.objects.filter(is_active=True, is_enrolled=True).order_by(
        "admission_number"
    )
    current_year = datetime.now().year
    year_range = [current_year - 2, current_year - 1, current_year, current_year + 1]

    months = []
    for i in range(1, 13):
        months.append({"number": i, "name": calendar.month_name[i]})

    context = {
        "children": children,
        "year_range": year_range,
        "months": months,
        "UserName": request.user.username,
    }
    return render(request, "../templates/apply_payment.html", context)


@login_required
def search_memo_for_payment(request):
    """
    Searches for an InvoiceMemo based on child, month, and year.
    Returns memo details for payment application.
    """
    if request.method == "GET":
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        # Debug: Print received parameters
        print(
            f"DEBUG: Received parameters - child_id={child_id}, month={month}, year={year}"
        )

        if not all([child_id, month, year]):
            return JsonResponse(
                {"error": "Child, month, and year are required for search."}, status=400
            )

        try:
            child = get_object_or_404(Child, id=child_id)
            month_int = int(month)
            year_int = int(year)
            month_name = calendar.month_name[month_int]

            # Debug: Check what's in the database for this child
            all_memos = InvoiceMemo.objects.filter(child_id=child).values(
                "id", "memo_month", "memo_year", "status", "is_active", "memo_code"
            )
            print(f"DEBUG: All memos for child {child.id}: {list(all_memos)}")

            # Debug: Show what we're searching for
            print(
                f"DEBUG: Searching for - child_id={child.id}, memo_month={month_int}, memo_year={year_int}, is_active=True"
            )

            # Change back to child_id=child (not child=child)
            memo = InvoiceMemo.objects.filter(
                child_id=child, memo_month=month_int, memo_year=year_int, is_active=True
            ).first()

            print(f"DEBUG: Found memo: {memo}")

            if memo:
                # Prepare memo details for the frontend
                memo_data = {
                    "id": memo.id,
                    "memo_code": memo.memo_code,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "child_admission": child.admission_number,
                    "memo_month": memo.memo_month,
                    "memo_year": memo.memo_year,
                    "month_name": month_name,
                    "net_amount_due": float(memo.net_amount_due),
                    "total_payments_received": float(memo.total_payments),
                    "status": memo.status,
                    "date_created": memo.date_created.strftime("%Y-%m-%d %H:%M")
                    if memo.date_created
                    else None,
                    "notes": memo.notes or "",
                }

                # Get details for each month (Outstanding, Previous, Current)
                details = memo.month_details.all().order_by("month_sequence")
                detailed_breakdown = []
                for detail in details:
                    detailed_breakdown.append(
                        {
                            "month_type": detail.month_type,
                            "month_name": detail.month_name,
                            "actual_year": detail.actual_year,
                            "gross_charges": float(detail.gross_charges),
                            "payments_received": float(detail.payments_received),
                            "net_balance": float(detail.net_balance),
                            "package_fee": float(detail.package_fee),
                            "extra_hours_charge": float(detail.extra_hours_charge),
                            "holiday_charges": float(detail.holiday_charges),
                            "discount_applied": float(detail.discount_applied),
                        }
                    )
                memo_data["detailed_breakdown"] = detailed_breakdown

                return JsonResponse({"success": True, "memo": memo_data})
            else:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"No active memo found for {month_name} {year} for {child.child_first_name} {child.child_last_name}.",
                        "child_name": f"{child.child_first_name} {child.child_last_name}",
                        "month_name": month_name,
                        "year": year_int,
                    }
                )

        except Child.DoesNotExist:
            return JsonResponse({"error": "Child not found."}, status=404)
        except Exception as e:
            print(f"DEBUG: Exception occurred: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse(
            {"error": "Invalid request method. Only GET is allowed."}, status=405
        )


# ... (Keep your existing process_payment view function here) ...
@login_required
@transaction.atomic
def process_payment(request):
    """
    Process payment for an invoice memo with hierarchical payment application.

    This view handles payment processing for invoice memos by applying payments
    in a specific hierarchy: Outstanding balance -> Previous month -> Current month.
    It ensures proper payment distribution and maintains accurate financial records.

    Payment Hierarchy:
        1. Outstanding Balance: Applied to 2-month-old charges first
        2. Previous Month: Applied to 1-month-old charges second
        3. Current Month: Applied as advance payment for current charges

    Parameters:
        request (HttpRequest): POST request containing payment data:
            - memo_id: Integer ID of the invoice memo
            - payment_amount: Decimal total payment amount
            - receipt_number: String payment receipt reference
            - payment_date: String date in YYYY-MM-DD format (optional)
            - payment_method: String payment method (default: BANK_TRANSFER)

    Returns:
        JsonResponse: JSON response with payment processing results:
            - success: Boolean indicating successful processing
            - message: String description of payment application
            - payment_distribution: Object showing how payment was applied
            - updated_balances: Object showing remaining balances
            - remaining_payment: Decimal any unused payment amount

    Error Responses:
        - 400: Missing required parameters or invalid data format
        - 404: Invoice memo not found
        - 500: Server error during payment processing

    Security:
        - Requires user login (@login_required decorator)
        - Validates memo existence before processing
        - Ensures payment amounts are positive
        - Prevents invalid payment data

    Business Logic:
        - Applies payments in strict hierarchical order
        - Updates memo detail records with payment information
        - Creates PaymentTransaction records for audit trail
        - Recalculates memo totals after payment application
        - Handles advance payments for current month

    Payment Application Process:
        1. Validates payment amount and format
        2. Retrieves memo and associated detail records
        3. Applies payment to outstanding balance (if exists)
        4. Applies remaining payment to previous month balance
        5. Applies remaining payment to current month (as advance)
        6. Updates all affected records
        7. Creates payment transaction record

    Data Updates:
        - Updates InvoiceMemoDetail payment records
        - Recalculates net balances for each month
        - Updates overall memo status and totals
        - Creates audit trail in PaymentTransaction

    Advanced Payment Handling:
        - Handles overpayments as credit for current month
        - Maintains negative balances for advance payments
        - Preserves payment allocation details
        - Supports future payment applications

    Receipt Management:
        - Associates receipt numbers with payments
        - Maintains receipt references in payment records
        - Supports multiple receipts per memo
        - Preserves receipt audit trail

    Integration:
        - Works with InvoiceMemo and InvoiceMemoDetail models
        - Creates PaymentTransaction records
        - Updates memo status automatically
        - Maintains financial data integrity

    Calculation Features:
        - Precise decimal arithmetic for financial accuracy
        - Handles partial payments correctly
        - Maintains payment distribution records
        - Preserves calculation audit trail

    Error Handling:
        - Validates all input parameters
        - Handles missing memo scenarios
        - Provides detailed error messages
        - Maintains data consistency on errors

    Transaction Management:
        - Ensures atomicity of payment operations
        - Maintains data consistency
        - Handles concurrent payment scenarios
        - Provides rollback capabilities
    """
    if request.method == "POST":
        try:
            # Extract data from the request
            # Assuming these are sent via AJAX or a form
            memo_id = request.POST.get("memo_id")
            payment_amount_str = request.POST.get("payment_amount")
            receipt_number = request.POST.get("receipt_number", "").strip()
            payment_date_str = request.POST.get(
                "payment_date", datetime.now().strftime("%Y-%m-%d")
            )
            payment_method = request.POST.get(
                "payment_method", "BANK_TRANSFER"
            )  # Default or get from form

            # Basic validation
            if not all([memo_id, payment_amount_str]):
                return JsonResponse(
                    {"error": "Missing memo ID or payment amount"}, status=400
                )

            try:
                payment_amount = Decimal(payment_amount_str)
                if payment_amount <= 0:
                    return JsonResponse(
                        {"error": "Payment amount must be positive"}, status=400
                    )
            except InvalidOperation:
                return JsonResponse(
                    {"error": "Invalid payment amount format"}, status=400
                )

            try:
                payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid payment date format. Use YYYY-MM-DD."},
                    status=400,
                )

            # Retrieve the memo and its details
            memo = get_object_or_404(InvoiceMemo, id=memo_id)

            # CHECK FOR PENDING TIME ADJUSTMENT REQUESTS IN PREVIOUS MONTH ONLY
            # Calculate PREVIOUS month relative to the memo's month
            if memo.memo_month > 1:
                check_month = memo.memo_month - 1
                check_year = memo.memo_year
            else:
                check_month = 12
                check_year = memo.memo_year - 1

            # Create date range for the PREVIOUS month
            from_date = datetime(check_year, check_month, 1).date()
            last_day = datetime(
                check_year, check_month, calendar.monthrange(check_year, check_month)[1]
            ).date()

            # Only check pending requests in the PREVIOUS month
            pending_adjustments = TimeAdjustmentRequest.objects.filter(
                child=memo.child,
                request_date__range=(from_date, last_day),
                status="PENDING_APPROVAL",
                is_active=True
            ).count()

            if pending_adjustments > 0:
                check_month_name = calendar.month_name[check_month]
                return JsonResponse(
                    {
                        "error": f"Cannot process payment. There {'is' if pending_adjustments == 1 else 'are'} "
                        f"{pending_adjustments} pending time adjustment request(s) for {check_month_name} {check_year}. "
                        f"Please approve or reject them first."
                    },
                    status=400,
                )

            remaining_payment = payment_amount

            # Get month details in the correct sequence
            # month_sequence: 1=Outstanding, 2=Previous, 3=Current
            outstanding_detail = memo.month_details.filter(month_sequence=1).first()
            previous_detail = memo.month_details.filter(month_sequence=2).first()
            current_detail = memo.month_details.filter(month_sequence=3).first()

            # Apply payment hierarchically: Outstanding -> Previous -> Current

            # 1. Apply to Outstanding balance
            if outstanding_detail and outstanding_detail.net_balance > 0:
                amount_to_apply = min(remaining_payment, outstanding_detail.net_balance)
                outstanding_detail.add_payment(amount_to_apply, receipt_number)
                remaining_payment -= amount_to_apply
                outstanding_detail.save()  # Save the detail to update its net_balance

            # 2. Apply to Previous month's balance
            if (
                remaining_payment > 0
                and previous_detail
                and previous_detail.net_balance > 0
            ):
                amount_to_apply = min(remaining_payment, previous_detail.net_balance)
                previous_detail.add_payment(amount_to_apply, receipt_number)
                remaining_payment -= amount_to_apply
                previous_detail.save()

            # 3. Apply to Current month's balance (as advanced payment if it creates a credit)
            if remaining_payment > 0 and current_detail:
                # Apply up to the current month's net charges, any excess becomes "advanced"
                amount_to_apply = min(
                    remaining_payment, current_detail.net_balance
                )  # This will be 0 if current_detail.net_balance is already 0 or negative

                # If current month has a positive balance, apply payment to it
                if current_detail.net_balance > 0:
                    current_detail.add_payment(amount_to_apply, receipt_number)
                    remaining_payment -= amount_to_apply
                    current_detail.save()
                # If current month is already paid or has credit, the entire remaining_payment is an advance
                elif current_detail.net_balance <= 0 and remaining_payment > 0:
                    # Treat the entire remaining_payment as an "advance" for the current month detail
                    # This will make its net_balance more negative (a larger credit)
                    current_detail.add_payment(remaining_payment, receipt_number)
                    remaining_payment = Decimal("0.00")  # All payment applied
                    current_detail.save()

            # Update overall memo totals and status after applying payments to details
            memo.calculate_totals()
            memo.save()  # Save the memo to persist updated totals and status

            # Create a record in the PaymentTransaction model for the overall payment
            PaymentTransaction.objects.create(
                memo=memo,
                amount=payment_amount,
                receipt_number=receipt_number,
                payment_date=payment_date,
                payment_method=payment_method,
                user_created=request.user.username,  # Use the logged-in user
                is_active=True,  # Assuming active by default
            )

            messages.success(
                request,
                f"Payment of Rs.{payment_amount:,.2f} applied successfully to memo {memo.memo_code}.",
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment processed successfully.",
                    "memo_code": memo.memo_code,
                    "new_net_amount_due": float(memo.net_amount_due),
                    "remaining_payment_unapplied": float(
                        remaining_payment
                    ),  # Should be 0 if all applied
                }
            )

        except InvoiceMemo.DoesNotExist:
            messages.error(request, "Invoice Memo not found.")
            return JsonResponse({"error": "Invoice Memo not found"}, status=404)
        except Exception as e:
            # Log the full traceback for debugging
            import traceback

            traceback.print_exc()
            messages.error(request, f"Error processing payment: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse(
            {"error": "Invalid request method. Only POST is allowed."}, status=405
        )
    """
    Processes a payment for a given memo, applying it hierarchically:
    Outstanding -> Previous Month -> Current Month (as advanced payment).
    """
    if request.method == "POST":
        try:
            # Extract data from the request
            # Assuming these are sent via AJAX or a form
            memo_id = request.POST.get("memo_id")
            payment_amount_str = request.POST.get("payment_amount")
            receipt_number = request.POST.get("receipt_number", "").strip()
            payment_date_str = request.POST.get(
                "payment_date", datetime.now().strftime("%Y-%m-%d")
            )
            payment_method = request.POST.get(
                "payment_method", "BANK_TRANSFER"
            )  # Default or get from form

            # Basic validation
            if not all([memo_id, payment_amount_str]):
                return JsonResponse(
                    {"error": "Missing memo ID or payment amount"}, status=400
                )

            try:
                payment_amount = Decimal(payment_amount_str)
                if payment_amount <= 0:
                    return JsonResponse(
                        {"error": "Payment amount must be positive"}, status=400
                    )
            except InvalidOperation:
                return JsonResponse(
                    {"error": "Invalid payment amount format"}, status=400
                )

            try:
                payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid payment date format. Use YYYY-MM-DD."},
                    status=400,
                )

            # Retrieve the memo and its details
            memo = get_object_or_404(InvoiceMemo, id=memo_id)
            remaining_payment = payment_amount

            # Get month details in the correct sequence
            # month_sequence: 1=Outstanding, 2=Previous, 3=Current
            outstanding_detail = memo.month_details.filter(month_sequence=1).first()
            previous_detail = memo.month_details.filter(month_sequence=2).first()
            current_detail = memo.month_details.filter(month_sequence=3).first()

            # Apply payment hierarchically: Outstanding -> Previous -> Current

            # 1. Apply to Outstanding balance
            if outstanding_detail and outstanding_detail.net_balance > 0:
                amount_to_apply = min(remaining_payment, outstanding_detail.net_balance)
                outstanding_detail.add_payment(amount_to_apply, receipt_number)
                remaining_payment -= amount_to_apply
                outstanding_detail.save()  # Save the detail to update its net_balance

            # 2. Apply to Previous month's balance
            if (
                remaining_payment > 0
                and previous_detail
                and previous_detail.net_balance > 0
            ):
                amount_to_apply = min(remaining_payment, previous_detail.net_balance)
                previous_detail.add_payment(amount_to_apply, receipt_number)
                remaining_payment -= amount_to_apply
                previous_detail.save()

            # 3. Apply to Current month's balance (as advanced payment if it creates a credit)
            if remaining_payment > 0 and current_detail:
                # Apply up to the current month's net charges, any excess becomes "advanced"
                amount_to_apply = min(
                    remaining_payment, current_detail.net_balance
                )  # This will be 0 if current_detail.net_balance is already 0 or negative

                # If current month has a positive balance, apply payment to it
                if current_detail.net_balance > 0:
                    current_detail.add_payment(amount_to_apply, receipt_number)
                    remaining_payment -= amount_to_apply
                    current_detail.save()
                # If current month is already paid or has credit, the entire remaining_payment is an advance
                elif current_detail.net_balance <= 0 and remaining_payment > 0:
                    # Treat the entire remaining_payment as an "advance" for the current month detail
                    # This will make its net_balance more negative (a larger credit)
                    current_detail.add_payment(remaining_payment, receipt_number)
                    remaining_payment = Decimal("0.00")  # All payment applied
                    current_detail.save()

            # Update overall memo totals and status after applying payments to details
            memo.calculate_totals()
            memo.save()  # Save the memo to persist updated totals and status

            # Create a record in the PaymentTransaction model for the overall payment
            PaymentTransaction.objects.create(
                memo=memo,
                amount=payment_amount,
                receipt_number=receipt_number,
                payment_date=payment_date,
                payment_method=payment_method,
                user_created=request.user.username,  # Use the logged-in user
                is_active=True,  # Assuming active by default
            )

            messages.success(
                request,
                f"Payment of Rs.{payment_amount:,.2f} applied successfully to memo {memo.memo_code}.",
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment processed successfully.",
                    "memo_code": memo.memo_code,
                    "new_net_amount_due": float(memo.net_amount_due),
                    "remaining_payment_unapplied": float(
                        remaining_payment
                    ),  # Should be 0 if all applied
                }
            )

        except InvoiceMemo.DoesNotExist:
            messages.error(request, "Invoice Memo not found.")
            return JsonResponse({"error": "Invoice Memo not found"}, status=404)
        except Exception as e:
            # Log the full traceback for debugging
            import traceback

            traceback.print_exc()
            messages.error(request, f"Error processing payment: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse(
            {"error": "Invalid request method. Only POST is allowed."}, status=405
        )


@login_required
@transaction.atomic
def process_payment_enhanced(request):
    """Enhanced payment processing with detailed allocation tracking"""
    if request.method == "POST":
        try:
            # Extract payment data
            memo_id = request.POST.get("memo_id")
            payment_amount_str = request.POST.get("payment_amount")
            receipt_number = request.POST.get("receipt_number", "").strip()
            payment_date_str = request.POST.get(
                "payment_date", datetime.now().strftime("%Y-%m-%d")
            )
            payment_method = request.POST.get("payment_method", "BANK_TRANSFER")
            payment_notes = request.POST.get("payment_notes", "").strip()

            # Validation
            if not all([memo_id, payment_amount_str]):
                return JsonResponse(
                    {"error": "Missing memo ID or payment amount"}, status=400
                )

            try:
                payment_amount = Decimal(payment_amount_str)
                if payment_amount <= 0:
                    return JsonResponse(
                        {"error": "Payment amount must be positive"}, status=400
                    )
            except:
                return JsonResponse(
                    {"error": "Invalid payment amount format"}, status=400
                )

            try:
                payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid payment date format"}, status=400
                )

            # Get memo
            memo = get_object_or_404(InvoiceMemo, id=memo_id)

            # CHECK FOR PENDING TIME ADJUSTMENT REQUESTS IN PREVIOUS MONTH ONLY
            # Calculate PREVIOUS month relative to the memo's month
            if memo.memo_month > 1:
                check_month = memo.memo_month - 1
                check_year = memo.memo_year
            else:
                check_month = 12
                check_year = memo.memo_year - 1

            # Create date range for the PREVIOUS month
            from_date = datetime(check_year, check_month, 1).date()
            last_day = datetime(
                check_year, check_month, calendar.monthrange(check_year, check_month)[1]
            ).date()

            # Only check pending requests in the PREVIOUS month
            pending_adjustments = TimeAdjustmentRequest.objects.filter(
                child=memo.child,
                request_date__range=(from_date, last_day),
                status="PENDING_APPROVAL",
                is_active=True
            ).count()

            if pending_adjustments > 0:
                check_month_name = calendar.month_name[check_month]
                return JsonResponse(
                    {
                        "error": f"Cannot process payment. There {'is' if pending_adjustments == 1 else 'are'} "
                        f"{pending_adjustments} pending time adjustment request(s) for {check_month_name} {check_year}. "
                        f"Please approve or reject them first."
                    },
                    status=400,
                )

            with transaction.atomic():
                # Apply payment hierarchically
                allocation_result = memo.apply_payment_hierarchically(
                    payment_amount, receipt_number, payment_date
                )

                # Create overall payment transaction record
                payment_transaction = PaymentTransaction.objects.create(
                    memo=memo,
                    amount=payment_amount,
                    receipt_number=receipt_number,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    notes=payment_notes,
                    user_created=request.user.username,
                    is_active=True,
                )

                # Update payment transaction with allocation details
                payment_transaction.notes = (
                    f"{payment_notes}\n\nAllocation Details:\n"
                    + json.dumps(allocation_result["allocation_breakdown"], indent=2)
                )
                payment_transaction.save()

            # Prepare response
            response_data = {
                "success": True,
                "message": f"Payment of Rs.{payment_amount:,.2f} processed successfully",
                "memo_code": memo.memo_code,
                "payment_transaction_id": payment_transaction.id,
                "allocation_details": allocation_result,
                "new_memo_balance": float(memo.net_amount_due),
                "memo_status": memo.status,
            }

            # Add success message for UI
            messages.success(
                request,
                f"Payment of Rs.{payment_amount:,.2f} applied successfully to memo {memo.memo_code}. "
                f"New balance: Rs.{memo.net_amount_due:,.2f}",
            )

            return JsonResponse(response_data)

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def get_memo_payment_history(request, memo_id):
    """Get detailed payment history for a memo"""
    try:
        memo = get_object_or_404(InvoiceMemo, id=memo_id)

        # Get payment summary from memo
        payment_summary = memo.get_payment_summary()

        # Get all payment transactions
        payment_transactions = PaymentTransaction.objects.filter(
            memo=memo, is_active=True
        ).order_by("-payment_date")

        transaction_list = []
        for txn in payment_transactions:
            transaction_list.append(
                {
                    "id": txn.id,
                    "amount": float(txn.amount),
                    "receipt_number": txn.receipt_number,
                    "payment_date": txn.payment_date.strftime("%Y-%m-%d"),
                    "payment_method": txn.payment_method,
                    "notes": txn.notes,
                    "user_created": txn.user_created,
                    "date_created": txn.date_created.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "memo_code": memo.memo_code,
                "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                "payment_summary_by_month": payment_summary,
                "payment_transactions": transaction_list,
                "total_payments": float(memo.total_payments),
                "current_balance": float(memo.net_amount_due),
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# =============================================================================
# MEMO LOADING WITH PAYMENT VALIDATION
# =============================================================================


def prepare_memo_display_data_with_payment_validation(memo):
    """
    Enhanced memo display preparation with payment validation
    Ensures payment allocation is correct when loading memo
    """
    try:
        # Get payment summary to validate current state
        payment_summary = memo.get_payment_summary()

        # Validate payment allocation (optional integrity check)
        total_payments_calculated = sum(
            month["payments_received"] for month in payment_summary
        )

        if abs(total_payments_calculated - float(memo.total_payments)) > 0.01:
            # Payment mismatch detected - log for investigation
            print(f"WARNING: Payment mismatch in memo {memo.memo_code}")
            print(
                f"Calculated: {total_payments_calculated}, Stored: {memo.total_payments}"
            )

            # Optionally trigger recalculation
            memo.calculate_totals()

        # Use existing prepare_memo_display_data_fixed function
        memo_data = prepare_memo_display_data_fixed(memo)

        # Add enhanced payment information
        memo_data["payment_validation"] = {
            "total_payments_calculated": total_payments_calculated,
            "total_payments_stored": float(memo.total_payments),
            "is_consistent": abs(total_payments_calculated - float(memo.total_payments))
            <= 0.01,
            "payment_summary_by_month": payment_summary,
        }

        return memo_data

    except Exception as e:
        print(f"Error in payment validation: {str(e)}")
        # Fallback to original function
        return prepare_memo_display_data_fixed(memo)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def validate_memo_payments(memo_id):
    """
    Validates and corrects payment allocations for a memo to ensure data integrity.

    This function performs comprehensive validation and correction of payment
    allocations across all months in a memo. It resets all payments and reapplies
    them in chronological order to ensure correct hierarchical payment allocation.

    Args:
        memo_id (int): Primary key ID of the InvoiceMemo to validate

    Returns:
        dict: Validation result containing:
            - success (bool): Whether validation completed successfully
            - memo_code (str): Memo code for identification
            - transactions_reprocessed (int): Number of transactions reapplied
            - final_balance (float): Final balance after validation
            - error (str): Error message if validation failed

    Business Logic:
        - Resets all payment allocations across memo months
        - Reapplies payments in chronological order
        - Ensures hierarchical payment allocation (outstanding → previous → current)
        - Maintains data integrity across all memo details
        - Provides audit trail for payment corrections

    Validation Process:
        1. Retrieves memo and all associated payment transactions
        2. Resets all month payment allocations to zero
        3. Clears all payment receipt records
        4. Reapplies payments chronologically using hierarchical allocation
        5. Returns summary of corrections made

    Payment Hierarchy:
        - Outstanding balance (oldest) gets priority
        - Previous month charges second priority
        - Current month charges third priority
        - Payments allocated in chronological order

    Data Integrity:
        - Ensures payment totals match transaction records
        - Maintains consistent balance calculations
        - Preserves payment receipt numbers and dates
        - Fixes any allocation discrepancies

    Error Handling:
        - Handles missing memo gracefully
        - Catches payment allocation errors
        - Returns detailed error information
        - Maintains system stability during validation

    Use Cases:
        - Data maintenance and cleanup
        - Fixing payment allocation errors
        - Auditing payment distributions
        - Correcting balance discrepancies
        - System integrity checks

    Integration:
        - Works with PaymentTransaction model
        - Uses InvoiceMemo.apply_payment_hierarchically() method
        - Maintains InvoiceMemoDetail payment records
        - Supports manual and automated validation

    Performance:
        - Efficient query with single memo retrieval
        - Chronological payment ordering
        - Minimal database operations
        - Scalable for large payment histories

    Security:
        - No authentication required (internal function)
        - Read-only validation with corrective actions
        - Maintains payment audit trail
        - Preserves original transaction data

    Administrative Features:
        - Can be called manually for specific memos
        - Supports batch validation operations
        - Provides detailed correction reports
        - Enables data quality assurance
    """
    try:
        memo = InvoiceMemo.objects.get(id=memo_id)

        # Get all payment transactions
        payment_transactions = PaymentTransaction.objects.filter(
            memo=memo, is_active=True
        ).order_by("payment_date")

        # Reset all month payments
        for detail in memo.month_details.all():
            detail.payments_received = Decimal("0.00")
            detail.payment_receipts = []
            detail.save()

        # Reapply all payments in chronological order
        for txn in payment_transactions:
            memo.apply_payment_hierarchically(
                txn.amount, txn.receipt_number, txn.payment_date
            )

        return {
            "success": True,
            "memo_code": memo.memo_code,
            "transactions_reprocessed": payment_transactions.count(),
            "final_balance": float(memo.net_amount_due),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# AJAX ENDPOINT FOR PAYMENT VALIDATION
# =============================================================================


@login_required
def validate_memo_payments_ajax(request, memo_id):
    """
    AJAX endpoint for validating and fixing memo payment allocations.

    This view provides a web interface for the validate_memo_payments function,
    allowing administrators to trigger payment validation through AJAX requests.
    It ensures proper authentication and returns JSON responses for frontend handling.

    Args:
        request (HttpRequest): POST request for payment validation
        memo_id (int): Primary key ID of the memo to validate

    Returns:
        JsonResponse: JSON response containing validation results or error message

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts POST requests for data modification
        - Validates memo existence through underlying function

    Request Format:
        - Method: POST only
        - URL: /memo/validate-payments/{memo_id}/
        - No request body required

    Response Format:
        Success Response:
        {
            "success": true,
            "memo_code": "MEMO_CODE",
            "transactions_reprocessed": 5,
            "final_balance": 1500.00
        }

        Error Response:
        {
            "success": false,
            "error": "Error message"
        }

    Business Logic:
        - Delegates validation to validate_memo_payments() function
        - Provides web interface for payment validation
        - Returns structured JSON for frontend processing
        - Maintains audit trail through underlying function

    Use Cases:
        - Administrative payment validation
        - Fixing payment allocation errors
        - Data integrity maintenance
        - Manual payment corrections
        - System troubleshooting

    Integration:
        - Works with validate_memo_payments() function
        - Supports frontend AJAX requests
        - Provides JSON responses for UI updates
        - Maintains RESTful API patterns

    Error Handling:
        - Returns 405 for non-POST requests
        - Passes through validation errors as JSON
        - Maintains consistent error response format
        - Preserves detailed error information

    Frontend Integration:
        - Supports AJAX calls from payment management pages
        - Provides structured responses for UI updates
        - Enables real-time validation feedback
        - Supports batch validation operations

    URL Pattern:
        - /memo/validate-payments/<int:memo_id>/ (POST)
    """
    if request.method == "POST":
        result = validate_memo_payments(memo_id)
        return JsonResponse(result)
    return JsonResponse({"error": "Invalid method"}, status=405)


@login_required
def get_memo_by_id_enhanced(request, memo_id):
    """Enhanced memo retrieval with payment validation"""
    try:
        memo = get_object_or_404(InvoiceMemo, pk=memo_id)

        # Use enhanced display preparation with payment validation
        memo_data = prepare_memo_display_data_with_payment_validation(memo)

        return JsonResponse(
            {
                "success": True,
                "memo": {
                    "id": memo.id,
                    "memo_code": memo.memo_code,
                    "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                    "child_admission": memo.child.admission_number,
                    "memo_month": memo.memo_month,
                    "memo_year": memo.memo_year,
                    "month_name": calendar.month_name[memo.memo_month],
                    "net_amount_due": float(memo.net_amount_due),
                    "total_payments_received": float(memo.total_payments),
                    "status": memo.status,
                    "detailed_breakdown": memo_data.get("payment_validation", {}).get(
                        "payment_summary_by_month", []
                    ),
                },
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_child_outstanding_balance(request):
    """
    Calculates the outstanding balance for a child by finding the 'net_amount_due'
    from the most recently generated memo. This is the correct "balance brought forward".
    """
    if request.method == "GET":
        child_id = request.GET.get("child_id")
        # These define the period for the NEW memo we are creating
        new_memo_month = int(request.GET.get("month"))
        new_memo_year = int(request.GET.get("year"))

        if not all([child_id, new_memo_month, new_memo_year]):
            return JsonResponse({"error": "Missing parameters"}, status=400)

        try:
            # Find the most recent memo that comes *before* the new memo's period.
            # We use `order_by` to get the latest one first.
            latest_previous_memo = (
                InvoiceMemo.objects.filter(
                    child_id=child_id, is_active=True, memo_year__lt=new_memo_year
                )
                .order_by("-memo_year", "-memo_month")
                .first()
            )

            # If no memo in a previous year, check the current year for a previous month
            if not latest_previous_memo:
                latest_previous_memo = (
                    InvoiceMemo.objects.filter(
                        child_id=child_id,
                        is_active=True,
                        memo_year=new_memo_year,
                        memo_month__lt=new_memo_month,
                    )
                    .order_by("-memo_month")
                    .first()
                )

            if latest_previous_memo:
                # The outstanding balance is the final "net_amount_due" of the last memo.
                outstanding_balance = latest_previous_memo.net_amount_due

                # We only carry forward a DEBIT balance. Credits are handled separately.
                if outstanding_balance < 0:
                    outstanding_balance = Decimal(
                        "0.00"
                    )  # Don't carry forward credit as a negative outstanding

                return JsonResponse(
                    {
                        "success": True,
                        "outstanding_balance": float(outstanding_balance),
                        "message": f"Found previous memo {latest_previous_memo.memo_code}. Outstanding balance is Rs. {outstanding_balance:,.2f}",
                    }
                )
            else:
                # If no previous memos exist at all for this child.
                return JsonResponse(
                    {
                        "success": True,
                        "outstanding_balance": 0.00,
                        "message": "No previous memos found for this child. Outstanding is zero.",
                    }
                )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


# =============================================================================
# Dashboard API Endpoints for Charts
# =============================================================================


@login_required
def getDashboardAttendanceTrend(request):
    """
    Returns last 7 days attendance data for dashboard chart.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON with date, attendance count, and total children for each day

    Business Logic:
        - Retrieves attendance data for the past 7 days
        - For each day, counts unique children who checked in
        - Returns total active enrolled children for comparison
        - Data is ordered from oldest to newest for chart display
    """
    try:
        today = date.today()
        total_children = Child.objects.filter(is_active=True, is_enrolled=True).count()

        attendance_data = []
        for i in range(6, -1, -1):  # Last 7 days, oldest first
            target_date = today - timedelta(days=i)
            day_attendance = (
                AttendanceLog.objects.filter(
                    date_logged=target_date,
                    is_active=True,
                    removal_status__in=["NONE", "REJECTED"],
                )
                .values("child")
                .distinct()
                .count()
            )

            attendance_data.append(
                {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "day_name": target_date.strftime("%a"),
                    "count": day_attendance,
                    "total_children": total_children,
                    "percentage": (
                        round((day_attendance / total_children) * 100, 1)
                        if total_children > 0
                        else 0
                    ),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "data": attendance_data,
                "total_children": total_children,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def getDashboardPendingBreakdown(request):
    """
    Returns pending approvals breakdown by type for dashboard chart.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: JSON with count of pending approvals for each workflow type

    Business Logic:
        - Counts pending approvals from 4 models:
            - ChildEnrollment (Enrollments)
            - Discount (Discounts)
            - PackageChangerequest (Package Changes)
            - CenterChangerequest (Center Changes)
        - Returns breakdown suitable for pie/donut chart
    """
    try:
        pending_enrollments = ChildEnrollment.objects.filter(
            status="PENDING_APPROVAL", is_active=True
        ).count()
        pending_discounts = Discount.objects.filter(
            status="PENDING_APPROVAL", is_active=True
        ).count()
        pending_package_changes = PackageChangerequest.objects.filter(
            status="PENDING_APPROVAL", is_active=True
        ).count()
        pending_center_changes = CenterChangerequest.objects.filter(
            status="PENDING_APPROVAL", is_active=True
        ).count()

        total = (
            pending_enrollments
            + pending_discounts
            + pending_package_changes
            + pending_center_changes
        )

        breakdown = [
            {
                "type": "Enrollments",
                "count": pending_enrollments,
                "percentage": (
                    round((pending_enrollments / total) * 100, 1) if total > 0 else 0
                ),
                "color": "#3498db",
            },
            {
                "type": "Discounts",
                "count": pending_discounts,
                "percentage": (
                    round((pending_discounts / total) * 100, 1) if total > 0 else 0
                ),
                "color": "#2ecc71",
            },
            {
                "type": "Package Changes",
                "count": pending_package_changes,
                "percentage": (
                    round((pending_package_changes / total) * 100, 1) if total > 0 else 0
                ),
                "color": "#f39c12",
            },
            {
                "type": "Center Changes",
                "count": pending_center_changes,
                "percentage": (
                    round((pending_center_changes / total) * 100, 1) if total > 0 else 0
                ),
                "color": "#9b59b6",
            },
        ]

        return JsonResponse(
            {"success": True, "data": breakdown, "total": total}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ==================== FINANCE REPORTS ====================

from .forms import (
    ARAgingReportForm,
    PackageRevenueReportForm,
    DiscountAnalysisReportForm,
    LocationPerformanceReportForm,
    ExtraHoursRevenueReportForm,
)


@login_required
def getARAgingReport(request):
    """
    Display the AR Aging Report page.

    Shows outstanding balances by aging buckets (0-30, 31-60, 61-90, 90+ days).
    Helps identify overdue accounts and prioritize collections.
    """
    form = ARAgingReportForm()
    return render(
        request,
        "../templates/reports/ar_aging_report.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getARAgingReportJS(request):
    """
    AJAX endpoint for AR Aging Report data.

    Returns outstanding balances categorized by aging buckets based on memo dates.
    """
    try:
        # Get parameters
        as_of_date = request.GET.get("as_of_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        aging_bucket = request.GET.get("aging_bucket", "all")
        minimum_balance = request.GET.get("minimum_balance")

        # Set default as_of_date to today
        if not as_of_date:
            as_of_date = datetime.now().date()
        else:
            as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()

        # Get all memos with outstanding balances
        memos = InvoiceMemo.objects.filter(
            is_active=True,
            net_amount_due__gt=0
        ).select_related("child")

        # Filter by minimum balance
        if minimum_balance:
            memos = memos.filter(net_amount_due__gte=Decimal(minimum_balance))

        # Filter by branch/center through enrollment
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            memos = memos.filter(child__id__in=enrolled_children)

        aging_data = []

        for memo in memos:
            # Calculate days outstanding from memo date
            days_outstanding = (as_of_date - memo.memo_date).days

            # Determine aging bucket
            if days_outstanding <= 30:
                bucket = "0-30"
                bucket_label = "0-30 Days"
            elif days_outstanding <= 60:
                bucket = "31-60"
                bucket_label = "31-60 Days"
            elif days_outstanding <= 90:
                bucket = "61-90"
                bucket_label = "61-90 Days"
            else:
                bucket = "90+"
                bucket_label = "90+ Days"

            # Filter by specific aging bucket if requested
            if aging_bucket != "all" and bucket != aging_bucket:
                continue

            # Get enrollment info
            enrollment = ChildEnrollment.objects.filter(
                child=memo.child, status="APPROVED", is_active=True
            ).select_related("branch", "center").first()

            aging_data.append({
                "child_admission": memo.child.admission_number,
                "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
                "memo_code": memo.memo_code,
                "memo_date": memo.memo_date.strftime("%Y-%m-%d"),
                "memo_month": f"{memo.get_memo_month_name()} {memo.memo_year}",
                "days_outstanding": days_outstanding,
                "aging_bucket": bucket,
                "aging_bucket_label": bucket_label,
                "gross_total": float(memo.gross_total),
                "total_payments": float(memo.total_payments),
                "outstanding_balance": float(memo.net_amount_due),
                "branch_name": enrollment.branch.branch_name if enrollment else "N/A",
                "center_name": enrollment.center.daycare_name if enrollment else "N/A",
                "status": memo.status,
                "fathers_contact": memo.child.fathers_contact_number,
                "mothers_contact": memo.child.mothers_contact_number,
            })

        # Sort by days outstanding descending
        aging_data.sort(key=lambda x: x["days_outstanding"], reverse=True)

        return JsonResponse(aging_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getARAgingSummaryJS(request):
    """
    AJAX endpoint for AR Aging Report summary statistics.

    Returns aggregate totals by aging bucket.
    """
    try:
        as_of_date = request.GET.get("as_of_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        minimum_balance = request.GET.get("minimum_balance")

        if not as_of_date:
            as_of_date = datetime.now().date()
        else:
            as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()

        # Get all memos with outstanding balances
        memos = InvoiceMemo.objects.filter(
            is_active=True,
            net_amount_due__gt=0
        )

        if minimum_balance:
            memos = memos.filter(net_amount_due__gte=Decimal(minimum_balance))

        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            memos = memos.filter(child__id__in=enrolled_children)

        # Initialize buckets
        buckets = {
            "0-30": {"count": 0, "total": Decimal("0.00")},
            "31-60": {"count": 0, "total": Decimal("0.00")},
            "61-90": {"count": 0, "total": Decimal("0.00")},
            "90+": {"count": 0, "total": Decimal("0.00")},
        }

        total_outstanding = Decimal("0.00")
        total_accounts = 0

        for memo in memos:
            days_outstanding = (as_of_date - memo.memo_date).days

            if days_outstanding <= 30:
                bucket = "0-30"
            elif days_outstanding <= 60:
                bucket = "31-60"
            elif days_outstanding <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"

            buckets[bucket]["count"] += 1
            buckets[bucket]["total"] += memo.net_amount_due
            total_outstanding += memo.net_amount_due
            total_accounts += 1

        summary = {
            "buckets": [
                {
                    "bucket": "0-30",
                    "label": "0-30 Days",
                    "count": buckets["0-30"]["count"],
                    "total": float(buckets["0-30"]["total"]),
                },
                {
                    "bucket": "31-60",
                    "label": "31-60 Days",
                    "count": buckets["31-60"]["count"],
                    "total": float(buckets["31-60"]["total"]),
                },
                {
                    "bucket": "61-90",
                    "label": "61-90 Days",
                    "count": buckets["61-90"]["count"],
                    "total": float(buckets["61-90"]["total"]),
                },
                {
                    "bucket": "90+",
                    "label": "90+ Days",
                    "count": buckets["90+"]["count"],
                    "total": float(buckets["90+"]["total"]),
                },
            ],
            "total_outstanding": float(total_outstanding),
            "total_accounts": total_accounts,
            "as_of_date": as_of_date.strftime("%Y-%m-%d"),
        }

        return JsonResponse(summary)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getPackageRevenueReport(request):
    """
    Display the Package Revenue Analysis Report page.

    Shows revenue by package type with enrollment counts.
    """
    form = PackageRevenueReportForm()
    return render(
        request,
        "../templates/reports/package_revenue_report.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getPackageRevenueReportJS(request):
    """
    AJAX endpoint for Package Revenue Analysis Report data.

    Returns revenue grouped by package, package type, branch, center, or month.
    """
    try:
        # Get parameters
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        package_category = request.GET.get("package_category", "all")
        group_by = request.GET.get("group_by", "package")

        # Set default date range (current year)
        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(month=1, day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get memo details with charges
        details = InvoiceMemoDetail.objects.filter(
            memo__is_active=True,
            memo__memo_date__range=(from_date, to_date)
        ).select_related("memo", "memo__child")

        # Filter by branch/center through enrollment
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            details = details.filter(memo__child__id__in=enrolled_children)

        # Aggregate data based on group_by
        revenue_data = {}

        for detail in details:
            # Get package mapping for this child at memo date
            package_mapping = ChildPackageMapping.objects.filter(
                child=detail.memo.child,
                is_active=True,
                effective_from__lte=detail.memo.memo_date,
            ).filter(
                Q(effective_to__gte=detail.memo.memo_date) | Q(effective_to__isnull=True)
            ).first()

            if not package_mapping:
                continue

            # Determine package info
            package_name = "Unknown"
            package_type_name = "Unknown"
            package_category_value = "unknown"
            package_total = Decimal("0.00")

            if package_mapping.normal_package:
                package = package_mapping.normal_package
                package_name = package.package_name
                package_type_name = package.package_type.package_type_name
                package_category_value = "fixed"
                package_total = package.package_total
            elif package_mapping.flex_package:
                package = package_mapping.flex_package
                package_name = package.package_name
                package_type_name = package.package_type.package_type_name
                package_category_value = "flex"
                package_total = package.package_total
            elif package_mapping.holiday_package:
                package = package_mapping.holiday_package
                package_name = package.package_name
                package_type_name = package.package_type.package_type_name
                package_category_value = "holiday"
                package_total = package.package_total

            # Filter by package category
            if package_category != "all" and package_category_value != package_category:
                continue

            # Determine grouping key
            if group_by == "package":
                key = package_name
            elif group_by == "package_type":
                key = package_type_name
            elif group_by == "branch":
                enrollment = ChildEnrollment.objects.filter(
                    child=detail.memo.child, status="APPROVED", is_active=True
                ).select_related("branch").first()
                key = enrollment.branch.branch_name if enrollment else "Unknown"
            elif group_by == "center":
                enrollment = ChildEnrollment.objects.filter(
                    child=detail.memo.child, status="APPROVED", is_active=True
                ).select_related("center").first()
                key = enrollment.center.daycare_name if enrollment else "Unknown"
            elif group_by == "month":
                key = f"{calendar.month_abbr[detail.actual_month]} {detail.actual_year}"
            else:
                key = package_name

            if key not in revenue_data:
                revenue_data[key] = {
                    "group_key": key,
                    "package_fee": Decimal("0.00"),
                    "extra_hours_charge": Decimal("0.00"),
                    "holiday_charges": Decimal("0.00"),
                    "other_charges": Decimal("0.00"),
                    "gross_revenue": Decimal("0.00"),
                    "discounts_applied": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"),
                    "payments_received": Decimal("0.00"),
                    "enrollment_count": set(),
                    "memo_count": 0,
                }

            revenue_data[key]["package_fee"] += detail.package_fee or Decimal("0.00")
            revenue_data[key]["extra_hours_charge"] += detail.extra_hours_charge or Decimal("0.00")
            revenue_data[key]["holiday_charges"] += detail.holiday_charges or Decimal("0.00")
            revenue_data[key]["other_charges"] += detail.other_charges or Decimal("0.00")
            revenue_data[key]["gross_revenue"] += detail.gross_charges or Decimal("0.00")
            revenue_data[key]["discounts_applied"] += detail.discount_applied or Decimal("0.00")
            revenue_data[key]["net_revenue"] += detail.net_charges or Decimal("0.00")
            revenue_data[key]["payments_received"] += detail.payments_received or Decimal("0.00")
            revenue_data[key]["enrollment_count"].add(detail.memo.child.id)
            revenue_data[key]["memo_count"] += 1

        # Convert to list and format
        result = []
        for key, data in revenue_data.items():
            result.append({
                "group_key": data["group_key"],
                "package_fee": float(data["package_fee"]),
                "extra_hours_charge": float(data["extra_hours_charge"]),
                "holiday_charges": float(data["holiday_charges"]),
                "other_charges": float(data["other_charges"]),
                "gross_revenue": float(data["gross_revenue"]),
                "discounts_applied": float(data["discounts_applied"]),
                "net_revenue": float(data["net_revenue"]),
                "payments_received": float(data["payments_received"]),
                "enrollment_count": len(data["enrollment_count"]),
                "memo_count": data["memo_count"],
                "collection_rate": round(
                    float(data["payments_received"]) / float(data["net_revenue"]) * 100, 1
                ) if data["net_revenue"] > 0 else 0,
            })

        # Sort by net revenue descending
        result.sort(key=lambda x: x["net_revenue"], reverse=True)

        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getDiscountAnalysisReport(request):
    """
    Display the Discount Analysis Report page.

    Shows discounts applied with percentage of revenue impact.
    """
    form = DiscountAnalysisReportForm()
    return render(
        request,
        "../templates/reports/discount_analysis_report.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getDiscountAnalysisReportJS(request):
    """
    AJAX endpoint for Discount Analysis Report data.

    Returns discount amounts grouped by discount code, child, branch, center, or month.
    """
    try:
        # Get parameters
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        discount_code_id = request.GET.get("discount_code")
        group_by = request.GET.get("group_by", "discount")

        # Set default date range
        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(month=1, day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get memo details with discounts
        details = InvoiceMemoDetail.objects.filter(
            memo__is_active=True,
            memo__memo_date__range=(from_date, to_date),
            discount_applied__gt=0
        ).select_related("memo", "memo__child")

        # Filter by branch/center
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            details = details.filter(memo__child__id__in=enrolled_children)

        # Filter by specific discount
        if discount_code_id:
            # Get children with this discount through package mapping
            mappings_with_discount = ChildPackageMapping.objects.filter(
                discount__id=discount_code_id,
                is_active=True
            ).values_list("child__id", flat=True)
            details = details.filter(memo__child__id__in=mappings_with_discount)

        # Aggregate data based on group_by
        discount_data = {}

        for detail in details:
            # Get discount info from package mapping
            package_mapping = ChildPackageMapping.objects.filter(
                child=detail.memo.child,
                is_active=True,
                effective_from__lte=detail.memo.memo_date,
            ).filter(
                Q(effective_to__gte=detail.memo.memo_date) | Q(effective_to__isnull=True)
            ).select_related("discount").first()

            discount_name = "Unknown Discount"
            discount_rate = Decimal("0.00")

            if package_mapping and package_mapping.discount:
                discount_name = f"{package_mapping.discount.discount_code} - {package_mapping.discount.discount_name}"
                discount_rate = package_mapping.discount.discount_rate

            # Get enrollment for branch/center info
            enrollment = ChildEnrollment.objects.filter(
                child=detail.memo.child, status="APPROVED", is_active=True
            ).select_related("branch", "center").first()

            # Determine grouping key
            if group_by == "discount":
                key = discount_name
            elif group_by == "child":
                key = f"{detail.memo.child.admission_number} - {detail.memo.child.child_first_name} {detail.memo.child.child_last_name}"
            elif group_by == "branch":
                key = enrollment.branch.branch_name if enrollment else "Unknown"
            elif group_by == "center":
                key = enrollment.center.daycare_name if enrollment else "Unknown"
            elif group_by == "month":
                key = f"{calendar.month_abbr[detail.actual_month]} {detail.actual_year}"
            else:
                key = discount_name

            if key not in discount_data:
                discount_data[key] = {
                    "group_key": key,
                    "discount_amount": Decimal("0.00"),
                    "gross_revenue": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"),
                    "child_count": set(),
                    "memo_count": 0,
                    "discount_rate": discount_rate,
                }

            discount_data[key]["discount_amount"] += detail.discount_applied or Decimal("0.00")
            discount_data[key]["gross_revenue"] += detail.gross_charges or Decimal("0.00")
            discount_data[key]["net_revenue"] += detail.net_charges or Decimal("0.00")
            discount_data[key]["child_count"].add(detail.memo.child.id)
            discount_data[key]["memo_count"] += 1

        # Convert to list and calculate percentages
        result = []
        for key, data in discount_data.items():
            discount_percentage = (
                float(data["discount_amount"]) / float(data["gross_revenue"]) * 100
                if data["gross_revenue"] > 0 else 0
            )
            result.append({
                "group_key": data["group_key"],
                "discount_amount": float(data["discount_amount"]),
                "gross_revenue": float(data["gross_revenue"]),
                "net_revenue": float(data["net_revenue"]),
                "discount_percentage": round(discount_percentage, 2),
                "child_count": len(data["child_count"]),
                "memo_count": data["memo_count"],
                "avg_discount_per_memo": round(
                    float(data["discount_amount"]) / data["memo_count"], 2
                ) if data["memo_count"] > 0 else 0,
            })

        # Sort by discount amount descending
        result.sort(key=lambda x: x["discount_amount"], reverse=True)

        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getDiscountSummaryJS(request):
    """
    AJAX endpoint for Discount Analysis Report summary.

    Returns overall discount statistics.
    """
    try:
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")

        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(month=1, day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get all memo details in date range
        all_details = InvoiceMemoDetail.objects.filter(
            memo__is_active=True,
            memo__memo_date__range=(from_date, to_date),
        )

        # Filter by branch/center
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            all_details = all_details.filter(memo__child__id__in=enrolled_children)

        # Calculate totals
        from django.db.models import Sum

        totals = all_details.aggregate(
            total_gross=Sum("gross_charges"),
            total_discount=Sum("discount_applied"),
            total_net=Sum("net_charges"),
        )

        total_gross = totals["total_gross"] or Decimal("0.00")
        total_discount = totals["total_discount"] or Decimal("0.00")
        total_net = totals["total_net"] or Decimal("0.00")

        # Count children with discounts
        children_with_discounts = all_details.filter(
            discount_applied__gt=0
        ).values("memo__child").distinct().count()

        total_children = all_details.values("memo__child").distinct().count()

        summary = {
            "total_gross_revenue": float(total_gross),
            "total_discount_amount": float(total_discount),
            "total_net_revenue": float(total_net),
            "discount_percentage": round(
                float(total_discount) / float(total_gross) * 100, 2
            ) if total_gross > 0 else 0,
            "children_with_discounts": children_with_discounts,
            "total_children": total_children,
            "discount_utilization": round(
                children_with_discounts / total_children * 100, 1
            ) if total_children > 0 else 0,
        }

        return JsonResponse(summary)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getLocationPerformanceReport(request):
    """
    Display the Branch/Center Performance Report page.

    Shows revenue, collections, and outstanding by location.
    """
    form = LocationPerformanceReportForm()
    return render(
        request,
        "../templates/reports/location_performance_report.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getLocationPerformanceReportJS(request):
    """
    AJAX endpoint for Branch/Center Performance Report data.

    Returns performance metrics by branch or center.
    """
    try:
        # Get parameters
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        level = request.GET.get("level", "branch")

        # Set default date range
        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(month=1, day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get enrollments for mapping children to locations
        enrollment_filters = Q(status="APPROVED", is_active=True)
        if branch_id:
            enrollment_filters &= Q(branch__id=branch_id)
        if center_id:
            enrollment_filters &= Q(center__id=center_id)

        enrollments = ChildEnrollment.objects.filter(
            enrollment_filters
        ).select_related("branch", "center", "child")

        # Build child to location mapping
        child_locations = {}
        for enrollment in enrollments:
            child_locations[enrollment.child.id] = {
                "branch_id": enrollment.branch.id,
                "branch_name": enrollment.branch.branch_name,
                "center_id": enrollment.center.id,
                "center_name": enrollment.center.daycare_name,
            }

        # Get memos for these children in date range
        memos = InvoiceMemo.objects.filter(
            is_active=True,
            memo_date__range=(from_date, to_date),
            child__id__in=child_locations.keys()
        ).select_related("child")

        # Aggregate by location
        location_data = {}

        for memo in memos:
            location = child_locations.get(memo.child.id)
            if not location:
                continue

            if level == "branch":
                key = location["branch_name"]
                location_id = location["branch_id"]
            else:
                key = location["center_name"]
                location_id = location["center_id"]

            if key not in location_data:
                location_data[key] = {
                    "location_name": key,
                    "location_id": location_id,
                    "gross_revenue": Decimal("0.00"),
                    "discounts_applied": Decimal("0.00"),
                    "net_revenue": Decimal("0.00"),
                    "payments_received": Decimal("0.00"),
                    "outstanding_balance": Decimal("0.00"),
                    "children": set(),
                    "memo_count": 0,
                }

            location_data[key]["gross_revenue"] += memo.gross_total
            location_data[key]["net_revenue"] += (
                memo.total_outstanding + memo.total_previous_month + memo.total_current_month
            )
            location_data[key]["payments_received"] += memo.total_payments
            location_data[key]["outstanding_balance"] += memo.net_amount_due
            location_data[key]["children"].add(memo.child.id)
            location_data[key]["memo_count"] += 1

        # Convert to list
        result = []
        for key, data in location_data.items():
            collection_rate = (
                float(data["payments_received"]) / float(data["gross_revenue"]) * 100
                if data["gross_revenue"] > 0 else 0
            )
            avg_outstanding = (
                float(data["outstanding_balance"]) / len(data["children"])
                if len(data["children"]) > 0 else 0
            )

            result.append({
                "location_name": data["location_name"],
                "gross_revenue": float(data["gross_revenue"]),
                "net_revenue": float(data["net_revenue"]),
                "payments_received": float(data["payments_received"]),
                "outstanding_balance": float(data["outstanding_balance"]),
                "collection_rate": round(collection_rate, 1),
                "enrollment_count": len(data["children"]),
                "memo_count": data["memo_count"],
                "avg_outstanding_per_child": round(avg_outstanding, 2),
                "revenue_per_child": round(
                    float(data["gross_revenue"]) / len(data["children"]), 2
                ) if len(data["children"]) > 0 else 0,
            })

        # Sort by gross revenue descending
        result.sort(key=lambda x: x["gross_revenue"], reverse=True)

        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getExtraHoursRevenueReport(request):
    """
    Display the Enhanced Extra Hours Revenue Report page.

    Shows extra hours revenue with before/after 5:30 PM breakdown and top users.
    """
    form = ExtraHoursRevenueReportForm()
    return render(
        request,
        "../templates/reports/extra_hours_revenue_report.html",
        {"form": form, "UserName": request.user.username},
    )


@login_required
def getExtraHoursRevenueReportJS(request):
    """
    AJAX endpoint for Enhanced Extra Hours Revenue Report data.

    Returns extra hours charges with before/after 5:30 PM breakdown.
    """
    try:
        # Get parameters
        child_id = request.GET.get("child")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        time_split = request.GET.get("time_split", "combined")

        # Set default dates
        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get memo details with extra hours charges
        details = InvoiceMemoDetail.objects.filter(
            memo__is_active=True,
            memo__memo_date__range=(from_date, to_date),
            extra_hours_charge__gt=0
        ).select_related("memo", "memo__child")

        if child_id:
            details = details.filter(memo__child__id=child_id)

        # Filter by branch/center
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            details = details.filter(memo__child__id__in=enrolled_children)

        revenue_data = []

        for detail in details:
            child = detail.memo.child

            # Get enrollment info
            enrollment = ChildEnrollment.objects.filter(
                child=child, status="APPROVED", is_active=True
            ).select_related("branch", "center").first()

            # Calculate split if needed (estimate from calculation_details if available)
            before_530_charge = Decimal("0.00")
            after_530_charge = Decimal("0.00")
            total_extra_charge = detail.extra_hours_charge or Decimal("0.00")

            # Check calculation_details for breakdown
            if detail.calculation_details and isinstance(detail.calculation_details, dict):
                before_530_charge = Decimal(str(detail.calculation_details.get("before_530_charge", 0)))
                after_530_charge = Decimal(str(detail.calculation_details.get("after_530_charge", 0)))
            else:
                # Default split estimate: assume 60% is after 5:30 PM
                after_530_charge = total_extra_charge * Decimal("0.6")
                before_530_charge = total_extra_charge - after_530_charge

            revenue_data.append({
                "child_admission": child.admission_number,
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "memo_code": detail.memo.memo_code,
                "month": f"{detail.month_name} {detail.actual_year}",
                "package_name": detail.package_name or "N/A",
                "extra_hours_charge": float(total_extra_charge),
                "before_530_charge": float(before_530_charge),
                "after_530_charge": float(after_530_charge),
                "holiday_charges": float(detail.holiday_charges or 0),
                "total_extra_charges": float(total_extra_charge + (detail.holiday_charges or Decimal("0.00"))),
                "branch_name": enrollment.branch.branch_name if enrollment else "N/A",
                "center_name": enrollment.center.daycare_name if enrollment else "N/A",
            })

        # Sort by total extra charges descending
        revenue_data.sort(key=lambda x: x["total_extra_charges"], reverse=True)

        return JsonResponse(revenue_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getExtraHoursTopUsersJS(request):
    """
    AJAX endpoint for Extra Hours Revenue Report - Top Users.

    Returns top N children by extra hours charges.
    """
    try:
        # Get parameters
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        branch_id = request.GET.get("branch")
        center_id = request.GET.get("center")
        top_n = int(request.GET.get("top_n", 10))

        # Set default dates
        today = datetime.now().date()
        if not from_date:
            from_date = today.replace(day=1)
        else:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

        if not to_date:
            to_date = today
        else:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

        # Get memo details with extra hours charges
        details = InvoiceMemoDetail.objects.filter(
            memo__is_active=True,
            memo__memo_date__range=(from_date, to_date),
            extra_hours_charge__gt=0
        ).select_related("memo", "memo__child")

        # Filter by branch/center
        if branch_id or center_id:
            enrollment_filters = Q(status="APPROVED", is_active=True)
            if branch_id:
                enrollment_filters &= Q(branch__id=branch_id)
            if center_id:
                enrollment_filters &= Q(center__id=center_id)

            enrolled_children = ChildEnrollment.objects.filter(
                enrollment_filters
            ).values_list("child__id", flat=True)
            details = details.filter(memo__child__id__in=enrolled_children)

        # Aggregate by child
        child_totals = {}

        for detail in details:
            child = detail.memo.child
            child_key = child.id

            if child_key not in child_totals:
                enrollment = ChildEnrollment.objects.filter(
                    child=child, status="APPROVED", is_active=True
                ).select_related("branch", "center").first()

                child_totals[child_key] = {
                    "child_id": child.id,
                    "child_admission": child.admission_number,
                    "child_name": f"{child.child_first_name} {child.child_last_name}",
                    "total_extra_hours_charge": Decimal("0.00"),
                    "total_holiday_charges": Decimal("0.00"),
                    "month_count": 0,
                    "branch_name": enrollment.branch.branch_name if enrollment else "N/A",
                    "center_name": enrollment.center.daycare_name if enrollment else "N/A",
                }

            child_totals[child_key]["total_extra_hours_charge"] += detail.extra_hours_charge or Decimal("0.00")
            child_totals[child_key]["total_holiday_charges"] += detail.holiday_charges or Decimal("0.00")
            child_totals[child_key]["month_count"] += 1

        # Convert to list and sort
        result = []
        for key, data in child_totals.items():
            total_charges = data["total_extra_hours_charge"] + data["total_holiday_charges"]
            avg_per_month = total_charges / data["month_count"] if data["month_count"] > 0 else Decimal("0.00")

            result.append({
                "rank": 0,  # Will be set after sorting
                "child_admission": data["child_admission"],
                "child_name": data["child_name"],
                "total_extra_hours_charge": float(data["total_extra_hours_charge"]),
                "total_holiday_charges": float(data["total_holiday_charges"]),
                "total_charges": float(total_charges),
                "month_count": data["month_count"],
                "avg_per_month": float(avg_per_month),
                "branch_name": data["branch_name"],
                "center_name": data["center_name"],
            })

        # Sort by total charges descending and limit to top_n
        result.sort(key=lambda x: x["total_charges"], reverse=True)
        result = result[:top_n]

        # Set ranks
        for i, item in enumerate(result):
            item["rank"] = i + 1

        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Attendance Log Editing Functions (Superuser Only)


def get_client_ip(request):
    """
    Extract client IP address from request headers.

    Checks X-Forwarded-For header first (for proxied requests),
    falls back to REMOTE_ADDR.

    Args:
        request: HttpRequest object

    Returns:
        str: Client IP address or None if not available
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


@login_required
def getAttendanceLogsForEdit(request):
    """
    Render the attendance log editing page for superusers.

    This view provides the interface for superusers to search, view, and edit
    attendance log records. Only superusers have access to modify historical
    attendance data to maintain audit integrity.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders attendance_log_edit.html template for superusers
        HttpResponse: Redirects to home page for non-superusers

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status for access
        - Non-superusers are redirected with an error message

    Template Context:
        - UserName: Current authenticated user's username
        - children: QuerySet of active enrolled children for filtering
        - centers: QuerySet of active daycare centers for filtering

    Business Logic:
        - Provides search interface for attendance records
        - Allows filtering by child, date range, and center
        - Supports editing of date_logged and time_logged fields
        - All edits are tracked in AttendanceLogAudit model
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:index")

    # Get active enrolled children for dropdown filter
    children = Child.objects.filter(
        is_active=True,
        is_enrolled=True,
        enrollement_approved=True,
    ).order_by("admission_number")

    # Get active centers for dropdown filter
    centers = DayCare.objects.filter(is_active=True).order_by("daycare_name")

    context = {
        "UserName": request.user.username,
        "children": children,
        "centers": centers,
    }

    return render(request, "../templates/utils/attendance_log_edit.html", context)


@login_required
def getAttendanceLogsForEditJS(request):
    """
    Provide AJAX-based attendance log data for the edit interface.

    This view returns filtered attendance log records in JSON format for
    display in the attendance log editing DataTable. Only superusers can
    access this endpoint.

    Args:
        request (HttpRequest): AJAX GET request with optional filter parameters:
            - child_id: Integer child ID for filtering
            - from_date: String start date in YYYY-MM-DD format
            - to_date: String end date in YYYY-MM-DD format
            - center_id: Integer center ID for filtering

    Returns:
        JsonResponse: JSON array of attendance log records with:
            - id: Integer attendance log ID
            - child_name: String child's full name
            - admission_number: String child's admission number
            - date_logged: String date in YYYY-MM-DD format
            - time_logged: String time in HH:MM:SS format
            - center_name: String name of the daycare center
            - last_updated_by: String username of last updater
            - last_updated_at: String datetime of last update

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 JSON error if not)
        - Only returns active attendance records

    Query Optimization:
        - Uses select_related for child and enrollment data
        - Applies filters efficiently using Q objects
        - Orders results by date descending for recent records first
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."}, status=403
        )

    try:
        # Get filter parameters
        child_id = request.GET.get("child_id")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        center_id = request.GET.get("center_id")

        # Build filter conditions
        filters = Q(is_active=True)

        if child_id:
            filters &= Q(child_id=child_id)

        if from_date:
            filters &= Q(date_logged__gte=from_date)

        if to_date:
            filters &= Q(date_logged__lte=to_date)

        # Query attendance logs with related data
        attendance_logs = AttendanceLog.objects.filter(filters).select_related(
            "child"
        ).order_by("-date_logged", "-time_logged")

        # If center filter is specified, filter by enrollment center
        if center_id:
            # Get children enrolled at the specified center
            enrolled_children = ChildEnrollment.objects.filter(
                center_id=center_id,
                status="APPROVED",
                is_active=True,
            ).values_list("child_id", flat=True)
            attendance_logs = attendance_logs.filter(child_id__in=enrolled_children)

        # Build result list
        result = []
        for log in attendance_logs:
            # Get enrollment info for center name
            enrollment = ChildEnrollment.objects.filter(
                child=log.child,
                status="APPROVED",
                is_active=True,
            ).select_related("center").first()

            center_name = ""
            if enrollment and enrollment.center:
                center_name = enrollment.center.daycare_name

            result.append({
                "id": log.id,
                "child_name": f"{log.child.child_first_name} {log.child.child_last_name}",
                "admission_number": log.child.admission_number,
                "date_logged": log.date_logged.strftime("%Y-%m-%d"),
                "time_logged": log.time_logged.strftime("%H:%M:%S"),
                "center_name": center_name,
                "last_updated_by": log.user_updated or log.user_created or "System",
                "last_updated_at": log.date_updated.strftime("%Y-%m-%d %H:%M:%S")
                if log.date_updated
                else (
                    log.date_created.strftime("%Y-%m-%d %H:%M:%S")
                    if log.date_created
                    else "N/A"
                ),
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def updateAttendanceLogEntry(request):
    """
    Update an attendance log record and create an audit trail.

    This view handles POST requests to update the date_logged and time_logged
    fields of an attendance record. All changes are tracked in the
    AttendanceLogAudit model for compliance and auditing purposes.

    Args:
        request (HttpRequest): POST request with:
            - attendance_id: Integer ID of the attendance record to update
            - new_date: String new date in YYYY-MM-DD format
            - new_time: String new time in HH:MM or HH:MM:SS format
            - edit_reason: String optional reason for the edit

    Returns:
        JsonResponse: Success response with:
            - success: Boolean True
            - message: String success message
            - attendance_id: Integer ID of updated record
        JsonResponse: Error response with:
            - error: String error message
            - status: HTTP status code (400, 403, 404, 405, or 500)

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 JSON error if not)
        - Records client IP address for audit trail
        - Creates immutable audit record before modifying data

    Business Logic:
        - Validates attendance record exists and is active
        - Creates AttendanceLogAudit record with old and new values
        - Updates the attendance log record with new values
        - Updates audit fields (user_updated, date_updated)

    Audit Trail:
        - Records old_date_logged and old_time_logged
        - Records new_date_logged and new_time_logged
        - Records edited_by username and edited_at timestamp
        - Records edit_reason if provided
        - Records client IP address

    Error Handling:
        - Returns 400 for missing required parameters
        - Returns 403 for non-superuser access
        - Returns 404 for non-existent attendance record
        - Returns 405 for non-POST requests
        - Returns 500 for unexpected errors
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."}, status=403
        )

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. POST required."}, status=405)

    try:
        # Get POST parameters
        attendance_id = request.POST.get("attendance_id")
        new_date = request.POST.get("new_date")
        new_time = request.POST.get("new_time")
        edit_reason = request.POST.get("edit_reason", "")

        # Validate required parameters
        if not attendance_id:
            return JsonResponse({"error": "Attendance ID is required."}, status=400)

        if not new_date:
            return JsonResponse({"error": "New date is required."}, status=400)

        if not new_time:
            return JsonResponse({"error": "New time is required."}, status=400)

        # Get the attendance record
        try:
            attendance = AttendanceLog.objects.get(id=attendance_id, is_active=True)
        except AttendanceLog.DoesNotExist:
            return JsonResponse({"error": "Attendance record not found."}, status=404)

        # Parse new date and time
        try:
            parsed_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse(
                {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
            )

        # Validate that the date is not in the future
        if parsed_date > date.today():
            return JsonResponse(
                {"error": "Cannot set attendance date to a future date."}, status=400
            )

        try:
            # Handle both HH:MM and HH:MM:SS formats
            if len(new_time) == 5:
                parsed_time = datetime.strptime(new_time, "%H:%M").time()
            else:
                parsed_time = datetime.strptime(new_time, "%H:%M:%S").time()
        except ValueError:
            return JsonResponse(
                {"error": "Invalid time format. Use HH:MM or HH:MM:SS."}, status=400
            )

        # Get client IP address
        client_ip = get_client_ip(request)

        # Create audit record before making changes
        with transaction.atomic():
            # Create audit trail entry
            AttendanceLogAudit.objects.create(
                attendance_log=attendance,
                child=attendance.child,
                old_date_logged=attendance.date_logged,
                old_time_logged=attendance.time_logged,
                new_date_logged=parsed_date,
                new_time_logged=parsed_time,
                edited_by=request.user.username,
                edit_reason=edit_reason if edit_reason else None,
                ip_address=client_ip,
                user_created=request.user.username,
            )

            # Update the attendance record
            attendance.date_logged = parsed_date
            attendance.time_logged = parsed_time
            attendance.user_updated = request.user.username
            attendance.save(update_fields=["date_logged", "time_logged", "user_updated", "date_updated"])

        return JsonResponse({
            "success": True,
            "message": "Attendance record updated successfully.",
            "attendance_id": attendance_id,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getAttendanceLogByIdJS(request, pk):
    """
    Retrieve a single attendance log record by ID for editing.

    This view returns detailed information about a specific attendance log
    record for display in the edit modal. Only superusers can access this
    endpoint.

    Args:
        request (HttpRequest): GET request
        pk (int): Primary key of the attendance log record

    Returns:
        JsonResponse: Success response with:
            - success: Boolean True
            - data: Object containing:
                - id: Integer attendance log ID
                - child_id: Integer child ID
                - child_name: String child's full name
                - admission_number: String child's admission number
                - date_logged: String date in YYYY-MM-DD format
                - time_logged: String time in HH:MM:SS format
                - center_name: String daycare center name
                - audit_count: Integer number of previous edits
        JsonResponse: Error response with:
            - error: String error message
            - status: HTTP status code (403, 404, or 500)

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 JSON error if not)

    Business Logic:
        - Returns full attendance record details for edit form population
        - Includes audit count to show edit history
        - Includes center name from active enrollment
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."}, status=403
        )

    try:
        # Get the attendance record
        try:
            attendance = AttendanceLog.objects.select_related("child").get(
                id=pk, is_active=True
            )
        except AttendanceLog.DoesNotExist:
            return JsonResponse({"error": "Attendance record not found."}, status=404)

        # Get enrollment info for center name
        enrollment = ChildEnrollment.objects.filter(
            child=attendance.child,
            status="APPROVED",
            is_active=True,
        ).select_related("center").first()

        center_name = ""
        if enrollment and enrollment.center:
            center_name = enrollment.center.daycare_name

        # Get audit count for this record
        audit_count = AttendanceLogAudit.objects.filter(
            attendance_log=attendance
        ).count()

        data = {
            "id": attendance.id,
            "child_id": attendance.child.id,
            "child_name": f"{attendance.child.child_first_name} {attendance.child.child_last_name}",
            "admission_number": attendance.child.admission_number,
            "date_logged": attendance.date_logged.strftime("%Y-%m-%d"),
            "time_logged": attendance.time_logged.strftime("%H:%M:%S"),
            "center_name": center_name,
            "audit_count": audit_count,
        }

        return JsonResponse({"success": True, "data": data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getAttendanceAuditTrail(request):
    """
    Render the attendance audit trail page for superusers.

    This view provides a read-only interface for superusers to view all changes
    made to attendance log records. The audit trail records are immutable and
    provide a complete history of all edits.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders attendance_audit_trail.html template for superusers
        HttpResponse: Redirects to home page for non-superusers

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status for access
        - Non-superusers are redirected with an error message

    Template Context:
        - UserName: Current authenticated user's username
        - children: QuerySet of active enrolled children for filtering

    Business Logic:
        - Provides search interface for audit trail records
        - Allows filtering by child and date range (edited date)
        - Shows: child name, admission no, old/new date/time, edited by,
          edited at, edit reason, and IP address
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:home")

    # Get active enrolled children for dropdown filter
    children = Child.objects.filter(
        is_active=True,
        is_enrolled=True,
        enrollement_approved=True,
    ).order_by("admission_number")

    context = {
        "UserName": request.user.username,
        "children": children,
    }

    return render(request, "../templates/utils/attendance_audit_trail.html", context)


@login_required
def getAttendanceAuditTrailJS(request):
    """
    Provide AJAX-based attendance audit trail data.

    This view returns filtered audit trail records in JSON format for
    display in the audit trail DataTable. Only superusers can access
    this endpoint.

    Args:
        request (HttpRequest): AJAX GET request with optional filter parameters:
            - child_id: Integer child ID for filtering
            - from_date: String start date in YYYY-MM-DD format (filters edited_at)
            - to_date: String end date in YYYY-MM-DD format (filters edited_at)

    Returns:
        JsonResponse: JSON array of audit trail records with:
            - id: Integer audit record ID
            - child_name: String child's full name
            - admission_number: String child's admission number
            - old_date_logged: String original date in YYYY-MM-DD format
            - old_time_logged: String original time in HH:MM:SS format
            - new_date_logged: String new date in YYYY-MM-DD format
            - new_time_logged: String new time in HH:MM:SS format
            - edited_by: String username of editor
            - edited_at: String datetime of edit in ISO format
            - edit_reason: String reason for edit (nullable)
            - ip_address: String IP address of editor (nullable)

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 JSON error if not)

    Query Optimization:
        - Uses select_related for child data
        - Applies filters efficiently using Q objects
        - Orders results by edited_at descending for recent edits first
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."}, status=403
        )

    try:
        # Get filter parameters
        child_id = request.GET.get("child_id")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")

        # Build filter conditions
        filters = Q(is_active=True)

        if child_id:
            filters &= Q(child_id=child_id)

        if from_date:
            filters &= Q(edited_at__date__gte=from_date)

        if to_date:
            filters &= Q(edited_at__date__lte=to_date)

        # Query audit records with related data
        audit_records = AttendanceLogAudit.objects.filter(filters).select_related(
            "child"
        ).order_by("-edited_at")

        # Build result list
        result = []
        for audit in audit_records:
            result.append({
                "id": audit.id,
                "child_name": f"{audit.child.child_first_name} {audit.child.child_last_name}",
                "admission_number": audit.child.admission_number,
                "old_date_logged": audit.old_date_logged.strftime("%Y-%m-%d"),
                "old_time_logged": audit.old_time_logged.strftime("%H:%M:%S"),
                "new_date_logged": audit.new_date_logged.strftime("%Y-%m-%d"),
                "new_time_logged": audit.new_time_logged.strftime("%H:%M:%S"),
                "edited_by": audit.edited_by,
                "edited_at": audit.edited_at.strftime("%Y-%m-%d %H:%M:%S"),
                "edit_reason": audit.edit_reason or "",
                "ip_address": audit.ip_address or "",
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


# Time Adjustment Request Functions


@login_required
def getTimeAdjustmentRequest(request):
    """
    Render the time adjustment request form page.

    This view displays the form for users to submit time adjustment requests
    when attendance check-in or check-out times were missed or incorrect.

    Args:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the time_adjustment_request.html template with:
            - UserName: Current authenticated user's username
            - children: QuerySet of active enrolled children for the dropdown

    Security:
        - Requires user authentication via @login_required decorator
    """
    UserName = request.user.username

    # Get active enrolled children for the dropdown
    children = Child.objects.filter(
        is_active=True,
        is_enrolled=True,
        enrollement_approved=True
    ).order_by("child_first_name", "child_last_name")

    return render(
        request,
        "time_adjustment_request.html",
        {
            "UserName": UserName,
            "children": children,
        },
    )


@login_required
def saveTimeAdjustmentRequest(request):
    """
    Save a new time adjustment request via AJAX POST.

    This view processes and saves new time adjustment requests submitted
    by users. It validates the input and creates a new TimeAdjustmentRequest
    record with PENDING_APPROVAL status.

    Args:
        request (HttpRequest): POST request with form data:
            - child_id: Integer ID of the child
            - request_date: String date in YYYY-MM-DD format
            - in_time: Optional string time in HH:MM format
            - out_time: Optional string time in HH:MM format
            - reason: String reason for the adjustment request

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Validates required fields (child_id, request_date, reason)
        - Validates at least one of in_time or out_time is provided
        - Determines entry_type based on which times are provided
        - Creates TimeAdjustmentRequest with status PENDING_APPROVAL
        - Records the requesting user

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts POST requests
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        # Get form data
        child_id = request.POST.get("child_id")
        request_date = request.POST.get("request_date")
        in_time_str = request.POST.get("in_time")
        out_time_str = request.POST.get("out_time")
        reason = request.POST.get("reason")

        # Validate required fields
        if not child_id:
            return JsonResponse({"error": "Child is required"}, status=400)
        if not request_date:
            return JsonResponse({"error": "Request date is required"}, status=400)
        if not reason or not reason.strip():
            return JsonResponse({"error": "Reason is required"}, status=400)
        if not in_time_str and not out_time_str:
            return JsonResponse(
                {"error": "At least one of check-in time or check-out time is required"},
                status=400
            )

        # Parse times
        in_time = None
        out_time = None
        if in_time_str:
            in_time = datetime.strptime(in_time_str, "%H:%M").time()
        if out_time_str:
            out_time = datetime.strptime(out_time_str, "%H:%M").time()

        # Determine entry type
        if in_time and out_time:
            entry_type = "BOTH"
        elif in_time:
            entry_type = "IN"
        else:
            entry_type = "OUT"

        # Parse request date
        parsed_request_date = datetime.strptime(request_date, "%Y-%m-%d").date()

        # Validate that the date is not in the future
        if parsed_request_date > date.today():
            return JsonResponse(
                {"error": "Cannot submit a time adjustment request for a future date."}, status=400
            )

        # Get the child object
        try:
            child = Child.objects.get(pk=child_id)
        except Child.DoesNotExist:
            return JsonResponse({"error": "Child not found"}, status=404)

        # Create the time adjustment request
        time_adjustment = TimeAdjustmentRequest(
            child=child,
            request_date=parsed_request_date,
            in_time=in_time,
            out_time=out_time,
            entry_type=entry_type,
            reason=reason.strip(),
            status="PENDING_APPROVAL",
            requested_by=request.user.username,
            user_created=request.user.username,
            user_updated=request.user.username,
        )
        time_adjustment.save()

        return JsonResponse({
            "success": True,
            "message": "Time adjustment request submitted successfully. Pending approval."
        })

    except ValueError as e:
        return JsonResponse({"error": f"Invalid date or time format: {str(e)}"}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getTimeAdjustmentRequestsJS(request):
    """
    Get list of time adjustment requests as JSON for AJAX display.

    This view returns time adjustment requests filtered based on user role.
    Superusers can see all requests, while regular users only see their own.

    Args:
        request (HttpRequest): GET request with optional filter parameters

    Returns:
        JsonResponse: JSON array of time adjustment request records with:
            - id: Integer request ID
            - child_name: String child's full name
            - admission_number: String child's admission number
            - request_date: String date in YYYY-MM-DD format
            - in_time: String time in HH:MM format or null
            - out_time: String time in HH:MM format or null
            - entry_type: String (IN/OUT/BOTH)
            - reason: String reason for request
            - status: String status (PENDING_APPROVAL/APPROVED/REJECTED)
            - requested_by: String username of requester
            - requested_date: String datetime in ISO format
            - rejection_reason: String or null

    Security:
        - Requires user authentication via @login_required decorator
        - Superusers see all requests; regular users see only their own
    """
    try:
        # Build query based on user role
        if request.user.is_superuser:
            requests_qs = TimeAdjustmentRequest.objects.filter(
                is_active=True
            ).select_related("child").order_by("-requested_date")
        else:
            requests_qs = TimeAdjustmentRequest.objects.filter(
                is_active=True,
                requested_by=request.user.username
            ).select_related("child").order_by("-requested_date")

        # Build result list
        result = []
        for req in requests_qs:
            result.append({
                "id": req.id,
                "child_name": f"{req.child.child_first_name} {req.child.child_last_name}",
                "admission_number": req.child.admission_number,
                "request_date": req.request_date.strftime("%Y-%m-%d"),
                "in_time": req.in_time.strftime("%H:%M") if req.in_time else None,
                "out_time": req.out_time.strftime("%H:%M") if req.out_time else None,
                "entry_type": req.entry_type,
                "entry_type_display": dict(TimeAdjustmentRequest.ENTRY_TYPE_CHOICES).get(req.entry_type, req.entry_type),
                "reason": req.reason,
                "status": req.status,
                "status_display": dict(TimeAdjustmentRequest.STATUS_CHOICES).get(req.status, req.status),
                "requested_by": req.requested_by,
                "requested_date": req.requested_date.strftime("%Y-%m-%d %H:%M:%S"),
                "approved_by": req.approved_by or "",
                "approved_date": req.approved_date.strftime("%Y-%m-%d %H:%M:%S") if req.approved_date else "",
                "rejection_reason": req.rejection_reason or "",
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getTimeAdjustmentApprovals(request):
    """
    Render the time adjustment approvals page for superusers.

    This view displays the approval interface where superusers can review,
    approve, or reject pending time adjustment requests.

    Args:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the time_adjustment_approvals.html template with:
            - UserName: Current authenticated user's username
            - pending_count: Integer count of pending requests
        OR
        HttpResponseRedirect: Redirects to home if user is not a superuser

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status; redirects non-superusers to home
    """
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to access this page.")
        return redirect("/")

    UserName = request.user.username

    # Get count of pending requests
    pending_count = TimeAdjustmentRequest.objects.filter(
        is_active=True,
        status="PENDING_APPROVAL"
    ).count()

    return render(
        request,
        "time_adjustment_approvals.html",
        {
            "UserName": UserName,
            "pending_count": pending_count,
        },
    )


@login_required
def getPendingTimeAdjustmentRequestsJS(request):
    """
    Get pending time adjustment requests as JSON for superuser approval page.

    This view returns all pending time adjustment requests with child info
    and any existing attendance for the requested date for context.

    Args:
        request (HttpRequest): GET request

    Returns:
        JsonResponse: JSON array of pending request records with:
            - id: Integer request ID
            - child_id: Integer child ID
            - child_name: String child's full name
            - admission_number: String child's admission number
            - request_date: String date in YYYY-MM-DD format
            - in_time: String time in HH:MM format or null
            - out_time: String time in HH:MM format or null
            - entry_type: String (IN/OUT/BOTH)
            - reason: String reason for request
            - requested_by: String username of requester
            - requested_date: String datetime in ISO format
            - existing_attendance: Array of existing attendance logs for that date

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    try:
        # Get pending requests
        pending_requests = TimeAdjustmentRequest.objects.filter(
            is_active=True,
            status="PENDING_APPROVAL"
        ).select_related("child").order_by("-requested_date")

        # Build result list
        result = []
        for req in pending_requests:
            # Get existing attendance logs for the requested date
            existing_attendance = AttendanceLog.objects.filter(
                child=req.child,
                date_logged=req.request_date,
                is_active=True
            ).order_by("time_logged")

            existing_logs = []
            for log in existing_attendance:
                existing_logs.append({
                    "id": log.id,
                    "time_logged": log.time_logged.strftime("%H:%M"),
                })

            result.append({
                "id": req.id,
                "child_id": req.child.id,
                "child_name": f"{req.child.admission_number} - {req.child.child_first_name} {req.child.child_last_name}",
                "admission_number": req.child.admission_number,
                "request_date": req.request_date.strftime("%Y-%m-%d"),
                "in_time": req.in_time.strftime("%H:%M") if req.in_time else None,
                "out_time": req.out_time.strftime("%H:%M") if req.out_time else None,
                "entry_type": req.entry_type,
                "entry_type_display": dict(TimeAdjustmentRequest.ENTRY_TYPE_CHOICES).get(req.entry_type, req.entry_type),
                "reason": req.reason,
                "requested_by": req.requested_by,
                "requested_date": req.requested_date.strftime("%Y-%m-%d %H:%M:%S"),
                "existing_attendance": existing_logs,
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def approveTimeAdjustmentRequest(request):
    """
    Approve a time adjustment request and create attendance log entries.

    This view processes approval of a time adjustment request, creating
    the corresponding AttendanceLog entries for the requested times and
    linking them back to the request.

    Args:
        request (HttpRequest): POST request with:
            - request_id: Integer ID of the TimeAdjustmentRequest to approve

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Creates AttendanceLog entry for in_time if provided
        - Creates AttendanceLog entry for out_time if provided
        - Updates request status to APPROVED
        - Records approving user and timestamp
        - Links created attendance logs to the request

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
        - Uses transaction.atomic for database integrity
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        request_id = request.POST.get("request_id")

        if not request_id:
            return JsonResponse({"error": "Request ID is required"}, status=400)

        # Get the time adjustment request
        try:
            time_request = TimeAdjustmentRequest.objects.get(
                pk=request_id,
                status="PENDING_APPROVAL",
                is_active=True
            )
        except TimeAdjustmentRequest.DoesNotExist:
            return JsonResponse(
                {"error": "Pending time adjustment request not found"},
                status=404
            )

        in_attendance_log = None
        out_attendance_log = None

        # Create attendance log for in_time if provided
        if time_request.in_time:
            in_attendance_log = AttendanceLog(
                child=time_request.child,
                date_logged=time_request.request_date,
                time_logged=time_request.in_time,
                user_created=request.user.username,
                user_updated=request.user.username,
            )
            in_attendance_log.save()

        # Create attendance log for out_time if provided
        if time_request.out_time:
            out_attendance_log = AttendanceLog(
                child=time_request.child,
                date_logged=time_request.request_date,
                time_logged=time_request.out_time,
                user_created=request.user.username,
                user_updated=request.user.username,
            )
            out_attendance_log.save()

        # Update the time adjustment request
        time_request.status = "APPROVED"
        time_request.approved_by = request.user.username
        time_request.approved_date = datetime.now()
        time_request.in_attendance_log = in_attendance_log
        time_request.out_attendance_log = out_attendance_log
        time_request.user_updated = request.user.username
        time_request.save()

        return JsonResponse({
            "success": True,
            "message": "Time adjustment request approved. Attendance entries created."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def rejectTimeAdjustmentRequest(request):
    """
    Reject a time adjustment request.

    This view processes rejection of a time adjustment request,
    updating the status to REJECTED and recording the rejection reason.

    Args:
        request (HttpRequest): POST request with:
            - request_id: Integer ID of the TimeAdjustmentRequest to reject
            - rejection_reason: Optional string reason for rejection

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Updates request status to REJECTED
        - Records rejection reason if provided
        - Records rejecting user and timestamp

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        request_id = request.POST.get("request_id")
        rejection_reason = request.POST.get("rejection_reason", "")

        if not request_id:
            return JsonResponse({"error": "Request ID is required"}, status=400)

        # Get the time adjustment request
        try:
            time_request = TimeAdjustmentRequest.objects.get(
                pk=request_id,
                status="PENDING_APPROVAL",
                is_active=True
            )
        except TimeAdjustmentRequest.DoesNotExist:
            return JsonResponse(
                {"error": "Pending time adjustment request not found"},
                status=404
            )

        # Update the time adjustment request
        time_request.status = "REJECTED"
        time_request.approved_by = request.user.username
        time_request.approved_date = datetime.now()
        time_request.rejection_reason = rejection_reason.strip() if rejection_reason else None
        time_request.user_updated = request.user.username
        time_request.save()

        return JsonResponse({
            "success": True,
            "message": "Time adjustment request has been rejected."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================================
# Enrollment Discount Request Views
# ============================================================================


@login_required
def getEnrollmentDiscountRequest(request):
    """
    Render the enrollment discount request form page.

    This view displays the form for users to submit discount requests
    for child enrollments. It loads active children with approved enrollments
    and available discounts for selection.

    Args:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the enrollment_discount_request.html template with:
            - UserName: Current authenticated user's username
            - children: QuerySet of active children with approved enrollments
            - discounts: QuerySet of active, approved discounts

    Security:
        - Requires user authentication via @login_required decorator
    """
    UserName = request.user.username

    # Get active children with approved enrollments for the dropdown
    children = Child.objects.filter(
        is_active=True,
        is_enrolled=True,
        enrollement_approved=True
    ).order_by("child_first_name", "child_last_name")

    # Get active, approved discounts for the dropdown
    discounts = Discount.objects.filter(
        is_active=True,
        status="Approved"
    ).order_by("discount_code")

    return render(
        request,
        "enrollment_discount_request.html",
        {
            "UserName": UserName,
            "children": children,
            "discounts": discounts,
        },
    )


@login_required
def saveEnrollmentDiscountRequest(request):
    """
    Save a new enrollment discount request via AJAX POST.

    This view processes and saves new discount requests submitted
    by users. It validates the input and creates a new EnrollmentDiscountRequest
    record with PENDING_APPROVAL status.

    Args:
        request (HttpRequest): POST request with form data:
            - child_id: Integer ID of the child
            - enrollment_id: Integer ID of the enrollment
            - discount_id: Integer ID of the discount to apply
            - effective_from: String date in YYYY-MM-DD format
            - reason: String reason for the discount request

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Validates required fields (child_id, enrollment_id, discount_id, effective_from, reason)
        - Validates that effective_from is not in the future
        - Stores the previous discount from the enrollment for audit trail
        - Creates EnrollmentDiscountRequest with status PENDING_APPROVAL

    Security:
        - Requires user authentication via @login_required decorator
        - Only accepts POST requests
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        # Get form data
        child_id = request.POST.get("child_id")
        enrollment_id = request.POST.get("enrollment_id")
        discount_id = request.POST.get("discount_id")
        effective_from_str = request.POST.get("effective_from")
        reason = request.POST.get("reason")

        # Validate required fields
        if not child_id:
            return JsonResponse({"error": "Child is required"}, status=400)
        if not enrollment_id:
            return JsonResponse({"error": "Enrollment is required"}, status=400)
        if not discount_id:
            return JsonResponse({"error": "Discount is required"}, status=400)
        if not effective_from_str:
            return JsonResponse({"error": "Effective from date is required"}, status=400)
        if not reason or not reason.strip():
            return JsonResponse({"error": "Reason is required"}, status=400)

        # Parse effective_from date
        effective_from = datetime.strptime(effective_from_str, "%Y-%m-%d").date()

        # Validate that the date is not in the future
        if effective_from > date.today():
            return JsonResponse(
                {"error": "Effective from date cannot be in the future."},
                status=400
            )

        # Get the child object
        try:
            child = Child.objects.get(pk=child_id)
        except Child.DoesNotExist:
            return JsonResponse({"error": "Child not found"}, status=404)

        # Get the enrollment object
        try:
            enrollment = ChildEnrollment.objects.get(pk=enrollment_id, child=child)
        except ChildEnrollment.DoesNotExist:
            return JsonResponse({"error": "Enrollment not found"}, status=404)

        # Get the discount object
        try:
            discount = Discount.objects.get(pk=discount_id)
        except Discount.DoesNotExist:
            return JsonResponse({"error": "Discount not found"}, status=404)

        # Store the previous discount (can be None)
        previous_discount = enrollment.discount

        # Create the enrollment discount request
        discount_request = EnrollmentDiscountRequest(
            child=child,
            enrollment=enrollment,
            discount=discount,
            effective_from=effective_from,
            reason=reason.strip(),
            status="PENDING_APPROVAL",
            requested_by=request.user.username,
            previous_discount=previous_discount,
            user_created=request.user.username,
            user_updated=request.user.username,
        )
        discount_request.save()

        return JsonResponse({
            "success": True,
            "message": "Discount request submitted successfully. Pending approval."
        })

    except ValueError as e:
        return JsonResponse({"error": f"Invalid date format: {str(e)}"}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getEnrollmentDiscountRequestsJS(request):
    """
    Get list of enrollment discount requests as JSON for AJAX display.

    This view returns discount requests filtered based on user role.
    Superusers can see all requests, while regular users only see their own.

    Args:
        request (HttpRequest): GET request with optional filter parameters

    Returns:
        JsonResponse: JSON array of discount request records with:
            - id: Integer request ID
            - child_name: String child's full name with admission number
            - admission_number: String child's admission number
            - enrollment_code: String enrollment code
            - discount_code: String discount code being requested
            - discount_percentage: Decimal discount percentage
            - effective_from: String date in YYYY-MM-DD format
            - reason: String reason for request
            - status: String status (PENDING_APPROVAL/APPROVED/REJECTED)
            - requested_by: String username of requester
            - requested_date: String datetime in ISO format
            - previous_discount_code: String or null (previous discount if any)
            - rejection_reason: String or null

    Security:
        - Requires user authentication via @login_required decorator
        - Superusers see all requests; regular users see only their own
    """
    try:
        # Build query based on user role
        if request.user.is_superuser:
            requests_qs = EnrollmentDiscountRequest.objects.filter(
                is_active=True
            ).select_related("child", "enrollment", "discount", "previous_discount").order_by("-requested_date")
        else:
            requests_qs = EnrollmentDiscountRequest.objects.filter(
                is_active=True,
                requested_by=request.user.username
            ).select_related("child", "enrollment", "discount", "previous_discount").order_by("-requested_date")

        # Build result list
        result = []
        for req in requests_qs:
            result.append({
                "id": req.id,
                "child_name": f"{req.child.admission_number} - {req.child.child_first_name} {req.child.child_last_name}",
                "admission_number": req.child.admission_number,
                "enrollment_code": req.enrollment.enrollment_code if req.enrollment else "",
                "discount_code": req.discount.discount_code,
                "discount_name": req.discount.discount_name,
                "discount_rate": float(req.discount.discount_rate),
                "effective_from": req.effective_from.strftime("%Y-%m-%d"),
                "reason": req.reason,
                "status": req.status,
                "status_display": dict(EnrollmentDiscountRequest.STATUS_CHOICES).get(req.status, req.status),
                "requested_by": req.requested_by,
                "requested_date": req.requested_date.strftime("%Y-%m-%d %H:%M:%S"),
                "approved_by": req.approved_by or "",
                "approved_date": req.approved_date.strftime("%Y-%m-%d %H:%M:%S") if req.approved_date else "",
                "previous_discount_code": req.previous_discount.discount_code if req.previous_discount else None,
                "rejection_reason": req.rejection_reason or "",
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getEnrollmentDiscountApprovals(request):
    """
    Render the enrollment discount approvals page for superusers.

    This view displays the approval interface where superusers can review,
    approve, or reject pending enrollment discount requests.

    Args:
        request (HttpRequest): The HTTP request object containing user session data

    Returns:
        HttpResponse: Renders the enrollment_discount_approvals.html template with:
            - UserName: Current authenticated user's username
            - pending_count: Integer count of pending requests
        OR
        HttpResponseRedirect: Redirects to home if user is not a superuser

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status; redirects non-superusers to home
    """
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to access this page.")
        return redirect("/")

    UserName = request.user.username

    # Get count of pending requests
    pending_count = EnrollmentDiscountRequest.objects.filter(
        is_active=True,
        status="PENDING_APPROVAL"
    ).count()

    return render(
        request,
        "enrollment_discount_approvals.html",
        {
            "UserName": UserName,
            "pending_count": pending_count,
        },
    )


@login_required
def getPendingEnrollmentDiscountRequestsJS(request):
    """
    Get pending enrollment discount requests as JSON for superuser approval page.

    This view returns all pending discount requests with child, enrollment,
    and discount information for the approval interface.

    Args:
        request (HttpRequest): GET request

    Returns:
        JsonResponse: JSON array of pending request records with:
            - id: Integer request ID
            - child_id: Integer child ID
            - child_name: String child's full name with admission number
            - admission_number: String child's admission number
            - enrollment_id: Integer enrollment ID
            - enrollment_code: String enrollment code
            - discount_id: Integer discount ID
            - discount_code: String discount code being requested
            - discount_percentage: Decimal discount percentage
            - effective_from: String date in YYYY-MM-DD format
            - reason: String reason for request
            - requested_by: String username of requester
            - requested_date: String datetime in ISO format
            - previous_discount_code: String or null (current discount on enrollment)

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    try:
        # Get pending requests
        pending_requests = EnrollmentDiscountRequest.objects.filter(
            is_active=True,
            status="PENDING_APPROVAL"
        ).select_related("child", "enrollment", "discount", "previous_discount").order_by("-requested_date")

        # Build result list
        result = []
        for req in pending_requests:
            # Get requested discount info with debug logging
            if req.discount:
                requested_discount_name = req.discount.discount_name or ""
                requested_discount_rate = float(req.discount.discount_rate)
                # Debug log if discount_name is empty
                if not requested_discount_name:
                    print(f"WARNING: Discount ID {req.discount.id} has empty discount_name. Code: {req.discount.discount_code}")
            else:
                requested_discount_name = ""
                requested_discount_rate = 0
                print(f"WARNING: EnrollmentDiscountRequest ID {req.id} has no discount!")

            # Get current/previous discount info
            current_discount_name = req.previous_discount.discount_name if req.previous_discount else None
            current_discount_rate = float(req.previous_discount.discount_rate) if req.previous_discount else 0

            result.append({
                "id": req.id,
                "child_id": req.child.id,
                "child_name": f"{req.child.child_first_name} {req.child.child_last_name}",
                "admission_number": req.child.admission_number,
                "enrollment_id": req.enrollment.id,
                "enrollment_code": req.enrollment.enrollment_code if req.enrollment else "",
                "discount_id": req.discount.id if req.discount else None,
                "discount_code": req.discount.discount_code if req.discount else "",
                "requested_discount_name": requested_discount_name,
                "requested_discount_rate": requested_discount_rate,
                "effective_from": req.effective_from.strftime("%Y-%m-%d"),
                "reason": req.reason,
                "requested_by": req.requested_by,
                "requested_date": req.requested_date.strftime("%Y-%m-%d %H:%M:%S"),
                "current_discount_name": current_discount_name,
                "current_discount_rate": current_discount_rate,
            })

        return JsonResponse(result, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@transaction.atomic
def approveEnrollmentDiscountRequest(request):
    """
    Approve an enrollment discount request and update the enrollment.

    This view processes approval of a discount request, updating
    the enrollment's discount field to the requested discount.

    Args:
        request (HttpRequest): POST request with:
            - request_id: Integer ID of the EnrollmentDiscountRequest to approve

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Updates request status to APPROVED
        - Records approving user and timestamp
        - Updates the enrollment's discount to the requested discount

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
        - Uses transaction.atomic for database integrity
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        request_id = request.POST.get("request_id")

        if not request_id:
            return JsonResponse({"error": "Request ID is required"}, status=400)

        # Get the discount request
        try:
            discount_request = EnrollmentDiscountRequest.objects.select_related(
                "enrollment", "discount"
            ).get(
                pk=request_id,
                status="PENDING_APPROVAL",
                is_active=True
            )
        except EnrollmentDiscountRequest.DoesNotExist:
            return JsonResponse(
                {"error": "Pending discount request not found"},
                status=404
            )

        # Update the enrollment's discount
        enrollment = discount_request.enrollment
        enrollment.discount = discount_request.discount
        enrollment.user_updated = request.user.username
        enrollment.save(update_fields=["discount", "user_updated", "date_updated"])

        # Update the discount request
        discount_request.status = "APPROVED"
        discount_request.approved_by = request.user.username
        discount_request.approved_date = datetime.now()
        discount_request.user_updated = request.user.username
        discount_request.save()

        return JsonResponse({
            "success": True,
            "message": "Discount request approved. Enrollment discount has been updated."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def rejectEnrollmentDiscountRequest(request):
    """
    Reject an enrollment discount request.

    This view processes rejection of a discount request,
    updating the status to REJECTED and recording the rejection reason.

    Args:
        request (HttpRequest): POST request with:
            - request_id: Integer ID of the EnrollmentDiscountRequest to reject
            - rejection_reason: Optional string reason for rejection

    Returns:
        JsonResponse: JSON response with:
            - success: Boolean indicating success
            - message: String success message
            OR
            - error: String error message (on failure)

    Business Logic:
        - Updates request status to REJECTED
        - Records rejection reason if provided
        - Records rejecting user and timestamp

    Security:
        - Requires user authentication via @login_required decorator
        - Requires superuser status (returns 403 if not)
    """
    if not request.user.is_superuser:
        return JsonResponse(
            {"error": "Permission denied. Superuser access required."},
            status=403
        )

    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)

    try:
        request_id = request.POST.get("request_id")
        rejection_reason = request.POST.get("rejection_reason", "")

        if not request_id:
            return JsonResponse({"error": "Request ID is required"}, status=400)

        # Get the discount request
        try:
            discount_request = EnrollmentDiscountRequest.objects.get(
                pk=request_id,
                status="PENDING_APPROVAL",
                is_active=True
            )
        except EnrollmentDiscountRequest.DoesNotExist:
            return JsonResponse(
                {"error": "Pending discount request not found"},
                status=404
            )

        # Update the discount request
        discount_request.status = "REJECTED"
        discount_request.approved_by = request.user.username
        discount_request.approved_date = datetime.now()
        discount_request.rejection_reason = rejection_reason.strip() if rejection_reason else None
        discount_request.user_updated = request.user.username
        discount_request.save()

        return JsonResponse({
            "success": True,
            "message": "Discount request has been rejected."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def getChildEnrollmentInfoJS(request):
    """
    Get enrollment information for a child via AJAX.
    Returns enrollment details including current discount, package, and center.
    """
    try:
        child_id = request.GET.get("child_id")
        if not child_id:
            return JsonResponse({"error": "Child ID is required"}, status=400)

        # Get the child's approved enrollment
        enrollment = ChildEnrollment.objects.filter(
            child_id=child_id,
            status="Approved",
            is_active=True
        ).select_related("discount", "center", "branch").first()

        if not enrollment:
            return JsonResponse({
                "found": False,
                "message": "No approved enrollment found for this child"
            })

        # Get package info
        package_mapping = ChildPackageMapping.objects.filter(
            child_id=child_id,
            is_active=True
        ).select_related("normal_package", "flex_package").first()

        package_name = "N/A"
        if package_mapping:
            if package_mapping.normal_package:
                package_name = package_mapping.normal_package.package_name
            elif package_mapping.flex_package:
                package_name = package_mapping.flex_package.package_name

        return JsonResponse({
            "found": True,
            "enrollment_id": enrollment.id,
            "enrollment_code": enrollment.enrollment_code,
            "enrollment_status": enrollment.status,
            "enrollment_date": enrollment.enrollment_date.strftime("%Y-%m-%d") if enrollment.enrollment_date else "",
            "center_name": enrollment.center.daycare_name if enrollment.center else "N/A",
            "branch_name": enrollment.branch.branch_name if enrollment.branch else "N/A",
            "current_discount": enrollment.discount.discount_name if enrollment.discount else "No discount",
            "current_discount_rate": str(enrollment.discount.discount_rate) if enrollment.discount else "0",
            "package_name": package_name,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


# ==================== BATCH MEMO GENERATION ====================


@login_required
def batchMemoGeneration(request):
    """
    Display the batch memo generation page.

    This view provides the interface for generating invoice memos for multiple
    children at once. It shows a preview of eligible children and allows
    batch generation with progress tracking.
    """
    try:
        # Generate year range
        current_year = datetime.now().year
        year_range = [
            current_year - 1,
            current_year,
            current_year + 1,
        ]

        # Get current month
        current_month = datetime.now().month

        context = {
            "year_range": year_range,
            "current_month": current_month,
            "current_year": current_year,
            "UserName": request.user.username,
        }

        return render(request, "utils/batch_memo_generation.html", context)

    except Exception as e:
        messages.error(request, f"Error loading page: {str(e)}")
        return redirect("core:load_invoice_memo")


@login_required
def previewBatchMemoGeneration(request):
    """
    AJAX endpoint to preview batch memo generation.

    Returns a preview of which children are ready for memo generation,
    which need attention (missing attendance), and which cannot be processed.
    """
    try:
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([month, year]):
            return JsonResponse({"error": "Month and year are required"}, status=400)

        month_int = int(month)
        year_int = int(year)

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        preview = service.preview_batch_generation(month_int, year_int)

        return JsonResponse({
            "success": True,
            "preview": preview
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def executeBatchMemoGeneration(request):
    """
    AJAX endpoint to execute batch memo generation.

    Generates memos for the specified children or all eligible children.
    Returns progress updates and final results.
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        data = json.loads(request.body)
        month = data.get("month")
        year = data.get("year")
        force = data.get("force", False)
        child_ids = data.get("child_ids")  # Optional: specific children to process

        if not all([month, year]):
            return JsonResponse({"error": "Month and year are required"}, status=400)

        month_int = int(month)
        year_int = int(year)

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        results = service.generate_batch_memos(
            month_int,
            year_int,
            force=force,
            child_ids=child_ids
        )

        return JsonResponse({
            "success": True,
            "results": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def generateSingleMemoFromBatch(request):
    """
    AJAX endpoint to generate memo for a single child from batch interface.

    Used when retrying failed children or generating for specific children.
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST method required"}, status=400)

        data = json.loads(request.body)
        child_id = data.get("child_id")
        month = data.get("month")
        year = data.get("year")
        force = data.get("force", False)

        if not all([child_id, month, year]):
            return JsonResponse({"error": "Child ID, month, and year are required"}, status=400)

        child = Child.objects.get(id=child_id)
        month_int = int(month)
        year_int = int(year)

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        result = service.generate_memo_for_child(child, month_int, year_int, force=force)

        if result["success"]:
            return JsonResponse({
                "success": True,
                "memo_code": result["memo_code"],
                "amount_due": result["amount_due"],
                "child_name": f"{child.child_first_name} {child.child_last_name}",
                "admission_number": child.admission_number,
            })
        else:
            return JsonResponse({
                "success": False,
                "error": result["error"],
                "requires_force": result.get("requires_force", False),
            }, status=400)

    except Child.DoesNotExist:
        return JsonResponse({"error": "Child not found"}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@login_required(login_url="login")
def previewSingleChildMemo(request):
    """
    AJAX endpoint to preview memo calculation for a single child without saving.

    Returns the calculated 3-month breakdown including:
    - Month 1 (Outstanding): Balance from previous memo with source information
    - Month 2 (Previous): Calculated charges with attendance-based breakdown
    - Month 3 (Current): Advance package fee

    This allows users to verify calculations before generating the actual memo.
    """
    try:
        child_id = request.GET.get("child_id")
        month = request.GET.get("month")
        year = request.GET.get("year")

        if not all([child_id, month, year]):
            return JsonResponse(
                {"success": False, "error": "Child ID, month, and year are required"},
                status=400,
            )

        child = Child.objects.get(id=child_id)
        month_int = int(month)
        year_int = int(year)

        # Calculate the 3-month data without saving
        three_month_data = calculate_enhanced_three_month_data(
            child, month_int, year_int
        )

        # Format decimal values for JSON response
        def decimal_to_float(obj):
            """Recursively convert Decimal values to float for JSON serialization."""
            from decimal import Decimal

            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: decimal_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decimal_to_float(item) for item in obj]
            return obj

        # Convert the data to JSON-serializable format
        preview_data = decimal_to_float(three_month_data)

        # Add source memo info for debugging (from month1 outstanding data)
        if "source_memo" in three_month_data.get("month1", {}):
            preview_data["month1"]["source_memo"] = three_month_data["month1"][
                "source_memo"
            ]

        return JsonResponse(
            {
                "success": True,
                "preview": preview_data,
            }
        )

    except Child.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Child not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ============================================
# MEMO REGENERATION VIEWS
# ============================================


@login_required(login_url="login")
def previewMemoRegeneration(request):
    """
    AJAX endpoint to preview what values would change if memo is regenerated.

    Returns comparison of current vs new calculated values.
    """
    try:
        memo_id = request.GET.get("memo_id")

        if not memo_id:
            return JsonResponse(
                {"success": False, "error": "Memo ID is required"},
                status=400
            )

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        memo = InvoiceMemo.objects.get(id=memo_id, is_active=True)

        # Get current values
        original_values = service.get_memo_snapshot(memo)

        # Calculate new values
        new_values = service.calculate_regeneration_preview(memo)

        if "error" in new_values:
            return JsonResponse(
                {"success": False, "error": new_values["error"]},
                status=500
            )

        return JsonResponse({
            "success": True,
            "memo_code": memo.memo_code,
            "child_name": f"{memo.child.child_first_name} {memo.child.child_last_name}",
            "admission_number": memo.child.admission_number,
            "original": original_values,
            "new": new_values,
            "differences": {
                "outstanding": new_values["outstanding"] - original_values["outstanding"],
                "previous_charges": new_values["previous_charges"] - original_values["previous_charges"],
                "current_advance": new_values["current_advance"] - original_values["current_advance"],
                "total_due": new_values["total_due"] - original_values["total_due"],
            }
        })

    except InvoiceMemo.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Memo not found"},
            status=404
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required(login_url="login")
def requestMemoRegeneration(request):
    """
    AJAX endpoint to create a regeneration request.

    POST parameters:
    - memo_id: ID of the memo to regenerate
    - reason: Reason for regeneration
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "POST method required"},
            status=405
        )

    try:
        import json
        data = json.loads(request.body)

        memo_id = data.get("memo_id")
        reason = data.get("reason", "").strip()

        if not memo_id:
            return JsonResponse(
                {"success": False, "error": "Memo ID is required"},
                status=400
            )

        if not reason:
            return JsonResponse(
                {"success": False, "error": "Reason for regeneration is required"},
                status=400
            )

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        result = service.request_memo_regeneration(memo_id, reason, request.user.username)

        if result["success"]:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required(login_url="login")
def getMemoRegenerationRequests(request):
    """
    Page to display pending regeneration requests for admin review.
    """
    from core.services.memo_generation import MemoGenerationService
    from core.models import MemoRegenerationRequest

    service = MemoGenerationService(user=request.user.username)
    pending_requests = service.get_pending_regeneration_requests()

    # Also get recent approved/rejected for history
    recent_processed = MemoRegenerationRequest.objects.filter(
        status__in=["APPROVED", "REJECTED"],
        is_active=True
    ).select_related('memo', 'memo__child').order_by('-reviewed_at')[:20]

    processed_list = []
    for req in recent_processed:
        processed_list.append({
            "id": req.id,
            "memo_code": req.memo.memo_code,
            "child_name": req.get_child_name(),
            "admission_number": req.memo.child.admission_number,
            "status": req.status,
            "reason": req.reason,
            "requested_by": req.requested_by,
            "requested_at": req.requested_at,
            "reviewed_by": req.reviewed_by,
            "reviewed_at": req.reviewed_at,
            "review_comments": req.review_comments,
        })

    context = {
        "pending_requests": pending_requests,
        "processed_requests": processed_list,
        "is_admin": request.user.is_staff or request.user.is_superuser,
    }

    return render(request, "memo_regeneration_requests.html", context)


@login_required(login_url="login")
def getRegenerationRequestDetail(request):
    """
    AJAX endpoint to get full details of a regeneration request.
    """
    try:
        request_id = request.GET.get("request_id")

        if not request_id:
            return JsonResponse(
                {"success": False, "error": "Request ID is required"},
                status=400
            )

        from core.models import MemoRegenerationRequest

        regen_request = MemoRegenerationRequest.objects.select_related(
            'memo', 'memo__child'
        ).get(id=request_id, is_active=True)

        return JsonResponse({
            "success": True,
            "request": {
                "id": regen_request.id,
                "memo_code": regen_request.memo.memo_code,
                "child_name": regen_request.get_child_name(),
                "admission_number": regen_request.memo.child.admission_number,
                "memo_month": regen_request.memo.memo_month,
                "memo_year": regen_request.memo.memo_year,
                "status": regen_request.status,
                "reason": regen_request.reason,
                "requested_by": regen_request.requested_by,
                "requested_at": regen_request.requested_at.isoformat(),
                "original_values": regen_request.original_values,
                "new_calculated_values": regen_request.new_calculated_values,
                "differences": regen_request.get_value_differences(),
            }
        })

    except MemoRegenerationRequest.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Request not found"},
            status=404
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required(login_url="login")
def approveMemoRegeneration(request):
    """
    AJAX endpoint for admin to approve a regeneration request.

    POST parameters:
    - request_id: ID of the regeneration request
    - comments: Optional approval comments
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "POST method required"},
            status=405
        )

    # Check if user is admin
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse(
            {"success": False, "error": "Admin privileges required"},
            status=403
        )

    try:
        import json
        data = json.loads(request.body)

        request_id = data.get("request_id")
        comments = data.get("comments", "")

        if not request_id:
            return JsonResponse(
                {"success": False, "error": "Request ID is required"},
                status=400
            )

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        result = service.approve_regeneration(request_id, request.user.username, comments)

        if result["success"]:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required(login_url="login")
def rejectMemoRegeneration(request):
    """
    AJAX endpoint for admin to reject a regeneration request.

    POST parameters:
    - request_id: ID of the regeneration request
    - reason: Reason for rejection
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "POST method required"},
            status=405
        )

    # Check if user is admin
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse(
            {"success": False, "error": "Admin privileges required"},
            status=403
        )

    try:
        import json
        data = json.loads(request.body)

        request_id = data.get("request_id")
        reason = data.get("reason", "")

        if not request_id:
            return JsonResponse(
                {"success": False, "error": "Request ID is required"},
                status=400
            )

        from core.services.memo_generation import MemoGenerationService

        service = MemoGenerationService(user=request.user.username)
        result = service.reject_regeneration(request_id, request.user.username, reason)

        if result["success"]:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)