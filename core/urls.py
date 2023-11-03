from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings
from . import views

urlpatterns = [
   path('', views.index,name='home'),
]+ static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
