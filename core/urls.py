from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("home/", views.index, name="home"),
    path("", views.index, name="home"),
    path("login/", views.UserLogin, name="login"),
    path("logout/", views.UserLogOut, name="logout"),
    path(
        "public_holidays/",
        views.getPublicHolidays,
        name="public_holidays",
    ),
    path(
        "get_all_public_holiday_JS/",
        views.getPublicHolidaysJS,
        name="get_all_public_holiday_JS",
    ),
    path(
        "get_holiday_public_byID/<int:pk>/",
        views.getPublicHolidayID,
        name="get_holiday_public_byID",
    ),
    path("save_public_holiday/", views.savePublicHoliday, name="save_public_holiday"),
    path(
        "polymath_holidays/",
        views.getPolymathHolidays,
        name="polymath_holidays",
    ),
    path(
        "save_polymath_holiday/",
        views.savePolymathHoliday,
        name="save_polymath_holiday",
    ),
    path(
        "get_holiday_polymath_byID/<int:pk>/",
        views.getPolymathHolidayID,
        name="get_holiday_polymath_byID",
    ),
    path(
        "get_all_polymath_holiday_JS/",
        views.getPolymathHolidaysJS,
        name="get_all_polymath_holiday_JS",
    ),
    path(
        "other_holidays/",
        views.getOtherHolidays,
        name="other_holidays",
    ),
    path(
        "get_all_other_holiday_JS/",
        views.getOtherHolidaysJS,
        name="get_all_other_holiday_JS",
    ),
    path(
        "save_other_holiday/",
        views.saveOtherHoliday,
        name="save_other_holiday",
    ),
    path(
        "get_holiday_other_byID/<int:pk>/",
        views.getOtherHolidayID,
        name="get_holiday_other_byID",
    ),
    path("child/", views.getChild, name="view_child"),
    path("get_all_child_JS/", views.getChild, name="get_all_child_JS"),
    path("childview/", views.getChildJson, name="view_child_j"),
    path("child/<int:pk>/", views.getChildbyID, name="view_child_with_id"),
    path("savechild/", views.createChild, name="save_child"),
    path("deletechild/<int:pk>/", views.deleteChild, name="child_delete"),
    path(
        "getAllChildWithEnrolmment",
        views.getChildWithEnrolementsJson,
        name="getChildWithEnrolementsJson",
    ),
    path(
        "getPackageTypeIdJs",
        views.getPackageTypeIdJs,
        name="getPackageTypeIdJs",
    ),
    path("packag_types/", views.getPacakgeTypes, name="view_package_types"),
    path("save_package_types/", views.savePackageTypes, name="save_package_types"),
    path("get_package_types_js/", views.getPackageTypeJs, name="get_package_types_js"),
    path("calculate_duration/", views.calculate_duration, name="calculate_duration"),
    path("additional_rates/", views.getAdditionalRates, name="view_additional_rates"),
    path(
        "additional_rates_upto530/",
        views.getAdditionalRatesUpto530,
        name="additional_rates_upto530",
    ),
    path(
        "save_AdditionalRates_Upto530/",
        views.saveAdditionalRatesUpTo530,
        name="save_AdditionalRates_Upto530",
    ),
    path(
        "update_AdditionalRates_Upto530/",
        views.updateAdditionalRatesUpto530,
        name="update_AdditionalRates_Upto530",
    ),
    path(
        "get_AdditionalRates_Upto530_By_Js/",
        views.getAdditionalRatesUpto530ByJs,
        name="get_AdditionalRates_Upto530_By_Js",
    ),
    path(
        "get_AdditionalRates_Upto530_Update/",
        views.getAdditionalRatesUpto530toUpdatebyId,
        name="get_AdditionalRates_Upto530_Update",
    ),
    path(
        "get_Additional_Rates_Upto530_History_By_Js/",
        views.getAdditionalRatesUpto530HistoryByIdJS,
        name="get_Additional_Rates_Upto530_History_By_Js",
    ),
    path(
        "additional_rates_js/",
        views.getAdditionalRatesJs,
        name="view_additional_rates_js",
    ),
    path(
        "view_additional_rates_byId/",
        views.getAdditionalRateById,
        name="view_additional_rates_byId",
    ),
    path(
        "get_Additional_Rates_after530_History_By_Js/",
        views.getAdditionalRatesafter530HistoryByIdJS,
        name="get_Additional_Rates_after530_History_By_Js",
    ),
    path(
        "get_AdditionalRates_By_Id_Js/",
        views.getAdditionalRatesByIdJs,
        name="get_AdditionalRates_By_Id_Js",
    ),
    path(
        "save_additional_rates/",
        views.saveAdditionalRates,
        name="save_additional_rates",
    ),
    path(
        "getPackageTypeId",
        views.getPackageTypeId,
        name="getPackageTypeId",
    ),
    path(
        "update_additional_rates/",
        views.updateAdditionalRates,
        name="update_additional_rates",
    ),
    path(
        "get_pacakage_extrahours_after530_js/",
        views.getPacakageExtrahoursAfter530JS,
        name="get_pacakage_extrahours_after530_js",
    ),
    path("fixed_packages/", views.getFixedPackages, name="view_fixed_packages"),
    path(
        "get_fixed_packages_js/", views.getFixedPackagesJs, name="get_fixed_packages_js"
    ),
    path(
        "get_pacakage_extrahours_upto530_js/",
        views.getPacakageExtrahoursUpto530JS,
        name="get_pacakage_extrahours_upto530_js",
    ),
    path("save_fixed_package/", views.saveFixedPackage, name="save_fixed_package"),
    path("flex_packages/", views.getFlexPackages, name="view_flex_packages"),
    path("get_flex_packages_js/", views.getflexPackagesJs, name="get_flex_packages_js"),
    path("save_flex_package/", views.saveFlexPackage, name="save_flex_package"),
    path("branches/", views.getBranches, name="view_branches"),
    path("get_branches_js/", views.getBranchesJs, name="get_branches_js"),
    path("save_branch/", views.saveBranch, name="save_branch"),
    path(
        "get_Branch_For_Update_By_Id/<int:pk>/",
        views.getBranchForUpdateById,
        name="get_Branch_For_Update",
    ),
    path("daycare/", views.getDaycareCenters, name="view_centers"),
    path("save_daycare/", views.saveDayCareCenter, name="save_daycare"),
    path("get_daycares_js/", views.getDayCareCentersJs, name="get_daycares_js"),
    path(
        "get_DayCareCenters_byId_Js/",
        views.getDayCareCenterNamebyIdJs,
        name="get_DayCareCenters_byId_Js",
    ),
    path(
        "get_DayCareCenter_ForUpdate_ById/<int:pk>/",
        views.getDayCareCenterForUpdateById,
        name="get_DayCareCenter_ForUpdate_ById",
    ),
    path(
        "get_daycares_by_branch_js/",
        views.getDayCareCentersByBranchJs,
        name="get_daycares_by_branch_js",
    ),
    path("discounts/", views.getDiscounts, name="view_discounts"),
    path("get_discounts_js/", views.getDiscountJson, name="view_discounts_js"),
    path("save_discount/", views.saveDiscount, name="save_discount"),
    path("approve_discount/", views.approveDiscount, name="approve_discount"),
    path("reject_discount/", views.rejectDiscount, name="reject_discount"),
    path("enrollments/", views.getEnrollments, name="view_enrollments"),
    path("enrollments_js/", views.getEnrollmentsJS, name="get_enrollments_js"),
    path(
        "enrollments_list_js/",
        views.getAllPendingEnrollmentsJS,
        name="get_all_enrollments_js",
    ),
    path(
        "enrollments_list_for_approval/",
        views.getAllEnrollmentsForApproval,
        name="enrollments_list_for_approval",
    ),
    path("save_enrollments/", views.saveEnrollments, name="save_enrollments"),
    path(
        "delete_enrollments/<int:pk>/",
        views.deleteEnrollments,
        name="enrollments_delete",
    ),
    path("approve_enrollments/", views.approveEnrollment, name="approve_enrollments"),
    path("reject_enrollments/", views.rejectEnrollment, name="reject_enrollments"),
    path(
        "download-enrollment-forms/<int:enrollment_id>/",
        views.download_enrollment_forms,
        name="download_enrollment_forms",
    ),
    path("check_ins/", views.getCheckIns, name="view_check_ins"),
    path("getAllAttendance/", views.getAllAttendanceJS, name="get_all_attendance_JS"),
    path("save_Attendance/", views.saveAttendance, name="save_Attendance"),
    path(
        "checkInView/<str:admission_no>/",
        views.autoAttendanceRecorder,
        name="checkInView",
    ),
    path(
        "missingAttendenceReport/",
        views.getMissingAttendanceRecords,
        name="missingAttendenceReport",
    ),
    path(
        "processmissingAttendenceJS/",
        views.processMissingAttendanceRecordsJS,
        name="processmissingAttendenceJS",
    ),
    path(
        "get_attendence_dataJs/",
        views.attendanceReportsJS,
        name="get_attendence_dataJs",
    ),
    path("attendenceReport/", views.getAttendanceReports, name="getAttendenceReport"),
    path("upload_csv/", views.upload_csv, name="upload_csv"),
    path("download_qr/", views.download_qr_files, name="download_qr"),
    path("get_package_change/", views.getPackageChange, name="getPackageChange"),
    path(
        "get_package_by_child_ID_Js/",
        views.getPackagesByChildIdJS,
        name="getPackageByChildIdJS",
    ),
    path(
        "save_PackageRequest/",
        views.savePackageRequest,
        name="save_PackageRequest",
    ),
    path(
        "get_package_change_requestsJs/",
        views.getPackageChangeRequestsJS,
        name="get_package_change_requestsJs",
    ),
    path(
        "get_package_change_approval/",
        views.getPackageChangeApproval,
        name="get_package_change_approval",
    ),
    path(
        "get_child_list/",
        views.getChildrenList,
        name="get_child_list",
    ),
    path(
        "get_child_details/",
        views.getChildrenDetails,
        name="get_child_details",
    ),
    path(
        "package_change_approval/",
        views.approvePackageChange,
        name="package_change_approval",
    ),
    path(
        "get_all_child_details_by_id_JS/<int:pk>/",
        views.getAllChildDetailsByIdJS,
        name="get_all_child_details_by_id_JS",
    ),
    path(
        "center_change_request/",
        views.getCenterChange,
        name="center_change_request",
    ),
    path(
        "get_center_change_requestsJs/",
        views.getCenterChangeRequestsJS,
        name="get_center_change_requestsJs",
    ),
    path(
        "extra_hours_report/",
        views.getExtraHoursReport,
        name="extra_hours_report",
    ),
    path(
        "get_extra_hours_report_js/",
        views.getExtraHoursReportJS,
        name="get_extra_hours_report_js",
    ),
    path(
        "get_extra_hours_summary_js/",
        views.getExtraHoursSummaryJS,
        name="get_extra_hours_summary_js",
    ),
    path(
        "child-package-mapping/",
        views.getChildPackageMapping,
        name="view_child_package_mapping",
    ),
    path(
        "child-package-mapping/data/",
        views.getPackageMappingsJS,
        name="get_package_mappings_js",
    ),
    path(
        "child-package-mapping/check/",
        views.checkChildPackageMapping,
        name="check_child_package_mapping",
    ),
    path(
        "child-package-mapping/save/",
        views.savePackageMapping,
        name="save_package_mapping",
    ),
    path(
        "child-package-mapping/details/<int:pk>/",
        views.getPackageMappingDetails,
        name="get_package_mapping_details",
    ),
    path(
        "child-package-mapping/deactivate/<int:pk>/",
        views.deactivatePackageMapping,
        name="deactivate_package_mapping",
    ),
    path(
        "child-package-mapping/history/",
        views.getChildPackageMappingHistory,
        name="get_child_package_mapping_history",
    ),
    # Memo Data Entry URLs
    path("memo_data_entry/", views.getMemoDataEntry, name="memo_data_entry"),
    path(
        "get_child_package_details/",
        views.getChildPackageDetails,
        name="get_child_package_details",
    ),
    path(
        "get_attendance_summary/",
        views.getAttendanceSummary,
        name="get_attendance_summary",
    ),
    path("calculate_memo_data/", views.calculateMemoData, name="calculate_memo_data"),
    path("save_memo_data_entry/", views.saveMemoDataEntry, name="save_memo_data_entry"),
    # Add this to your urlpatterns in urls.py
    path(
        "get_detailed_charges_breakdown/",
        views.getDetailedChargesBreakdown,
        name="get_detailed_charges_breakdown",
    ),
    path(
        "child_comprehensive_view/",
        views.getChildComprehensiveView,
        name="child_comprehensive_view",
    ),
    path(
        "get_child_comprehensive_data/",
        views.getChildComprehensiveDataJS,
        name="get_child_comprehensive_data_js",
    ),
    path("load_invoice_memo/", views.loadInvoiceMemo, name="load_invoice_memo"),
    path("search_invoice_memo/", views.searchInvoiceMemo, name="search_invoice_memo"),
    path("preview_invoice_memo/<int:memo_id>/", views.previewInvoiceMemo, name="preview_invoice_memo"),
    path("download_invoice_memo_pdf/", views.downloadInvoiceMemoPDF, name="download_invoice_memo_pdf"),
    path("get_invoice_memo_by_id/<int:pk>/", views.getInvoiceMemoByID, name="get_invoice_memo_by_id"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
