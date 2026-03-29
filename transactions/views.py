"""
Views for the transactions app.

This module contains views for managing package price changes and revisions,
as well as fee revision letter generation for parents.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Child, FixedPackage, FlexPackages

from .models import PackagePriceRevision
from .services.letter_generation import FeeRevisionLetterService


@login_required
def get_package_price_changes(request):
    """
    Displays the package price changes management page.

    This function renders the interface for managing price revisions
    for both fixed and flex packages.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders package_price_changes.html template

    Business Logic:
        - Retrieves all active fixed and flex packages
        - Provides interface for bulk and individual price changes
        - Displays pending price revisions awaiting application
    """
    fixed_packages = FixedPackage.objects.filter(is_active=True).select_related(
        "package_type", "package_term"
    )
    flex_packages = FlexPackages.objects.filter(is_active=True).select_related(
        "package_type", "package_term"
    )

    return render(
        request,
        "../templates/package_price_changes.html",
        {
            "fixed_packages": fixed_packages,
            "flex_packages": flex_packages,
            "UserName": request.user.username,
        },
    )


@login_required
def get_packages_for_price_change_js(request):
    """
    Returns JSON data of packages for DataTables display.

    This function provides package data for the DataTables component
    on the price changes management page.

    Args:
        request (HttpRequest): The HTTP request object
            - type (optional): Filter by package type ('fixed' or 'flex')

    Returns:
        JsonResponse: List of packages with id, code, name, type, price, term,
                      and type-specific fields (time_slot for fixed, hours for flex)

    Business Logic:
        - Retrieves fixed and/or flex packages based on type filter
        - Combines them into a unified list with package type indicator
        - Returns data formatted for DataTables consumption
    """
    if request.method == "GET":
        packages_list = []
        package_type_filter = request.GET.get("type", "").lower()

        # Get fixed packages (if no filter or filter is 'fixed')
        if not package_type_filter or package_type_filter == "fixed":
            fixed_packages = FixedPackage.objects.filter(is_active=True).select_related(
                "package_term"
            )
            for pkg in fixed_packages:
                # Format time slot (e.g., "8:00 AM - 12:00 PM")
                time_slot = ""
                if pkg.from_time and pkg.to_time:
                    from_str = pkg.from_time.strftime("%I:%M %p").lstrip("0")
                    to_str = pkg.to_time.strftime("%I:%M %p").lstrip("0")
                    time_slot = f"{from_str} - {to_str}"

                packages_list.append(
                    {
                        "id": pkg.id,
                        "package_code": pkg.package_code,
                        "package_name": pkg.package_name,
                        "package_type": "Fixed",
                        "current_price": float(pkg.package_total) if pkg.package_total else 0,
                        "package_term": pkg.package_term.package_type_name if pkg.package_term else "",
                        "time_slot": time_slot,
                        "hours": float(pkg.no_hours) if pkg.no_hours else 0,
                    }
                )

        # Get flex packages (if no filter or filter is 'flex')
        if not package_type_filter or package_type_filter == "flex":
            flex_packages = FlexPackages.objects.filter(is_active=True).select_related(
                "package_term"
            )
            for pkg in flex_packages:
                packages_list.append(
                    {
                        "id": pkg.id,
                        "package_code": pkg.package_code,
                        "package_name": pkg.package_name,
                        "package_type": "Flex",
                        "current_price": float(pkg.package_total) if pkg.package_total else 0,
                        "package_term": pkg.package_term.package_type_name if pkg.package_term else "",
                        "time_slot": "",
                        "hours": float(pkg.no_hours) if pkg.no_hours else 0,
                    }
                )

        return JsonResponse(packages_list, safe=False)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
@transaction.atomic
def save_bulk_price_change(request):
    """
    Saves bulk price changes by percentage for multiple packages.

    This function processes bulk price revision requests, creating
    PackagePriceRevision records for each selected package based on
    a percentage increase/decrease.

    Args:
        request (HttpRequest): The HTTP request object containing:
            - percentage: Decimal percentage change (e.g., 10 for 10% increase)
            - effective_from: Date when changes take effect
            - package_ids: JSON list of package IDs with type (e.g., "fixed_1", "flex_2")
            - notes: Optional notes about the revision

    Returns:
        HttpResponseRedirect: Redirects to package price changes page

    Business Logic:
        - Validates user permissions (restricts Data Entry users)
        - Calculates new prices based on percentage change
        - Creates PackagePriceRevision records for each package
        - Uses atomic transactions for data consistency
        - Supports both positive (increase) and negative (decrease) percentages

    Database Operations:
        - Creates PackagePriceRevision records
        - Uses @transaction.atomic for data integrity
    """
    if request.method == "POST":
        import json

        user = User.objects.get(username=request.user.username)

        # Check for permission
        if user.groups.filter(name="Data Entry").exists():
            return JsonResponse(
                {"success": False, "error": "You are not authorized to perform this operation."},
                status=403,
            )

        try:
            # Handle JSON body for AJAX requests
            if request.content_type == "application/json":
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse(
                        {"success": False, "error": "Invalid JSON data."}, status=400
                    )
                percentage_str = str(data.get("percentage_change", "0"))
                effective_from_str = data.get("effective_from")
                package_ids = data.get("selected_packages", [])
                notes = data.get("notes", "")
            else:
                # Handle form data
                percentage_str = request.POST.get("percentage", "0")
                effective_from_str = request.POST.get("effective_from")
                package_ids_json = request.POST.get("package_ids", "[]")
                notes = request.POST.get("notes", "")
                try:
                    package_ids = json.loads(package_ids_json)
                except json.JSONDecodeError:
                    return JsonResponse(
                        {"success": False, "error": "Invalid package selection."}, status=400
                    )

            # Validate percentage
            try:
                percentage = Decimal(percentage_str)
            except (InvalidOperation, ValueError):
                return JsonResponse(
                    {"success": False, "error": "Invalid percentage value."}, status=400
                )

            # Validate effective date
            if not effective_from_str:
                return JsonResponse(
                    {"success": False, "error": "Effective from date is required."}, status=400
                )

            try:
                effective_from = date.fromisoformat(effective_from_str)
            except ValueError:
                return JsonResponse(
                    {"success": False, "error": "Invalid date format."}, status=400
                )

            if not package_ids:
                return JsonResponse(
                    {"success": False, "error": "No packages selected."}, status=400
                )

            # Process each package
            created_count = 0
            for pkg_info in package_ids:
                pkg_type = pkg_info.get("type")
                pkg_id = pkg_info.get("id")

                if pkg_type == "fixed":
                    try:
                        package = FixedPackage.objects.get(id=pkg_id, is_active=True)
                        current_price = package.package_total or Decimal("0")
                        new_price = current_price * (1 + percentage / 100)
                        new_price = new_price.quantize(Decimal("0.01"))

                        PackagePriceRevision.objects.create(
                            fixed_package=package,
                            current_price=current_price,
                            new_price=new_price,
                            percentage_change=percentage,
                            effective_from=effective_from,
                            notes=notes,
                            user_created=request.user.username,
                        )
                        created_count += 1
                    except FixedPackage.DoesNotExist:
                        continue

                elif pkg_type == "flex":
                    try:
                        package = FlexPackages.objects.get(id=pkg_id, is_active=True)
                        current_price = package.package_total or Decimal("0")
                        new_price = current_price * (1 + percentage / 100)
                        new_price = new_price.quantize(Decimal("0.01"))

                        PackagePriceRevision.objects.create(
                            flex_package=package,
                            current_price=current_price,
                            new_price=new_price,
                            percentage_change=percentage,
                            effective_from=effective_from,
                            notes=notes,
                            user_created=request.user.username,
                        )
                        created_count += 1
                    except FlexPackages.DoesNotExist:
                        continue

            if created_count > 0:
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Price revision created for {created_count} package(s).",
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "error": "No price revisions were created."},
                    status=400,
                )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error creating price revisions: {str(e)}"},
                status=500,
            )

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)


@login_required
@transaction.atomic
def save_individual_price_change(request):
    """
    Saves an individual package price change.

    This function processes individual price revision requests,
    creating a PackagePriceRevision record for a single package.

    Args:
        request (HttpRequest): The HTTP request object containing:
            - package_id: ID of the package to update
            - package_type: Type of package ('fixed' or 'flex')
            - new_price: The new price to apply
            - effective_from: Date when change takes effect
            - notes: Optional notes about the revision

    Returns:
        HttpResponseRedirect: Redirects to package price changes page

    Business Logic:
        - Validates user permissions (restricts Data Entry users)
        - Creates PackagePriceRevision record with specified new price
        - Calculates percentage change for record keeping
        - Uses atomic transactions for data consistency

    Database Operations:
        - Creates PackagePriceRevision record
        - Uses @transaction.atomic for data integrity
    """
    if request.method == "POST":
        import json

        user = User.objects.get(username=request.user.username)

        # Check for permission
        if user.groups.filter(name="Data Entry").exists():
            return JsonResponse(
                {"success": False, "error": "You are not authorized to perform this operation."},
                status=403,
            )

        try:
            # Handle JSON body for AJAX requests
            if request.content_type == "application/json":
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse(
                        {"success": False, "error": "Invalid JSON data."}, status=400
                    )
                package_id = data.get("package_id")
                package_type = data.get("package_type")
                new_price_str = str(data.get("new_price", ""))
                effective_from_str = data.get("effective_from")
                notes = data.get("notes", "")
            else:
                # Handle form data
                package_id = request.POST.get("package_id")
                package_type = request.POST.get("package_type")
                new_price_str = request.POST.get("new_price", "")
                effective_from_str = request.POST.get("effective_from")
                notes = request.POST.get("notes", "")

            # Validate inputs
            if not package_id:
                return JsonResponse(
                    {"success": False, "error": "Package ID is required."}, status=400
                )

            if not package_type or package_type not in ["fixed", "flex"]:
                return JsonResponse(
                    {"success": False, "error": "Invalid package type."}, status=400
                )

            # Validate new price
            try:
                new_price = Decimal(new_price_str)
                if new_price < 0:
                    return JsonResponse(
                        {"success": False, "error": "Price cannot be negative."}, status=400
                    )
            except (InvalidOperation, ValueError, TypeError):
                return JsonResponse(
                    {"success": False, "error": "Invalid price value."}, status=400
                )

            # Validate effective date
            if not effective_from_str:
                return JsonResponse(
                    {"success": False, "error": "Effective from date is required."}, status=400
                )

            try:
                effective_from = date.fromisoformat(effective_from_str)
            except ValueError:
                return JsonResponse(
                    {"success": False, "error": "Invalid date format."}, status=400
                )

            # Get the package and create revision
            if package_type == "fixed":
                try:
                    package = FixedPackage.objects.get(id=package_id, is_active=True)
                    current_price = package.package_total or Decimal("0")

                    # Calculate percentage change
                    if current_price > 0:
                        percentage_change = (
                            (new_price - current_price) / current_price
                        ) * 100
                        percentage_change = percentage_change.quantize(Decimal("0.01"))
                    else:
                        percentage_change = None

                    PackagePriceRevision.objects.create(
                        fixed_package=package,
                        current_price=current_price,
                        new_price=new_price.quantize(Decimal("0.01")),
                        percentage_change=percentage_change,
                        effective_from=effective_from,
                        notes=notes,
                        user_created=request.user.username,
                    )
                    return JsonResponse(
                        {
                            "success": True,
                            "message": f"Price revision created for {package.package_name}.",
                        }
                    )
                except FixedPackage.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "error": "Fixed package not found."}, status=404
                    )

            elif package_type == "flex":
                try:
                    package = FlexPackages.objects.get(id=package_id, is_active=True)
                    current_price = package.package_total or Decimal("0")

                    # Calculate percentage change
                    if current_price > 0:
                        percentage_change = (
                            (new_price - current_price) / current_price
                        ) * 100
                        percentage_change = percentage_change.quantize(Decimal("0.01"))
                    else:
                        percentage_change = None

                    PackagePriceRevision.objects.create(
                        flex_package=package,
                        current_price=current_price,
                        new_price=new_price.quantize(Decimal("0.01")),
                        percentage_change=percentage_change,
                        effective_from=effective_from,
                        notes=notes,
                        user_created=request.user.username,
                    )
                    return JsonResponse(
                        {
                            "success": True,
                            "message": f"Price revision created for {package.package_name}.",
                        }
                    )
                except FlexPackages.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "error": "Flex package not found."}, status=404
                    )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error creating price revision: {str(e)}"},
                status=500,
            )

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)


@login_required
def get_pending_price_revisions_js(request):
    """
    Returns JSON data of pending price revisions for DataTables display.

    This function provides pending price revision data for the DataTables
    component, showing revisions that have not yet been applied.

    Args:
        request (HttpRequest): The HTTP request object
            - type (optional): Filter by package type ('fixed' or 'flex')

    Returns:
        JsonResponse: List of pending revisions with package details and pricing info

    Business Logic:
        - Retrieves PackagePriceRevision records where is_applied=False
        - Optionally filters by package type
        - Includes package name, current price, new price, percentage change
        - Returns data formatted for DataTables consumption
    """
    if request.method == "GET":
        revisions_list = []
        package_type_filter = request.GET.get("type", "").lower()

        # Build base queryset
        pending_revisions = PackagePriceRevision.objects.filter(
            is_active=True, is_applied=False
        ).select_related("fixed_package", "flex_package")

        # Apply type filter if specified
        if package_type_filter == "fixed":
            pending_revisions = pending_revisions.filter(
                fixed_package__isnull=False
            )
        elif package_type_filter == "flex":
            pending_revisions = pending_revisions.filter(
                flex_package__isnull=False
            )

        for revision in pending_revisions:
            # Determine package name and type
            if revision.fixed_package:
                package_name = revision.fixed_package.package_name
                package_type = "Fixed"
                package_code = revision.fixed_package.package_code
            elif revision.flex_package:
                package_name = revision.flex_package.package_name
                package_type = "Flex"
                package_code = revision.flex_package.package_code
            else:
                package_name = "Unknown"
                package_type = "Unknown"
                package_code = ""

            revisions_list.append(
                {
                    "id": revision.id,
                    "package_name": package_name,
                    "package_code": package_code,
                    "package_type": package_type,
                    "current_price": float(revision.current_price),
                    "new_price": float(revision.new_price),
                    "percentage_change": (
                        float(revision.percentage_change)
                        if revision.percentage_change
                        else 0
                    ),
                    "effective_from": revision.effective_from.isoformat(),
                    "notes": revision.notes or "",
                    "created_at": revision.date_created.strftime("%Y-%m-%d %H:%M")
                    if revision.date_created
                    else "",
                }
            )

        return JsonResponse(revisions_list, safe=False)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
@transaction.atomic
def apply_pending_price_changes(request):
    """
    Applies pending price changes that have reached their effective date.

    This function finds all PackagePriceRevision records that are due
    to be applied (effective_from <= today and is_applied=False) and
    updates the corresponding package prices.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponseRedirect: Redirects to package price changes page

    Business Logic:
        - Finds all pending revisions where effective_from <= today
        - Updates package.package_total to the new_price
        - Sets is_applied=True and applied_date to current timestamp
        - Uses atomic transactions to ensure all-or-nothing updates
        - Validates user permissions before applying changes

    Database Operations:
        - Updates FixedPackage.package_total or FlexPackages.package_total
        - Updates PackagePriceRevision status fields
        - Uses @transaction.atomic for data integrity
    """
    if request.method == "POST":
        user = User.objects.get(username=request.user.username)

        # Check for permission
        if user.groups.filter(name="Data Entry").exists():
            return JsonResponse(
                {"success": False, "error": "You are not authorized to perform this operation."},
                status=403,
            )

        try:
            today = date.today()

            # Find all pending revisions that are due
            pending_revisions = PackagePriceRevision.objects.filter(
                is_active=True, is_applied=False, effective_from__lte=today
            ).select_related("fixed_package", "flex_package")

            applied_count = 0
            now = timezone.now()

            for revision in pending_revisions:
                if revision.fixed_package:
                    # Update fixed package price
                    package = revision.fixed_package
                    package.package_total = revision.new_price
                    package.user_updated = request.user.username
                    package.save(update_fields=["package_total", "user_updated"])

                    # Mark revision as applied
                    revision.is_applied = True
                    revision.applied_date = now
                    revision.user_updated = request.user.username
                    revision.save(
                        update_fields=["is_applied", "applied_date", "user_updated"]
                    )
                    applied_count += 1

                elif revision.flex_package:
                    # Update flex package price
                    package = revision.flex_package
                    package.package_total = revision.new_price
                    package.user_updated = request.user.username
                    package.save(update_fields=["package_total", "user_updated"])

                    # Mark revision as applied
                    revision.is_applied = True
                    revision.applied_date = now
                    revision.user_updated = request.user.username
                    revision.save(
                        update_fields=["is_applied", "applied_date", "user_updated"]
                    )
                    applied_count += 1

            if applied_count > 0:
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Successfully applied {applied_count} price change(s).",
                    }
                )
            else:
                return JsonResponse(
                    {"success": True, "message": "No pending price changes to apply."}
                )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error applying price changes: {str(e)}"},
                status=500,
            )

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)


@login_required
@transaction.atomic
def cancel_price_revision(request):
    """
    Cancels a pending price revision by soft-deleting it.

    This function deactivates a PackagePriceRevision record that has not
    yet been applied.

    Args:
        request (HttpRequest): The HTTP request object containing:
            - revision_id: ID of the revision to cancel

    Returns:
        HttpResponseRedirect: Redirects to package price changes page

    Business Logic:
        - Only allows cancellation of unapplied revisions
        - Sets is_active=False (soft delete)
        - Uses atomic transactions for data consistency

    Database Operations:
        - Updates PackagePriceRevision.is_active to False
        - Uses @transaction.atomic for data integrity
    """
    if request.method == "POST":
        import json

        user = User.objects.get(username=request.user.username)

        # Check for permission
        if user.groups.filter(name="Data Entry").exists():
            return JsonResponse(
                {"success": False, "error": "You are not authorized to perform this operation."},
                status=403,
            )

        try:
            # Handle JSON body for AJAX requests
            if request.content_type == "application/json":
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse(
                        {"success": False, "error": "Invalid JSON data."}, status=400
                    )
                revision_id = data.get("revision_id")
            else:
                revision_id = request.POST.get("revision_id")

            if not revision_id:
                return JsonResponse(
                    {"success": False, "error": "Revision ID is required."}, status=400
                )

            revision = PackagePriceRevision.objects.get(
                id=revision_id, is_active=True, is_applied=False
            )

            # Soft delete the revision
            revision.is_active = False
            revision.user_updated = request.user.username
            revision.save(update_fields=["is_active", "user_updated"])

            return JsonResponse(
                {"success": True, "message": "Price revision cancelled successfully."}
            )

        except PackagePriceRevision.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Revision not found or has already been applied/cancelled."},
                status=404,
            )
        except Exception as e:
            return JsonResponse(
                {"success": False, "error": f"Error cancelling revision: {str(e)}"},
                status=500,
            )

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)


@login_required
def get_price_revision_history_js(request):
    """
    Returns JSON data of applied price revisions for historical reference.

    This function provides historical price revision data for reporting
    and audit purposes.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: List of applied revisions with package details and pricing info

    Business Logic:
        - Retrieves PackagePriceRevision records where is_applied=True
        - Includes package name, old price, new price, applied date
        - Returns data formatted for DataTables consumption
    """
    if request.method == "GET":
        revisions_list = []

        applied_revisions = (
            PackagePriceRevision.objects.filter(is_active=True, is_applied=True)
            .select_related("fixed_package", "flex_package")
            .order_by("-applied_date")[:100]
        )  # Limit to last 100

        for revision in applied_revisions:
            # Determine package name and type
            if revision.fixed_package:
                package_name = revision.fixed_package.package_name
                package_type = "Fixed"
                package_code = revision.fixed_package.package_code
            elif revision.flex_package:
                package_name = revision.flex_package.package_name
                package_type = "Flex"
                package_code = revision.flex_package.package_code
            else:
                package_name = "Unknown"
                package_type = "Unknown"
                package_code = ""

            revisions_list.append(
                {
                    "id": revision.id,
                    "package_name": package_name,
                    "package_code": package_code,
                    "package_type": package_type,
                    "current_price": float(revision.current_price),
                    "new_price": float(revision.new_price),
                    "percentage_change": (
                        float(revision.percentage_change)
                        if revision.percentage_change
                        else None
                    ),
                    "effective_from": revision.effective_from.isoformat(),
                    "applied_date": revision.applied_date.strftime("%Y-%m-%d %H:%M")
                    if revision.applied_date
                    else "",
                    "notes": revision.notes or "",
                }
            )

        return JsonResponse(revisions_list, safe=False)

    return JsonResponse({"error": "Invalid request method"}, status=405)


# =============================================================================
# Fee Revision Letter Generation Views
# =============================================================================


@login_required
def get_generate_parents_letter(request):
    """
    Displays the fee revision letter generation page.

    This view renders the interface for generating PDF letters to notify
    parents about upcoming package price changes.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        HttpResponse: Renders generate_parents_letter.html template

    Business Logic:
        - Shows list of eligible children (active attendance in last 2 months)
        - Provides options for bulk or individual letter generation
        - Displays current and revised package prices
    """
    return render(
        request,
        "generate_parents_letter.html",
        {
            "UserName": request.user.username,
        },
    )


@login_required
def get_eligible_children_js(request):
    """
    Returns JSON data of eligible children for letter generation.

    This function provides data for the DataTables component showing
    children eligible for fee revision letters.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        JsonResponse: List of children with package and pricing info

    Business Logic:
        - Queries children with active attendance in last 2 months
        - Includes current package and revised price information
        - Returns data formatted for DataTables consumption
    """
    if request.method == "GET":
        try:
            children_summary = FeeRevisionLetterService.get_children_summary()
            return JsonResponse(children_summary, safe=False)
        except Exception as e:
            return JsonResponse(
                {"error": f"Error fetching children: {str(e)}"}, status=500
            )

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def generate_individual_letter_pdf(request, child_id):
    """
    Generates a PDF letter for a single child.

    Args:
        request (HttpRequest): The HTTP request object
        child_id (int): ID of the child

    Returns:
        FileResponse: PDF file download

    Business Logic:
        - Retrieves child by ID
        - Generates personalized fee revision letter
        - Returns PDF as downloadable file
    """
    child = get_object_or_404(Child, id=child_id, is_active=True)

    service = FeeRevisionLetterService()
    pdf_buffer = service.generate_individual_letter(child)

    # Generate filename
    child_name = f"{child.child_first_name}_{child.child_last_name}"
    child_name = child_name.replace(" ", "_")
    filename = f"fee_revision_letter_{child_name}_{date.today().isoformat()}.pdf"

    response = FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
    return response


@login_required
def generate_bulk_letters_pdf(request):
    """
    Generates a PDF containing letters for all eligible children.

    Args:
        request (HttpRequest): The HTTP request object

    Returns:
        FileResponse: PDF file download with all letters

    Business Logic:
        - Queries all eligible children (active attendance in last 2 months)
        - Generates letters for each child in a single PDF
        - Each letter appears on a separate page
    """
    if request.method == "POST":
        import json

        try:
            # Check if specific child IDs were provided
            if request.content_type == "application/json":
                data = json.loads(request.body)
                child_ids = data.get("child_ids", [])
            else:
                child_ids_json = request.POST.get("child_ids", "[]")
                child_ids = json.loads(child_ids_json)

            service = FeeRevisionLetterService()

            if child_ids:
                # Generate for selected children only
                children = Child.objects.filter(
                    id__in=child_ids,
                    is_active=True,
                    is_enrolled=True,
                    enrollement_approved=True,
                ).order_by("child_first_name", "child_last_name")
            else:
                # Generate for all eligible children
                children = service.get_children_with_active_attendance()

            if not children.exists():
                return JsonResponse(
                    {"error": "No eligible children found."}, status=400
                )

            pdf_buffer = service.generate_bulk_letters(children)

            # Generate filename
            filename = f"fee_revision_letters_bulk_{date.today().isoformat()}.pdf"

            response = FileResponse(
                pdf_buffer,
                as_attachment=True,
                filename=filename,
                content_type="application/pdf",
            )
            return response

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data."}, status=400)
        except Exception as e:
            return JsonResponse(
                {"error": f"Error generating letters: {str(e)}"}, status=500
            )

    # For GET requests, generate for all eligible children
    service = FeeRevisionLetterService()
    children = service.get_children_with_active_attendance()

    if not children.exists():
        return JsonResponse({"error": "No eligible children found."}, status=400)

    pdf_buffer = service.generate_bulk_letters(children)

    filename = f"fee_revision_letters_bulk_{date.today().isoformat()}.pdf"

    response = FileResponse(
        pdf_buffer,
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
    return response


@login_required
def preview_letter_pdf(request, child_id):
    """
    Previews a PDF letter for a single child (inline display).

    Args:
        request (HttpRequest): The HTTP request object
        child_id (int): ID of the child

    Returns:
        HttpResponse: PDF displayed inline in browser

    Business Logic:
        - Similar to generate_individual_letter_pdf but displays inline
        - Useful for previewing before bulk download
    """
    child = get_object_or_404(Child, id=child_id, is_active=True)

    service = FeeRevisionLetterService()
    pdf_buffer = service.generate_individual_letter(child)

    response = HttpResponse(pdf_buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = "inline"
    # Allow embedding in iframe for preview functionality
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response
