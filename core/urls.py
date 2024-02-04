from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from . import views
from django.contrib.auth import logout

app_name = 'core'

urlpatterns = [
                  path('', views.index, name='home'),

                  path('login/', views.UserLogin, name='login'),
                  path('logout/', views.UserLogOut, name='logout'),

                  path('child/', views.getChild, name='view_child'),
                  path('get_all_child_JS/', views.getChild, name='get_all_child_JS'),
                  path('childview/', views.getChildJson, name='view_child_j'),
                  path('child/<int:pk>/', views.getChildbyID, name='view_child_with_id'),
                  path('savechild/', views.createChild, name='save_child'),
                  path('deletechild/<int:pk>/', views.deleteChild, name='child_delete'),
                  
                  path('rates/', views.getRates, name='view_rates'),
                  path('ratesjs/', views.getRatesJs, name='view_rates_js'),
                  path('view_rate_byId/<int:pk>/', views.getRateByID, name='view_rates_byId'),
                  path('save_rates/', views.saveRates, name='save_rates'),
                  path('rates_rate_js/', views.getRatesforRatesJs, name='view_rates_rate_js'),
                  path('base_rate_js/', views.getRateHistoryById, name='view_baserate_update_byId'),
                  path('save_rates_for_base_rate/', views.saveBaseRate, name='save_rates_forBaseRate'),
                  path('get_Rate_Amount_By_Id_Js/', views.getRateAmountByIdJs, name='get_Rate_amount_By_Id_Js'),
                  path('calculate_duration/', views.calculate_duration, name='calculate_duration'),

                  
                  path('additional_rates/', views.getAdditionalRates, name='view_additional_rates'),
                  path('additional_rates_js/', views.getAdditionalRatesJs, name='view_additional_rates_js'),
                  path('save_additional_rates/', views.saveAdditionalRates, name='save_additional_rates'),
                  path('view_additional_rates_byId', views.getAdditionalRateById, name='view_additional_rates_byId'),
                  path('update_additional_rates/', views.updateAdditionalRates, name='update_additional_rates'),

                  path('packages/', views.getPackages, name='view_packages'),
                  path('get_packages_js/', views.getPackagesJs, name='view_packages_js'),
                  path('save_package/', views.savePackage, name='save_package'),

                  path('branches/', views.getBranches, name='view_branches'),
                  path('get_branches_js/', views.getBranchesJs, name='get_branches_js'),
                  path('save_branch/', views.saveBranch, name='save_branch'),
                  path('get_Branch_For_Update_By_Id/<int:pk>/', views.getBranchForUpdateById, name='get_Branch_For_Update'),

                  path('daycare/', views.getDaycareCenters, name='view_centers'),
                  path('save_daycare/', views.saveDayCareCenter, name='save_daycare'),
                  path('get_daycares_js/', views.getDayCareCentersJs, name='get_daycares_js'),
                  path('get_DayCareCenters_byId_Js/', views.getDayCareCenterNamebyIdJs, name='get_DayCareCenters_byId_Js'),
                  path('get_DayCareCenter_ForUpdate_ById/<int:pk>/', views.getDayCareCenterForUpdateById, name='get_DayCareCenter_ForUpdate_ById'),
                  path('get_daycares_by_branch_js/', views.getDayCareCentersByBranchJs, name='get_daycares_by_branch_js'),
                  
                  path('discounts/', views.getDiscounts, name='view_discounts'),
                  path('get_discounts_js/', views.getDiscountJson, name='view_discounts_js'),
                  path('save_discount/', views.saveDiscount, name='save_discount'),
                  path('approve_discount/', views.approveDiscount, name='approve_discount'),
                  path('reject_discount/', views.rejectDiscount, name='reject_discount'),


                  path('enrollments/', views.getEnrollments, name='view_enrollments'),
                  path('enrollments_js/', views.getEnrollmentsJS, name='get_enrollments_js'),
                  path('enrollments_list_js/', views.getAllEnrollmentsJS, name='get_all_enrollments_js'),
                  path('enrollments_list_for_approval/', views.getAllEnrollmentsForApproval, name='enrollments_list_for_approval'),
                  path('save_enrollments/', views.saveEnrollments, name='save_enrollments'),
                  path('delete_enrollments/<int:pk>/', views.deleteEnrollments, name='enrollments_delete'),
                  path('approve_enrollments/', views.approveEnrollment, name='approve_enrollments'),
                  path('reject_enrollments/', views.rejectEnrollment, name='reject_enrollments'),


                  path('check_ins/', views.getCheckIns, name='view_check_ins'),
                  path('getAllAttendance/', views.getAllAttendanceJS, name='get_all_attendance_JS'),
                  path('save_Attendance/', views.saveAttendance, name='save_Attendance'),
                  path('missingAttendenceReport/', views.getMissingAttendanceRecords, name='missingAttendenceReport')



                  
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
