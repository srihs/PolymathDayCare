"""
Django management command to fix missing ChildEnrollment records.

Finds children who have is_active=True, is_enrolled=True, and have ChildPackageMapping
records but no approved ChildEnrollment record, then creates the missing enrollment.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from core.models import (
    Branch,
    Child,
    ChildEnrollment,
    ChildPackageMapping,
    DayCare,
)


class Command(BaseCommand):
    """
    Management command to create missing ChildEnrollment records for children
    who have package mappings but no enrollment records.
    """

    help = (
        "Fix missing ChildEnrollment records for children who have package mappings "
        "but no approved enrollment records."
    )

    def add_arguments(self, parser):
        """Define command-line arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Preview changes without creating any records.",
        )
        parser.add_argument(
            "--with-packages-only",
            action="store_true",
            dest="with_packages_only",
            default=True,
            help="Only fix children with package mappings (default: True).",
        )
        parser.add_argument(
            "--all-enrolled",
            action="store_true",
            dest="all_enrolled",
            help="Fix all enrolled children, even those without package mappings.",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options["dry_run"]
        with_packages_only = options["with_packages_only"]
        all_enrolled = options["all_enrolled"]

        # If --all-enrolled is specified, override with_packages_only
        if all_enrolled:
            with_packages_only = False

        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(
            self.style.NOTICE("Fix Missing Enrollments Command")
        )
        self.stdout.write(self.style.NOTICE("=" * 60))

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n[DRY RUN MODE] No records will be created.\n")
            )

        # Find children missing enrollments
        children_to_fix = self._find_children_missing_enrollments(with_packages_only)

        if not children_to_fix:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nNo children found with missing enrollment records."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"\nFound {len(children_to_fix)} children with missing enrollments:\n"
            )
        )

        # Display children to be fixed
        for child in children_to_fix:
            self._display_child_info(child)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY RUN] The above enrollments would be created."
                )
            )
            self._display_summary(len(children_to_fix), 0, dry_run=True)
            return

        # Create enrollments
        created_count = self._create_enrollments(children_to_fix)
        self._display_summary(len(children_to_fix), created_count)

    def _find_children_missing_enrollments(self, with_packages_only):
        """
        Find children who are enrolled but have no approved enrollment record.

        Args:
            with_packages_only: If True, only return children with package mappings.

        Returns:
            QuerySet of Child objects missing enrollment records.
        """
        # Subquery to check for approved enrollment
        has_approved_enrollment = ChildEnrollment.objects.filter(
            child=OuterRef("pk"),
            status="APPROVED",
            is_active=True,
        )

        # Base queryset: active, enrolled children without approved enrollment
        queryset = Child.objects.filter(
            is_active=True,
            is_enrolled=True,
        ).exclude(
            Exists(has_approved_enrollment)
        )

        if with_packages_only:
            # Only children with active package mappings
            has_package_mapping = ChildPackageMapping.objects.filter(
                child=OuterRef("pk"),
                is_active=True,
            )
            queryset = queryset.filter(Exists(has_package_mapping))

        return queryset.select_related().prefetch_related(
            "childpackagemapping_set"
        ).order_by("admission_number")

    def _display_child_info(self, child):
        """Display information about a child to be fixed."""
        package_mapping = self._get_latest_package_mapping(child)
        center_info = "N/A"
        branch_info = "N/A"

        if package_mapping:
            # Try to get center from package mapping context
            # Since ChildPackageMapping doesn't have center, we need to find it
            center, branch = self._determine_center_branch(child, package_mapping)
            if center:
                center_info = f"{center.daycare_code} - {center.daycare_name}"
            if branch:
                branch_info = f"{branch.branch_code} - {branch.branch_name}"

        self.stdout.write(
            f"  - {child.admission_number}: {child.child_first_name} {child.child_last_name}"
        )
        self.stdout.write(f"    Admission Date: {child.admission_date}")
        self.stdout.write(f"    Center: {center_info}")
        self.stdout.write(f"    Branch: {branch_info}")
        self.stdout.write("")

    def _get_latest_package_mapping(self, child):
        """Get the most recent active package mapping for a child."""
        return (
            ChildPackageMapping.objects.filter(
                child=child,
                is_active=True,
            )
            .order_by("-effective_from")
            .first()
        )

    def _determine_center_branch(self, child, package_mapping):
        """
        Determine the center and branch for the child.

        Priority:
        1. Existing pending/rejected enrollment's center (if any)
        2. First available center (fallback)

        Args:
            child: The Child instance.
            package_mapping: The ChildPackageMapping instance (unused but kept for API).

        Returns:
            Tuple of (DayCare, Branch) or (None, None).
        """
        # Check for any existing enrollment (even pending/rejected) to get center
        existing_enrollment = (
            ChildEnrollment.objects.filter(child=child)
            .select_related("center", "branch")
            .first()
        )

        if existing_enrollment:
            return existing_enrollment.center, existing_enrollment.branch

        # Fallback: Use first available center
        first_center = (
            DayCare.objects.filter(is_active=True)
            .select_related("branch")
            .first()
        )

        if first_center:
            return first_center, first_center.branch

        return None, None

    def _create_enrollments(self, children):
        """
        Create enrollment records for the given children.

        Args:
            children: QuerySet of Child objects.

        Returns:
            Number of enrollments created.
        """
        created_count = 0

        with transaction.atomic():
            for child in children:
                enrollment = self._create_single_enrollment(child)
                if enrollment:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created enrollment: {enrollment.enrollment_code} "
                            f"for {child.admission_number}"
                        )
                    )

        return created_count

    def _create_single_enrollment(self, child):
        """
        Create a single enrollment record for a child.

        Args:
            child: The Child instance.

        Returns:
            The created ChildEnrollment instance, or None if failed.
        """
        package_mapping = self._get_latest_package_mapping(child)
        center, branch = self._determine_center_branch(child, package_mapping)

        if not center or not branch:
            self.stdout.write(
                self.style.ERROR(
                    f"  ERROR: No center/branch found for {child.admission_number}. "
                    "Skipping."
                )
            )
            return None

        # Generate enrollment code
        enrollment_code = self._generate_enrollment_code(child)

        # Determine enrollment date
        enrollment_date = child.admission_date or date.today()

        # Get discount from package mapping if available
        discount = None
        if package_mapping and package_mapping.discount:
            discount = package_mapping.discount

        try:
            enrollment = ChildEnrollment.objects.create(
                enrollment_code=enrollment_code,
                enrollment_date=enrollment_date,
                child=child,
                branch=branch,
                center=center,
                discount=discount,
                status="APPROVED",
                is_active=True,
                user_created="fix_missing_enrollments",
                user_updated="fix_missing_enrollments",
            )

            # Update child's enrollment_approved flag
            child.enrollement_approved = True
            child.save(update_fields=["enrollement_approved", "date_updated"])

            return enrollment

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"  ERROR: Failed to create enrollment for {child.admission_number}: {e}"
                )
            )
            return None

    def _generate_enrollment_code(self, child):
        """
        Generate a unique enrollment code for a child.

        Format: ENR-{admission_number}-{date}

        Args:
            child: The Child instance.

        Returns:
            A unique enrollment code string.
        """
        base_code = f"ENR-{child.admission_number}-{date.today().strftime('%Y%m%d')}"

        # Check for existing enrollment with same code and make unique if needed
        existing_count = ChildEnrollment.objects.filter(
            enrollment_code__startswith=base_code
        ).count()

        if existing_count > 0:
            return f"{base_code}-{existing_count + 1}"

        return base_code

    def _display_summary(self, total_found, created_count, dry_run=False):
        """Display summary of the operation."""
        self.stdout.write(self.style.NOTICE("\n" + "=" * 60))
        self.stdout.write(self.style.NOTICE("Summary"))
        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(f"  Children missing enrollments found: {total_found}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"  Enrollments to be created: {total_found}")
            )
            self.stdout.write(
                self.style.NOTICE(
                    "\nRun without --dry-run to create the enrollment records."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  Enrollments created: {created_count}")
            )
            failed = total_found - created_count
            if failed > 0:
                self.stdout.write(
                    self.style.ERROR(f"  Enrollments failed: {failed}")
                )

        self.stdout.write("")
