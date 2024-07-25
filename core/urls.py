from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="home"),
    path("login/", views.UserLogin, name="login"),
    path("logout/", views.UserLogOut, name="logout"),
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
        views.getExtraHoursUpto530,
        name="additional_rates_upto530",
    ),
    path(
        "save_AdditionalRates_Upto530/",
        views.saveAdditionalRatesUpTo530,
        name="save_AdditionalRates_Upto530",
    ),
    path(
        "get_AdditionalRates_Upto530_By_Id_Js/",
        views.getAdditionalRatesUpto530ByIdJs,
        name="get_AdditionalRates_Upto530_By_Id_Js",
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
    # path(
    #     "get_ExtraHoursUpto530/",
    #     views.getExtraHoursUpto530,
    #     name="get_ExtraHoursUpto530",
    # ),
    path("packages/", views.getPackages, name="view_packages"),
    path("get_packages_js/", views.getPackagesJs, name="view_packages_js"),
    path("save_package/", views.savePackage, name="save_package"),
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
    path("check_ins/", views.getCheckIns, name="view_check_ins"),
    path("getAllAttendance/", views.getAllAttendanceJS, name="get_all_attendance_JS"),
    path("save_Attendance/", views.saveAttendance, name="save_Attendance"),
    path("checkInView/<studentID>/", views.autoAttendanceRecorder, name="checkInView"),
    path(
        "missingAttendenceReport/",
        views.getMissingAttendanceRecords,
        name="missingAttendenceReport",
    ),
    path(
        "processmissingAttendence/",
        views.processMissingAttendanceRecords,
        name="processmissingAttendence",
    ),
    path("attendenceReport/", views.loadAttendanceReports, name="getAttendenceReport"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
