"""
Custom template filters for number formatting.

Provides filters for formatting numbers with thousand separators
and currency display in the daycare management system.
"""

from decimal import Decimal

from django import template

register = template.Library()


@register.filter(name="format_currency")
def format_currency(value, decimal_places=2):
    """
    Format a number as currency with thousand separators.

    Args:
        value: The numeric value to format
        decimal_places: Number of decimal places (default: 2)

    Returns:
        Formatted string with Rs. prefix and thousand separators

    Example:
        {{ 1234567.89|format_currency }} -> "Rs. 1,234,567.89"
        {{ 1000|format_currency:0 }} -> "Rs. 1,000"
    """
    try:
        if value is None:
            return "Rs. 0.00"

        # Convert to Decimal for precision
        if isinstance(value, str):
            value = Decimal(value)
        elif not isinstance(value, Decimal):
            value = Decimal(str(value))

        # Format with thousand separators
        formatted = f"{value:,.{decimal_places}f}"
        return f"Rs. {formatted}"
    except (ValueError, TypeError, decimal.InvalidOperation):
        return "Rs. 0.00"


@register.filter(name="format_number")
def format_number(value, decimal_places=0):
    """
    Format a number with thousand separators.

    Args:
        value: The numeric value to format
        decimal_places: Number of decimal places (default: 0)

    Returns:
        Formatted string with thousand separators

    Example:
        {{ 1234567|format_number }} -> "1,234,567"
        {{ 1234.56|format_number:2 }} -> "1,234.56"
    """
    try:
        if value is None:
            return "0"

        # Convert to float for formatting
        num_value = float(value)

        # Format with thousand separators
        if decimal_places > 0:
            return f"{num_value:,.{decimal_places}f}"
        else:
            return f"{int(num_value):,}"
    except (ValueError, TypeError):
        return "0"


# Import decimal for exception handling
import decimal
