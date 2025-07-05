from django.contrib import admin
from .models import Room,Appliance,ApplianceUsageLog,Controller,SlaveDevice
from django.contrib.auth.admin import UserAdmin
from  core.models import User

admin.site.register(Room)
admin.site.register(Appliance)
admin.site.register(ApplianceUsageLog)
admin.site.register(User, UserAdmin)
admin.site.register(Controller)
admin.site.register(SlaveDevice)


