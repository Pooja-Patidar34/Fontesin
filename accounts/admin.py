from django.contrib import admin
from accounts.models import *


# Register your models here.
admin.site.register(Tenant)
admin.site.register(Company)
admin.site.register(User)
admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(RolePermission)
admin.site.register(UserRole)
admin.site.register(AuditLog)
admin.site.register(Classification) 