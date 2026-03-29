"""
Service module for generating fee revision letters for parents.

This module handles the PDF generation of official letters notifying parents
about package price changes at Polymath College Daycare.
"""

import io
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db.models import Q, QuerySet

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import AttendanceLog, Child, ChildPackageMapping
from transactions.models import PackagePriceRevision


class FeeRevisionLetterService:
    """
    Service class for generating fee revision notification letters.

    This service handles:
    - Querying eligible children (active attendance in last 2 months)
    - Generating individual PDF letters
    - Generating bulk PDF letters in a single document
    """

    # Letter content configuration
    EFFECTIVE_MONTH = "May"
    EFFECTIVE_YEAR = "2026"
    LETTER_SUBJECT = "Fee Revision Notification"

    # Page layout
    PAGE_WIDTH, PAGE_HEIGHT = A4
    LEFT_MARGIN = 25 * mm
    RIGHT_MARGIN = 25 * mm
    TOP_MARGIN = 20 * mm
    BOTTOM_MARGIN = 10 * mm  # Reduced to push footer closer to edge

    def __init__(self):
        """Initialize the service with styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles for the letter."""
        # Heading style
        self.styles.add(
            ParagraphStyle(
                name="LetterHeading",
                parent=self.styles["Heading1"],
                fontSize=14,
                spaceAfter=6,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#1a365d"),
            )
        )

        # Tagline style
        self.styles.add(
            ParagraphStyle(
                name="Tagline",
                parent=self.styles["Normal"],
                fontSize=10,
                spaceAfter=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#4a5568"),
                fontName="Times-Italic",
            )
        )

        # Date style (right-aligned)
        self.styles.add(
            ParagraphStyle(
                name="LetterDate",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=20,
                spaceAfter=20,
                alignment=TA_RIGHT,
            )
        )

        # Salutation style
        self.styles.add(
            ParagraphStyle(
                name="Salutation",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=12,
                spaceAfter=12,
                alignment=TA_LEFT,
            )
        )

        # Body paragraph style
        self.styles.add(
            ParagraphStyle(
                name="BodyParagraph",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=8,
                spaceAfter=8,
                alignment=TA_JUSTIFY,
                leading=16,
            )
        )

        # Details heading style
        self.styles.add(
            ParagraphStyle(
                name="DetailsHeading",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=12,
                spaceAfter=6,
                fontName="Helvetica-Bold",
            )
        )

        # Details row style
        self.styles.add(
            ParagraphStyle(
                name="DetailsRow",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=4,
                spaceAfter=4,
                leftIndent=20,
            )
        )

        # Closing style
        self.styles.add(
            ParagraphStyle(
                name="Closing",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=20,
                spaceAfter=6,
            )
        )

        # Signature style
        self.styles.add(
            ParagraphStyle(
                name="Signature",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceBefore=40,
                spaceAfter=6,
                fontName="Helvetica-Bold",
            )
        )

        # Footer style
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#4a5568"),
            )
        )

    @staticmethod
    def get_children_with_active_attendance(
        only_with_pending_revisions: bool = True,
    ) -> QuerySet[Child]:
        """
        Query children with active attendance in the last 2 months.

        Args:
            only_with_pending_revisions: If True, only return children whose
                packages have pending (unapplied) price revisions

        Returns:
            QuerySet[Child]: Queryset of eligible children with related data

        Business Logic:
            - Child must be active (is_active=True)
            - Child must be enrolled (is_enrolled=True)
            - Enrollment must be approved (enrollement_approved=True)
            - Must have at least one attendance log in the last 2 months
            - If only_with_pending_revisions is True, child's package must
              have a pending price revision (is_applied=False)
        """
        two_months_ago = date.today() - timedelta(days=60)

        # Get children with attendance in the last 2 months
        children_with_attendance = (
            AttendanceLog.objects.filter(
                date_logged__gte=two_months_ago, is_active=True
            )
            .values_list("child_id", flat=True)
            .distinct()
        )

        # Filter active, enrolled children with approved enrollment
        eligible_children = (
            Child.objects.filter(
                id__in=children_with_attendance,
                is_active=True,
                is_enrolled=True,
                enrollement_approved=True,
            )
            .select_related()
            .order_by("child_first_name", "child_last_name")
        )

        if only_with_pending_revisions:
            # Get packages with pending revisions
            pending_fixed_packages = PackagePriceRevision.objects.filter(
                is_active=True, is_applied=False, fixed_package__isnull=False
            ).values_list("fixed_package_id", flat=True)

            pending_flex_packages = PackagePriceRevision.objects.filter(
                is_active=True, is_applied=False, flex_package__isnull=False
            ).values_list("flex_package_id", flat=True)

            # Get children who have mappings to these packages
            children_with_pending_revisions = ChildPackageMapping.objects.filter(
                Q(
                    normal_package_id__in=pending_fixed_packages,
                    is_active=True,
                )
                | Q(
                    flex_package_id__in=pending_flex_packages,
                    is_active=True,
                )
            ).values_list("child_id", flat=True)

            eligible_children = eligible_children.filter(
                id__in=children_with_pending_revisions
            )

        return eligible_children

    @staticmethod
    def get_child_package_info(child: Child) -> dict:
        """
        Get package information for a child including revised price.

        Args:
            child: The Child instance

        Returns:
            dict: Dictionary containing package details and revised price

        Business Logic:
            - Gets the current active package mapping for the child
            - Checks for pending price revisions for the package
            - Returns the new price if a revision exists, otherwise current price
        """
        package_info = {
            "package_name": "N/A",
            "current_price": Decimal("0.00"),
            "revised_price": Decimal("0.00"),
            "has_revision": False,
            "package_type": None,
        }

        # Get the current active package mapping
        current_mapping = (
            ChildPackageMapping.objects.filter(
                child=child, is_active=True, effective_to__isnull=True
            )
            .select_related("normal_package", "flex_package")
            .first()
        )

        if not current_mapping:
            # Try to get any active mapping
            current_mapping = (
                ChildPackageMapping.objects.filter(child=child, is_active=True)
                .select_related("normal_package", "flex_package")
                .order_by("-effective_from")
                .first()
            )

        if current_mapping:
            # Determine which package is active
            if current_mapping.normal_package:
                package = current_mapping.normal_package
                package_info["package_name"] = package.package_name
                package_info["current_price"] = package.package_total
                package_info["package_type"] = "fixed"

                # Check for pending price revision
                pending_revision = PackagePriceRevision.objects.filter(
                    fixed_package=package, is_active=True, is_applied=False
                ).first()

                if pending_revision:
                    package_info["revised_price"] = pending_revision.new_price
                    package_info["has_revision"] = True
                else:
                    package_info["revised_price"] = package.package_total

            elif current_mapping.flex_package:
                package = current_mapping.flex_package
                package_info["package_name"] = package.package_name
                package_info["current_price"] = package.package_total
                package_info["package_type"] = "flex"

                # Check for pending price revision
                pending_revision = PackagePriceRevision.objects.filter(
                    flex_package=package, is_active=True, is_applied=False
                ).first()

                if pending_revision:
                    package_info["revised_price"] = pending_revision.new_price
                    package_info["has_revision"] = True
                else:
                    package_info["revised_price"] = package.package_total

        return package_info

    def _get_logo_path(self) -> Optional[str]:
        """Get the path to the Polymath College logo."""
        logo_path = os.path.join(
            settings.BASE_DIR, "static", "assets", "images", "college.png"
        )
        if os.path.exists(logo_path):
            return logo_path
        return None

    def _get_parent_name(self, child: Child) -> str:
        """
        Get the parent/guardian name for salutation.

        Args:
            child: The Child instance

        Returns:
            str: Formatted parent name for salutation (with title prefixes removed)
        """
        # Prefer father's name, fallback to mother's name
        if child.fathers_name and child.fathers_name.strip():
            name = child.fathers_name.strip()
        elif child.mothers_name and child.mothers_name.strip():
            name = child.mothers_name.strip()
        else:
            return "Parent/Guardian"

        # Remove common title prefixes if present (case-insensitive)
        title_prefixes = [
            "Mr.", "Mr ", "Mrs.", "Mrs ", "Ms.", "Ms ",
            "Dr.", "Dr ", "Prof.", "Prof ",
            "Mr./Mrs.", "Mr./Mrs ", "Mr/Mrs.", "Mr/Mrs ",
        ]
        for prefix in title_prefixes:
            if name.lower().startswith(prefix.lower()):
                name = name[len(prefix):].strip()
                break

        return name

    def _build_letter_content(
        self, child: Child, package_info: dict, letter_date: date
    ) -> list:
        """
        Build the letter content as a list of Platypus flowables.

        Args:
            child: The Child instance
            package_info: Dictionary with package details
            letter_date: Date for the letter

        Returns:
            list: List of Platypus flowables for the PDF
        """
        story = []

        # Header with logo - maintaining aspect ratio (300x66 = 4.55:1)
        logo_path = self._get_logo_path()
        if logo_path:
            try:
                # Logo is 1000x225 pixels, aspect ratio ~4.44:1
                # Set width to 45mm to fit within margins
                logo_width = 45 * mm
                logo_height = logo_width / 4.44  # Maintain aspect ratio
                logo = Image(logo_path, width=logo_width, height=logo_height)
                logo.hAlign = "RIGHT"
                story.append(logo)
            except Exception:
                # If logo fails, just add the text header
                story.append(
                    Paragraph("POLYMATH COLLEGE", self.styles["LetterHeading"])
                )
        else:
            story.append(Paragraph("POLYMATH COLLEGE", self.styles["LetterHeading"]))

        story.append(Spacer(1, 6 * mm))

        # Date (left-aligned)
        formatted_date = letter_date.strftime("%d %B %Y")
        story.append(Paragraph(formatted_date, self.styles["Salutation"]))

        story.append(Spacer(1, 4 * mm))

        # Salutation
        parent_name = self._get_parent_name(child)
        story.append(
            Paragraph(f"Dear Mr/Ms {parent_name},", self.styles["Salutation"])
        )

        story.append(Spacer(1, 4 * mm))

        # Body paragraph 1
        body_para1 = (
            "Over the past two years, there has been a steady increase in operational costs. "
            "Throughout this period, the management has made every effort to absorb these expenses "
            "without passing on the burden on to parents, and we sincerely appreciate your continued "
            "trust and support."
        )
        story.append(Paragraph(body_para1, self.styles["BodyParagraph"]))

        # Body paragraph 2
        body_para2 = (
            f"However, we have now reached a point where it is no longer possible to maintain the "
            f"quality of our services without revising the monthly fee. Therefore, with effect from "
            f"<b>{self.EFFECTIVE_MONTH} {self.EFFECTIVE_YEAR}</b>, the daycare fee will be increased."
        )
        story.append(Paragraph(body_para2, self.styles["BodyParagraph"]))

        # Body paragraph 3
        body_para3 = (
            "We truly value your understanding and continued partnership. Please be assured that "
            "the management and staff of Polymath remain fully committed to providing your child "
            "with a safe, secure, and nurturing environment each day, until he or she is collected."
        )
        story.append(Paragraph(body_para3, self.styles["BodyParagraph"]))

        # Body paragraph 4 - Thank you
        body_para4 = "Thank you once again for your continued support."
        story.append(Paragraph(body_para4, self.styles["BodyParagraph"]))

        story.append(Spacer(1, 10 * mm))

        # Details section as table for better alignment
        child_full_name = f"{child.child_first_name} {child.child_last_name}"
        revised_price = package_info["revised_price"]
        formatted_price = f"Rs. {revised_price:,.2f}"

        # Create details table
        details_data = [
            [
                Paragraph("<b>Name of the student</b>", self.styles["DetailsRow"]),
                Paragraph(f": {child_full_name}", self.styles["DetailsRow"]),
            ],
            [
                Paragraph("<b>Monthly package</b>", self.styles["DetailsRow"]),
                Paragraph(f": {package_info['package_name']}", self.styles["DetailsRow"]),
            ],
            [
                Paragraph("<b>Revised fee</b>", self.styles["DetailsRow"]),
                Paragraph(f": {formatted_price}", self.styles["DetailsRow"]),
            ],
        ]

        details_table = Table(
            details_data,
            colWidths=[45 * mm, 100 * mm],
            hAlign="LEFT",
        )
        details_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(details_table)

        # Signature section
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph("Principal", self.styles["Closing"]))

        # Footer with address - pushed to bottom edge
        story.append(Spacer(1, 35 * mm))

        # Footer line
        footer_line = Table(
            [[" "]],
            colWidths=[self.PAGE_WIDTH - self.LEFT_MARGIN - self.RIGHT_MARGIN],
        )
        footer_line.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#666666")),
                ]
            )
        )
        story.append(footer_line)
        story.append(Spacer(1, 2 * mm))

        # Footer text - exact from document
        footer_line1 = "452/3, High Level Road, Nawinna, Maharagama."
        footer_line2 = "0112 803 545 | office@polymath.edu.lk | www.polymathcollege.com"
        story.append(Paragraph(footer_line1, self.styles["Footer"]))
        story.append(Paragraph(footer_line2, self.styles["Footer"]))

        return story

    def generate_individual_letter(
        self, child: Child, letter_date: Optional[date] = None
    ) -> io.BytesIO:
        """
        Generate a PDF letter for a single child.

        Args:
            child: The Child instance
            letter_date: Date for the letter (defaults to today)

        Returns:
            io.BytesIO: Buffer containing the PDF data
        """
        if letter_date is None:
            letter_date = date.today()

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.LEFT_MARGIN,
            rightMargin=self.RIGHT_MARGIN,
            topMargin=self.TOP_MARGIN,
            bottomMargin=self.BOTTOM_MARGIN,
        )

        # Get package info
        package_info = self.get_child_package_info(child)

        # Build letter content
        story = self._build_letter_content(child, package_info, letter_date)

        # Build PDF
        doc.build(story)

        buffer.seek(0)
        return buffer

    def generate_bulk_letters(
        self, children: QuerySet[Child], letter_date: Optional[date] = None
    ) -> io.BytesIO:
        """
        Generate a single PDF containing letters for multiple children.

        Each letter will be on a separate page.

        Args:
            children: QuerySet of Child instances
            letter_date: Date for the letters (defaults to today)

        Returns:
            io.BytesIO: Buffer containing the PDF data
        """
        if letter_date is None:
            letter_date = date.today()

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=self.LEFT_MARGIN,
            rightMargin=self.RIGHT_MARGIN,
            topMargin=self.TOP_MARGIN,
            bottomMargin=self.BOTTOM_MARGIN,
        )

        story = []
        children_list = list(children)

        for idx, child in enumerate(children_list):
            # Get package info
            package_info = self.get_child_package_info(child)

            # Build letter content
            letter_content = self._build_letter_content(child, package_info, letter_date)
            story.extend(letter_content)

            # Add page break if not the last child
            if idx < len(children_list) - 1:
                from reportlab.platypus import PageBreak

                story.append(PageBreak())

        # Build PDF
        doc.build(story)

        buffer.seek(0)
        return buffer

    @staticmethod
    def get_children_summary() -> list:
        """
        Get a summary of eligible children for letter generation.

        Only returns children whose packages have pending (unapplied) price
        revisions. Once revisions are applied, children are removed from
        this list since letters should have already been sent.

        Returns:
            list: List of dictionaries with child and package info
        """
        children = FeeRevisionLetterService.get_children_with_active_attendance()
        summary = []

        for child in children:
            package_info = FeeRevisionLetterService.get_child_package_info(child)

            # Only include children with pending (unapplied) price revisions
            if package_info["has_revision"]:
                summary.append(
                    {
                        "id": child.id,
                        "admission_number": child.admission_number,
                        "name": f"{child.child_first_name} {child.child_last_name}",
                        "parent_name": child.fathers_name or child.mothers_name or "N/A",
                        "package_name": package_info["package_name"],
                        "current_price": float(package_info["current_price"]),
                        "revised_price": float(package_info["revised_price"]),
                        "has_revision": package_info["has_revision"],
                    }
                )

        return summary
