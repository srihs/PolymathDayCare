from django.contrib import admin

from .models import (
    AttendanceLog,
    Branch,
    Child,
    ChildEnrollment,
    ExtraHoursAfter530,
    FixedPackage,
    Holiday,
    HolidayType,
    PackageTerm,
)

# Register your models here.
admin.site.register(Child)
# admin.site.register(Rates)
# admin.site.register(RateHistory)
admin.site.register(ExtraHoursAfter530)
admin.site.register(PackageTerm)
admin.site.register(FixedPackage)
admin.site.register(HolidayType)
admin.site.register(Holiday)
admin.site.register(Branch)
admin.site.register(ChildEnrollment)

admin.site.register(AttendanceLog)
