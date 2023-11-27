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
                  
                  path('settingspkg/', views.getSettings, name='view_settings_packagess'),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
