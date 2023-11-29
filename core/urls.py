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
                  path('save_rates/', views.saveRates, name='save_rates'),
                  
                  path('additional_rates/', views.getAdditionalRates, name='view_additional_rates'),
                  path('additional_rates_js/', views.getAdditionalRatesJs, name='view_additional_rates_js'),
                  
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
