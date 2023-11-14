from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from . import views

app_name ='core'

urlpatterns = [
   path('', views.index,name='home'),

   path('login/',views.UserLogin,name='login'),

   path('child/',views.getChild,name='view_child'),
   path('savechild/',views.createChild,name='save_child'),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
