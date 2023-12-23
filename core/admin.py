from django.contrib import admin
from .models import Child, Rates,RateHistory, ExtraCharges, Package, HolidayType

# Register your models here.
admin.site.register(Child)
admin.site.register(Rates)
admin.site.register(RateHistory)
admin.site.register(ExtraCharges)
admin.site.register(Package)
admin.site.register(HolidayType)
