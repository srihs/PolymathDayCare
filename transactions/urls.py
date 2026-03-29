"""
URL patterns for the transactions app.

This module contains URL routing for package price changes,
fee revision letters, and related operations.
"""

from django.urls import path

from . import views

app_name = "transactions"

urlpatterns = [
    # Package Price Changes - Main page
    path(
        "package_price_changes/",
        views.get_package_price_changes,
        name="package_price_changes",
    ),
    # JSON endpoints for DataTables
    path(
        "packages_for_price_change_js/",
        views.get_packages_for_price_change_js,
        name="packages_for_price_change_js",
    ),
    path(
        "pending_price_revisions_js/",
        views.get_pending_price_revisions_js,
        name="pending_price_revisions_js",
    ),
    path(
        "price_revision_history_js/",
        views.get_price_revision_history_js,
        name="price_revision_history_js",
    ),
    # Save operations
    path(
        "save_bulk_price_change/",
        views.save_bulk_price_change,
        name="save_bulk_price_change",
    ),
    path(
        "save_individual_price_change/",
        views.save_individual_price_change,
        name="save_individual_price_change",
    ),
    # Apply and cancel operations
    path(
        "apply_pending_price_changes/",
        views.apply_pending_price_changes,
        name="apply_pending_price_changes",
    ),
    path(
        "cancel_price_revision/",
        views.cancel_price_revision,
        name="cancel_price_revision",
    ),
    # Fee Revision Letter Generation
    path(
        "generate_parents_letter/",
        views.get_generate_parents_letter,
        name="generate_parents_letter",
    ),
    path(
        "eligible_children_js/",
        views.get_eligible_children_js,
        name="eligible_children_js",
    ),
    path(
        "generate_individual_letter/<int:child_id>/",
        views.generate_individual_letter_pdf,
        name="generate_individual_letter",
    ),
    path(
        "generate_bulk_letters/",
        views.generate_bulk_letters_pdf,
        name="generate_bulk_letters",
    ),
    path(
        "preview_letter/<int:child_id>/",
        views.preview_letter_pdf,
        name="preview_letter",
    ),
]
