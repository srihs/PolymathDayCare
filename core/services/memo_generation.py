"""
Memo Generation Service

Service class for automated batch memo generation.
Handles validation, generation, and reporting for invoice memos.
"""

import calendar
import json
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Optional, Any

from django.db import transaction
from django.db.models import QuerySet

from core.models import (
    Child,
    ChildEnrollment,
    ChildPackageMapping,
    InvoiceMemo,
    InvoiceMemoDetail,
    AttendanceLog,
    TimeAdjustmentRequest,
)


class MemoGenerationService:
    """
    Service class for automated memo generation.

    Provides methods for:
    - Getting eligible children for memo generation
    - Validating children before memo generation
    - Generating memos for single or multiple children
    - Reporting generation results
    """

    def __init__(self, user: str = "System"):
        """
        Initialize the service.

        Args:
            user: Username for audit trail (default: "System")
        """
        self.user = user

    def get_eligible_children(self, month: int, year: int) -> QuerySet:
        """
        Get children eligible for memo generation.

        Returns children who:
        - Are active (is_active=True)
        - Are enrolled (is_enrolled=True)
        - Have approved enrollment (enrollement_approved=True)
        - Don't already have a memo for the specified month/year

        Args:
            month: Target month (1-12)
            year: Target year (e.g., 2025)

        Returns:
            QuerySet of eligible Child objects
        """
        # Get children who already have memos for this month
        existing_memo_child_ids = InvoiceMemo.objects.filter(
            memo_month=month,
            memo_year=year,
            is_active=True
        ).values_list('child_id', flat=True)

        return Child.objects.filter(
            is_active=True,
            is_enrolled=True,
            enrollement_approved=True
        ).exclude(
            id__in=existing_memo_child_ids
        ).order_by('admission_number')

    def get_children_with_existing_memos(self, month: int, year: int) -> QuerySet:
        """
        Get children who already have memos for the specified month.

        Args:
            month: Target month (1-12)
            year: Target year

        Returns:
            QuerySet of Child objects with existing memos
        """
        existing_memo_child_ids = InvoiceMemo.objects.filter(
            memo_month=month,
            memo_year=year,
            is_active=True
        ).values_list('child_id', flat=True)

        return Child.objects.filter(
            id__in=existing_memo_child_ids,
            is_active=True
        ).order_by('admission_number')

    def _get_previous_month(self, month: int, year: int) -> tuple:
        """Calculate previous month and year."""
        if month > 1:
            return month - 1, year
        return 12, year - 1

    def _get_outstanding_month(self, month: int, year: int) -> tuple:
        """Calculate outstanding month (2 months before target)."""
        if month > 2:
            return month - 2, year
        elif month == 2:
            return 12, year - 1
        else:  # month == 1
            return 11, year - 1

    def _get_month_range(self, month: int, year: int) -> tuple:
        """Get first and last day of a month."""
        first_day = datetime(year, month, 1).date()
        last_day = datetime(year, month, calendar.monthrange(year, month)[1]).date()
        return first_day, last_day

    def _check_missing_attendance(self, child: Child, month: int, year: int) -> Dict:
        """
        Check for missing IN/OUT attendance records.

        Returns dict with:
        - count: Number of days with missing records
        - details: List of missing record details
        """
        from_date, last_day = self._get_month_range(month, year)

        attendance_records = AttendanceLog.objects.filter(
            child=child,
            date_logged__range=(from_date, last_day),
            is_active=True
        ).values_list("date_logged", "time_logged")

        attendance_dict = {}
        for date_logged, time_logged in attendance_records:
            attendance_dict.setdefault(date_logged, []).append(time_logged)

        cutoff_time = time(15, 0)
        missing_details = []

        for date_logged, time_logs in attendance_dict.items():
            if len(time_logs) == 1:
                single_time = time_logs[0]
                missing_type = "IN" if single_time > cutoff_time else "OUT"
                missing_details.append({
                    "date": date_logged.strftime("%Y-%m-%d"),
                    "missing_type": missing_type,
                })

        return {
            "count": len(missing_details),
            "details": missing_details
        }

    def validate_child_for_memo(self, child: Child, month: int, year: int) -> Dict:
        """
        Validate if a child can have a memo generated.

        Checks:
        - Pending time adjustment requests (BLOCKING)
        - Package mapping exists (BLOCKING)
        - Enrollment exists (BLOCKING)
        - Missing attendance records (WARNING)

        Args:
            child: Child object to validate
            month: Target month
            year: Target year

        Returns:
            Dict with keys: valid, errors, warnings, can_force
        """
        errors = []
        warnings = []

        prev_month, prev_year = self._get_previous_month(month, year)

        # Check pending time adjustments (BLOCKING - cannot bypass)
        from_date, last_day = self._get_month_range(prev_month, prev_year)
        pending = TimeAdjustmentRequest.objects.filter(
            child=child,
            request_date__range=(from_date, last_day),
            status="PENDING_APPROVAL",
            is_active=True
        ).count()

        if pending > 0:
            errors.append(f"{pending} pending time adjustment(s) for {calendar.month_name[prev_month]} {prev_year}")

        # Check package mapping for previous month (billing period)
        from core.views import get_package_mapping_for_period
        pkg_mapping = get_package_mapping_for_period(child, prev_month, prev_year)
        if not pkg_mapping:
            errors.append(f"No package mapping for {calendar.month_name[prev_month]} {prev_year}")

        # Check package mapping for current month (advance payment)
        curr_pkg_mapping = get_package_mapping_for_period(child, month, year)
        if not curr_pkg_mapping:
            errors.append(f"No package mapping for {calendar.month_name[month]} {year}")

        # Check enrollment
        enrollment = ChildEnrollment.objects.filter(
            child=child,
            status="Approved",
            is_active=True
        ).first()
        if not enrollment:
            errors.append("No approved enrollment")

        # Check missing attendance (WARNING - can be bypassed with force)
        missing = self._check_missing_attendance(child, prev_month, prev_year)
        if missing["count"] > 0:
            warnings.append({
                "message": f"{missing['count']} missing IN/OUT record(s) for {calendar.month_name[prev_month]} {prev_year}",
                "details": missing["details"]
            })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "can_force": len(errors) == 0 and len(warnings) > 0
        }

    def generate_memo_for_child(
        self,
        child: Child,
        month: int,
        year: int,
        force: bool = False
    ) -> Dict:
        """
        Generate memo for a single child.

        Args:
            child: Child object
            month: Target month
            year: Target year
            force: If True, skip attendance validation

        Returns:
            Dict with keys: success, memo_code, amount_due, error
        """
        from core.views import (
            get_package_mapping_for_period,
            calculate_enhanced_three_month_data,
            get_automatic_breakdown_data,
            format_extra_hours_for_display,
            format_holiday_charges_for_display,
        )

        try:
            month_int = int(month)
            year_int = int(year)

            # Validate first
            validation = self.validate_child_for_memo(child, month_int, year_int)

            if not validation["valid"]:
                return {
                    "success": False,
                    "error": "; ".join(validation["errors"]),
                    "memo_code": None,
                    "amount_due": None
                }

            if validation["warnings"] and not force:
                return {
                    "success": False,
                    "error": validation["warnings"][0]["message"],
                    "memo_code": None,
                    "amount_due": None,
                    "requires_force": True
                }

            # Check if memo already exists
            if InvoiceMemo.objects.filter(
                child=child,
                memo_month=month_int,
                memo_year=year_int,
                is_active=True
            ).exists():
                return {
                    "success": False,
                    "error": f"Memo already exists for {calendar.month_name[month_int]} {year_int}",
                    "memo_code": None,
                    "amount_due": None
                }

            # Calculate month positions
            outstanding_month, outstanding_year = self._get_outstanding_month(month_int, year_int)
            previous_month, previous_year = self._get_previous_month(month_int, year_int)

            # Get detailed breakdown for previous month
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
                    notes=f"Batch generated {'(FORCED)' if force else ''} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    user_created=self.user,
                )

                # Extract data
                month1_data = three_month_data["month1"]  # Outstanding
                month2_data = three_month_data["month2"]  # Previous (Calculated)
                month3_data = three_month_data["month3"]  # Current (Advance)

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
                        "batch_generated": True,
                        "forced": force,
                    },
                    user_created=self.user,
                )

                # Create Previous Month Detail (Month 2)
                extra_hours_breakdown = previous_month_breakdown.get("extra_hours_breakdown", [])
                holiday_breakdown = previous_month_breakdown.get("holiday_charges_breakdown", [])

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
                    attendance_percentage=Decimal(str(month2_data.get("attendance_percentage", 0))),
                    is_half_charge_applied=month2_data.get("is_half_charge", False),
                    notes=f"Calculated for {month2_data['name']} - {month2_data.get('days_attended', 0)}/{month2_data.get('expected_days', 22)} days",
                    calculation_details={
                        "type": "calculated",
                        "batch_generated": True,
                        "forced": force,
                        "extra_hours_breakdown": extra_hours_breakdown,
                        "holiday_charges_breakdown": holiday_breakdown,
                        "extra_hours_display_text": format_extra_hours_for_display(extra_hours_breakdown) if extra_hours_breakdown else "",
                        "holiday_charges_display_text": format_holiday_charges_for_display(holiday_breakdown) if holiday_breakdown else "",
                    },
                    user_created=self.user,
                )

                # Create Current Month Detail (Month 3)
                current_detail = InvoiceMemoDetail.objects.create(
                    memo=memo,
                    month_sequence=3,
                    month_type="CURRENT",
                    actual_month=month_int,
                    actual_year=year_int,
                    month_name=month3_data["name"],
                    package_fee=Decimal(str(month3_data.get("package_fee", 0))),
                    extra_hours_charge=Decimal(str(month3_data.get("extra_charges", 0))),
                    holiday_charges=Decimal(str(month3_data.get("holiday_charges", 0))),
                    other_charges=Decimal("0"),
                    discount_applied=Decimal(str(month3_data.get("discount", 0))),
                    other_deductions=Decimal("0"),
                    payments_received=Decimal(str(month3_data.get("payments", 0))),
                    payment_receipts=month3_data.get("payment_details", []),
                    package_name=month3_data.get("package_name", "Normal Package"),
                    expected_days=month3_data.get("expected_days", 22),
                    notes=f"Advance for {month3_data['name']}",
                    calculation_details={
                        "type": "advance",
                        "batch_generated": True,
                        "forced": force,
                    },
                    user_created=self.user,
                )

                # Calculate totals
                memo.calculate_totals()
                memo.save()

            return {
                "success": True,
                "memo_code": memo_code,
                "amount_due": float(memo.net_amount_due),
                "error": None
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "memo_code": None,
                "amount_due": None
            }

    def preview_batch_generation(self, month: int, year: int) -> Dict:
        """
        Preview what would happen in a batch generation.

        Returns summary of eligible children, those that would be skipped, etc.

        Args:
            month: Target month
            year: Target year

        Returns:
            Dict with preview results
        """
        eligible_children = self.get_eligible_children(month, year)
        existing_children = self.get_children_with_existing_memos(month, year)

        results = {
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "total_enrolled": Child.objects.filter(
                is_active=True,
                is_enrolled=True,
                enrollement_approved=True
            ).count(),
            "already_generated": existing_children.count(),
            "eligible_count": eligible_children.count(),
            "ready_to_generate": [],
            "need_attention": [],
            "cannot_generate": [],
        }

        for child in eligible_children:
            validation = self.validate_child_for_memo(child, month, year)

            child_info = {
                "id": child.id,
                "admission_number": child.admission_number,
                "name": f"{child.child_first_name} {child.child_last_name}",
            }

            if validation["valid"] and not validation["warnings"]:
                results["ready_to_generate"].append(child_info)
            elif validation["can_force"]:
                child_info["warnings"] = [w["message"] for w in validation["warnings"]]
                child_info["warning_details"] = validation["warnings"]
                results["need_attention"].append(child_info)
            else:
                child_info["errors"] = validation["errors"]
                results["cannot_generate"].append(child_info)

        return results

    def generate_batch_memos(
        self,
        month: int,
        year: int,
        force: bool = False,
        child_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Generate memos for multiple children.

        Args:
            month: Target month
            year: Target year
            force: If True, skip attendance validation for all
            child_ids: Optional list of specific child IDs to process

        Returns:
            Dict with generation results
        """
        if child_ids:
            children = Child.objects.filter(
                id__in=child_ids,
                is_active=True,
                is_enrolled=True
            )
        else:
            children = self.get_eligible_children(month, year)

        results = {
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "total_processed": 0,
            "generated": 0,
            "skipped": 0,
            "failed": 0,
            "details": {
                "generated": [],
                "skipped": [],
                "failed": [],
            }
        }

        for child in children:
            results["total_processed"] += 1

            child_info = {
                "id": child.id,
                "admission_number": child.admission_number,
                "name": f"{child.child_first_name} {child.child_last_name}",
            }

            # Validate
            validation = self.validate_child_for_memo(child, month, year)

            if not validation["valid"]:
                results["skipped"] += 1
                child_info["reason"] = "; ".join(validation["errors"])
                child_info["type"] = "error"
                results["details"]["skipped"].append(child_info)
                continue

            if validation["warnings"] and not force:
                results["skipped"] += 1
                child_info["reason"] = validation["warnings"][0]["message"]
                child_info["type"] = "warning"
                child_info["can_force"] = True
                results["details"]["skipped"].append(child_info)
                continue

            # Generate
            result = self.generate_memo_for_child(child, month, year, force)

            if result["success"]:
                results["generated"] += 1
                child_info["memo_code"] = result["memo_code"]
                child_info["amount_due"] = result["amount_due"]
                results["details"]["generated"].append(child_info)
            else:
                results["failed"] += 1
                child_info["error"] = result["error"]
                results["details"]["failed"].append(child_info)

        return results
