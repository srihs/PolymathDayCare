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
                  path('childview/', views.getChildJson, name='view_child_j'),
                  path('child/<int:pk>/', views.getChildbyID, name='view_child_with_id'),
                  path('savechild/', views.createChild, name='save_child'),
                  path('deletechild/<int:pk>/', views.deleteChild, name='child_delete'),
                  
                  path('rates/', views.getRates, name='view_rates'),
                  path('ratesjs/', views.getRatesJs, name='view_rates_js'),
                  path('view_rate_byId/<int:pk>/', views.getRateByID, name='view_rates_byId'),
                  path('save_rates/', views.saveRates, name='save_rates'),
                  path('rates_rate_js/', views.getRatesforRatesJs, name='view_rates_rate_js'),
                  path('rates_rate_js/<int:pk>/', views.getRateHistoryById, name='view_baserate_update_byId'),
                  path('save_rates_for_base_rate/', views.saveBaseRate, name='save_rates_forBaseRate'),
                  path('get_Rate_Amount_By_Id_Js/', views.getRateAmountByIdJs, name='get_Rate_amount_By_Id_Js'),

                  
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

                  
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
