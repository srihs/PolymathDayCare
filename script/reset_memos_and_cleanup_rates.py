#!/usr/bin/env python
"""
One-off maintenance script for the PolymathDayCare site.

STEP 1 - Clear all billing documents and reset their identity:
    Deletes every InvoiceMemo, InvoiceMemoDetail, PaymentTransaction (receipt)
    and MemoRegenerationRequest, then resets each table's AUTO_INCREMENT to 1
    (done via TRUNCATE, which both empties the table and resets the counter).

STEP 2 - additional_rates_upto530 cleanup:
    De-duplicates / closes overlapping ExtraHoursUpTo530 rate rows so at most one
    rate is active per hour on any given date (exact duplicates are deactivated;
    an older overlapping rate is ended the day before the newer one starts).

SAFETY:
    * Dry-run by default - it only reports what it would do and changes nothing.
    * Pass --apply to actually execute.
    * STEP 1 uses TRUNCATE, which is irreversible and cannot be rolled back.
      BACK UP THE DATABASE BEFORE RUNNING WITH --apply.

USAGE (inside the web/app container - NOT the db container):
    # dry-run of everything (safe, shows what would happen)
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py

    # execute everything (wipe memos/receipts + clean rates)
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py --apply

    # ONLY clean the upto-5:30 rates, keep all memos/receipts:
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py --rates-only           # dry-run
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py --rates-only --apply   # execute

    # ONLY wipe memos/receipts, leave rates alone:  add --memos-only

    # EMPTY the rate tables entirely (after-5:30 + upto-5:30 + history) so you can
    # re-enter rates from scratch. Memos are NOT touched:
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py --clear-rates           # dry-run
    docker exec <web-container> python /app/script/reset_memos_and_cleanup_rates.py --clear-rates --apply   # execute
"""

import os
import sys

import django

# Ensure the project root (parent of this script/ folder) is importable so that
# the daycareSystem settings module can be found regardless of CWD.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "daycareSystem.settings")
django.setup()

from collections import defaultdict  # noqa: E402
from datetime import date, timedelta  # noqa: E402

from django.db import connection, transaction  # noqa: E402

from core.models import (  # noqa: E402
    ExtraChargesHistory,
    ExtraHoursAfter530,
    ExtraHoursUpTo530,
    InvoiceMemo,
    InvoiceMemoDetail,
    PaymentTransaction,
)

try:
    from core.models import MemoRegenerationRequest
except Exception:  # pragma: no cover - model may not exist in older schemas
    MemoRegenerationRequest = None

APPLY = "--apply" in sys.argv
RATES_ONLY = "--rates-only" in sys.argv  # skip STEP 1 (memo/receipt wipe)
MEMOS_ONLY = "--memos-only" in sys.argv  # skip STEP 2 (rate cleanup)
# Empty the rate tables entirely (after-5:30 + upto-5:30 + their change history)
# and reset their AUTO_INCREMENT to 1, so the rates can be re-entered from
# scratch. When set, ONLY this runs (no memo wipe, no de-dup).
CLEAR_RATES = "--clear-rates" in sys.argv

# Order matters only for readability; FK checks are disabled during TRUNCATE.
MEMO_TABLES = [
    "dc_payment_transactions",
    "dc_invoice_memo_details",
    "dc_memo_regeneration_request",
    "dc_invoice_memos",
]

# Rate tables to empty for --clear-rates (history first; FK checks off anyway).
RATE_TABLES = [
    "dc_extra_charges_history",
    "dc_extra_charge_after_530",
    "dc_extra_charges_till_530",
]


def _auto_increment(table):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT AUTO_INCREMENT FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [table],
        )
        row = cur.fetchone()
    return row[0] if row else None


def step1_clear_memos():
    print("\n=== STEP 1: clear memos + receipts, reset identity to 1 ===")
    print("Current counts:")
    print("  payments (receipts):", PaymentTransaction.objects.count())
    print("  memo_details        :", InvoiceMemoDetail.objects.count())
    print("  memos               :", InvoiceMemo.objects.count())
    if MemoRegenerationRequest:
        print("  regen_requests      :", MemoRegenerationRequest.objects.count())

    if not APPLY:
        print(f"DRY-RUN: would TRUNCATE {MEMO_TABLES} and reset AUTO_INCREMENT to 1.")
        return

    with connection.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in MEMO_TABLES:
            cur.execute(f"TRUNCATE TABLE `{t}`")
            print(f"  truncated {t}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

    print("After:")
    print("  payments (receipts):", PaymentTransaction.objects.count())
    print("  memo_details        :", InvoiceMemoDetail.objects.count())
    print("  memos               :", InvoiceMemo.objects.count())
    for t in MEMO_TABLES:
        print(f"  AUTO_INCREMENT[{t}] = {_auto_increment(t)}")


def step2_cleanup_rates():
    print("\n=== STEP 2: additional_rates_upto530 dedupe / close overlaps ===")
    rows = list(ExtraHoursUpTo530.objects.filter(is_active=True))
    by_hour = defaultdict(list)
    for r in rows:
        by_hour[r.hour_number].append(r)

    changes = []
    with transaction.atomic():
        for hour, rates in by_hour.items():
            if len(rates) < 2:
                continue
            rates.sort(key=lambda r: (r.effective_from or date.min, r.id))
            for i in range(len(rates) - 1):
                cur, nxt = rates[i], rates[i + 1]
                exact_dup = (
                    cur.effective_from == nxt.effective_from
                    and cur.effective_to == nxt.effective_to
                    and cur.extra_rate == nxt.extra_rate
                )
                if exact_dup:
                    dup = nxt if nxt.id > cur.id else cur
                    changes.append(
                        f"  hour {hour}: deactivate id {dup.id} (exact duplicate)"
                    )
                    dup.is_active = False
                    dup.user_updated = "rate-dedupe"
                    dup.save()
                elif nxt.effective_from and (
                    cur.effective_to is None or cur.effective_to >= nxt.effective_from
                ):
                    new_to = nxt.effective_from - timedelta(days=1)
                    changes.append(
                        f"  hour {hour}: id {cur.id} effective_to "
                        f"{cur.effective_to} -> {new_to} (close before id {nxt.id})"
                    )
                    cur.effective_to = new_to
                    cur.user_updated = "rate-dedupe"
                    cur.save()

        # verify no remaining overlaps
        overlaps = 0
        active = list(ExtraHoursUpTo530.objects.filter(is_active=True))
        bh = defaultdict(list)
        for r in active:
            bh[r.hour_number].append(r)
        for hour, rs in bh.items():
            rs.sort(key=lambda r: (r.effective_from or date.min, r.id))
            for i in range(len(rs) - 1):
                a, b = rs[i], rs[i + 1]
                if a.effective_to is None or (
                    b.effective_from and a.effective_to >= b.effective_from
                ):
                    overlaps += 1

        for c in changes:
            print(c)
        if not changes:
            print("  no duplicates/overlaps found")
        print(f"  remaining overlaps after cleanup: {overlaps}")

        if not APPLY:
            transaction.set_rollback(True)


def step_clear_rate_tables():
    print("\n=== CLEAR RATES: empty rate tables + reset identity to 1 ===")
    print("Current counts:")
    print("  after-5:30 rates (dc_extra_charge_after_530):", ExtraHoursAfter530.objects.count())
    print("  upto-5:30 rates  (dc_extra_charges_till_530):", ExtraHoursUpTo530.objects.count())
    print("  rate history     (dc_extra_charges_history) :", ExtraChargesHistory.objects.count())

    if not APPLY:
        print(f"DRY-RUN: would TRUNCATE {RATE_TABLES} and reset AUTO_INCREMENT to 1.")
        return

    with connection.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in RATE_TABLES:
            cur.execute(f"TRUNCATE TABLE `{t}`")
            print(f"  truncated {t}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

    print("After:")
    print("  after-5:30 rates:", ExtraHoursAfter530.objects.count())
    print("  upto-5:30 rates :", ExtraHoursUpTo530.objects.count())
    print("  rate history    :", ExtraChargesHistory.objects.count())
    for t in RATE_TABLES:
        print(f"  AUTO_INCREMENT[{t}] = {_auto_increment(t)}")


def main():
    print("MODE:", "APPLY (changes WILL be committed)" if APPLY else "DRY-RUN (no changes)")

    # --clear-rates is a standalone action: empty the rate tables only.
    if CLEAR_RATES:
        print("SCOPE: --clear-rates (ONLY empties rate tables; memos untouched)")
        step_clear_rate_tables()
        if not APPLY:
            print(
                "\nDRY-RUN complete. Re-run with --apply to execute. "
                "TRUNCATE is irreversible — BACK UP THE DATABASE FIRST."
            )
        else:
            print("\nDONE. Rate tables are empty; you can now re-enter the rates.")
        return

    if RATES_ONLY:
        print("SCOPE: --rates-only (STEP 1 memo/receipt wipe is SKIPPED)")
    elif MEMOS_ONLY:
        print("SCOPE: --memos-only (STEP 2 rate cleanup is SKIPPED)")

    if not RATES_ONLY:
        step1_clear_memos()
    if not MEMOS_ONLY:
        step2_cleanup_rates()

    if not APPLY:
        print(
            "\nDRY-RUN complete. Re-run with --apply to execute. "
            "BACK UP THE DATABASE FIRST (STEP 1 TRUNCATE is irreversible)."
        )
    else:
        print("\nDONE.")


if __name__ == "__main__":
    main()
