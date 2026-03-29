"""
Transaction models for the PolymathDayCare system.

This module contains models related to financial transactions and pricing operations.
"""

from django.db import models

from core.models import BaseClass, FixedPackage, FlexPackages


class PackagePriceRevision(BaseClass):
    """
    Tracks price revisions for daycare packages.

    This model stores proposed and applied price changes for both fixed and flex packages,
    including the effective date, percentage change calculations, and application status.
    Used for audit trails and scheduled price updates.
    """

    # Package references - one of these should be set
    fixed_package = models.ForeignKey(
        FixedPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="price_revisions",
        help_text="The fixed package being updated",
    )
    flex_package = models.ForeignKey(
        FlexPackages,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="price_revisions",
        help_text="The flex package being updated",
    )

    # Price information
    current_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="The current price at time of revision creation",
    )
    new_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="The new price to apply",
    )
    percentage_change = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="The percentage change used (optional)",
    )

    # Effective date
    effective_from = models.DateField(
        help_text="When the price change takes effect",
    )

    # Application status
    is_applied = models.BooleanField(
        default=False,
        help_text="Whether the price has been applied to the package",
    )
    applied_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the price was actually applied",
    )

    # Notes
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Optional notes about this price revision",
    )

    class Meta:
        verbose_name = "Package Price Revision"
        verbose_name_plural = "Package Price Revisions"
        db_table = "dc_package_price_revisions"
        ordering = ["-effective_from", "-date_created"]
        indexes = [
            models.Index(fields=["effective_from"]),
            models.Index(fields=["is_applied"]),
            models.Index(fields=["fixed_package", "effective_from"]),
            models.Index(fields=["flex_package", "effective_from"]),
        ]

    def __str__(self):
        if self.fixed_package:
            package_name = self.fixed_package.package_name
        elif self.flex_package:
            package_name = self.flex_package.package_name
        else:
            package_name = "Unknown"
        return f"{package_name} - {self.effective_from}"

    @property
    def package(self):
        """Return the associated package (fixed or flex)."""
        return self.fixed_package or self.flex_package

    @property
    def package_name(self):
        """Return the name of the associated package."""
        pkg = self.package
        return pkg.package_name if pkg else "Unknown"

    @property
    def calculated_percentage_change(self):
        """Calculate the percentage change between current and new price."""
        if self.current_price and self.current_price != 0:
            from decimal import Decimal

            change = ((self.new_price - self.current_price) / self.current_price) * 100
            return Decimal(str(change)).quantize(Decimal("0.01"))
        return Decimal("0.00")

    @property
    def price_difference(self):
        """Calculate the absolute price difference."""
        return self.new_price - self.current_price

    @property
    def is_price_increase(self):
        """Check if this revision represents a price increase."""
        return self.new_price > self.current_price
