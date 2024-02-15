from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Tenant, TranspipeUser


class TranspipeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Assignments',
                                        {'fields': ('assigned_languages', 'assigned_courses')}),
                                       ('Tenant',
                                       {'fields': ('tenants',)}))
    list_filter = UserAdmin.list_filter + ('tenants',)


admin.site.register(TranspipeUser, TranspipeUserAdmin)
admin.site.register(Tenant)
