"""
Django management command to correct historical invoice memos whose vacation
month was billed with the normal (non-vacation) package.

Background: the memo calculation was made vacation-aware (a month that is a
"vacation month" for the child bills the vacation package). Memos generated
before that fix stored the normal-package figures. This command recomputes ONLY
the vacation-month detail(s) of each affected memo from the current engine and
updates that detail's charges in place.

It is intentionally SURGICAL:
  * Only the vacation-month detail (PREVIOUS/calculated or CURRENT/advance) is
    touched. The OUTSTANDING detail and every payment_received value are left
    exactly as-is. This avoids the failure mode of a full regeneration, which
    recomputes OUTSTANDING from the prior memo and wipes manually-entered
    brought-forward balances to zero.
  * Idempotent: a detail already matching the engine is skipped.

Run with --dry-run first (default) to review the scope, then --apply.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import InvoiceMemo
from core.views import (
    calculate_enhanced_three_month_data,
    get_package_mapping_for_period,
    is_vacation_month_for_period,
)

TAG = "vacation-pkg-fix"


class Command(BaseCommand):
    help = (
        "Correct historical memos whose vacation month was billed with the "
        "normal package. Surgical: only the vacation-month detail is updated; "
        "OUTSTANDING balances and all payments are preserved."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply",
            help="Commit the changes. Without this flag the command is a dry-run.",
        )
        parser.add_argument(
            "--memo-code",
            dest="memo_code",
            default=None,
            help="Limit to a single memo code (e.g. MO0044) for targeted testing.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        memo_code = options["memo_code"]
        stamp = timezone.now().strftime("%Y-%m-%d %H:%M")

        qs = InvoiceMemo.objects.filter(is_active=True).select_related("child")
        if memo_code:
            qs = qs.filter(memo_code=memo_code)
        qs = qs.order_by("memo_year", "memo_month", "id")

        changed = []
        errors = 0

        # Wrap the whole pass in one transaction. For a dry-run we roll it back
        # via set_rollback so nothing is ever persisted.
        with transaction.atomic():
            for memo in qs:
                try:
                    data = calculate_enhanced_three_month_data(
                        memo.child, memo.memo_month, memo.memo_year
                    )
                except Exception as exc:  # noqa: BLE001 - report and skip
                    errors += 1
                    self.stderr.write(f"  ! {memo.memo_code}: calc error: {exc}")
                    continue

                details = {d.month_sequence: d for d in memo.month_details.all()}
                before = memo.net_amount_due or Decimal("0")
                touched = False

                for seq, key in ((2, "month2"), (3, "month3")):
                    d = details.get(seq)
                    if not d:
                        continue
                    mp = get_package_mapping_for_period(
                        memo.child, d.actual_month, d.actual_year
                    )
                    if not mp or not is_vacation_month_for_period(
                        memo.child, mp, d.actual_month, d.actual_year
                    ):
                        continue

                    new_pkg = Decimal(str(data[key].get("package_fee", 0)))
                    new_hol = Decimal(str(data[key].get("holiday_charges", 0)))
                    if new_pkg == (d.package_fee or 0) and new_hol == (
                        d.holiday_charges or 0
                    ):
                        continue  # already correct

                    new_extra = Decimal(str(data[key].get("extra_charges", 0)))
                    if seq == 3:
                        # advance month does not expose a discount key directly
                        new_disc = Decimal(
                            str(data["month3"].get("package_fee", 0))
                        ) - Decimal(str(data["month3"].get("charge", 0)))
                    else:
                        new_disc = Decimal(str(data[key].get("discount", 0)))

                    d.package_fee = new_pkg
                    d.holiday_charges = new_hol
                    d.extra_hours_charge = new_extra
                    d.discount_applied = new_disc
                    if d.month_type == "PREVIOUS":
                        d.days_attended = data[key].get("days_attended", 0)
                        d.expected_days = data[key].get("expected_days", 22)
                        d.attendance_percentage = Decimal(
                            str(data[key].get("attendance_percentage", 0))
                        )
                        d.is_half_charge_applied = data[key].get("is_half_charge", False)
                    d.calculate_totals()
                    d.user_updated = TAG
                    d.save()
                    touched = True

                if touched:
                    memo.calculate_totals()
                    memo.notes = f"{memo.notes or ''}\n[VACATION-PKG-FIX {stamp}]"
                    memo.user_updated = TAG
                    memo.save()
                    memo.refresh_from_db()
                    changed.append(
                        (memo.memo_code, memo.child.admission_number, before, memo.net_amount_due)
                    )

            for code, adm, b, a in changed:
                self.stdout.write(
                    f"  {code:8} {adm:8} net {b:>12} -> {a:>12} (delta {a - b:>+12})"
                )
            total_delta = sum((a - b) for _, _, b, a in changed)
            mode = "APPLIED" if apply else "DRY-RUN (rolled back)"
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{mode}] memos changed: {len(changed)} | calc errors: {errors} "
                    f"| net delta: {total_delta:+}"
                )
            )

            if not apply:
                transaction.set_rollback(True)
                self.stdout.write(
                    "Dry-run only. Re-run with --apply to commit. "
                    "Back up the database before applying in production."
                )
