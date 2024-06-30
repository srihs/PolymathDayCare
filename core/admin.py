from django.contrib import admin

from .models import (
    Branch,
    Child,
    ChildEnrollment,
    ExtraCharges,
    Holiday,
    HolidayType,
    Package,
)

# Register your models here.
admin.site.register(Child)
# admin.site.register(Rates)
# admin.site.register(RateHistory)
admin.site.register(ExtraCharges)
admin.site.register(Package)
admin.site.register(HolidayType)
admin.site.register(Holiday)
admin.site.register(Branch)
admin.site.register(ChildEnrollment)
