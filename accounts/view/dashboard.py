from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import Tenant, Company, User

@login_required
def dashboard(request):
    user = request.user

    context = {}

    # -----------------------------------
    # SUPER ADMIN (system-wide dashboard)
    # -----------------------------------
    if user.is_superuser:
        context.update({
            # Tenant metrics
            "total_tenants": Tenant.objects.count(),
            "active_tenants": Tenant.objects.filter(is_active=True).count(),
            "inactive_tenants": Tenant.objects.filter(is_active=False).count(),

            # Global company metrics
            "total_companies": Company.objects.count(),
            "active_companies": Company.objects.filter(is_active=True).count(),
            "inactive_companies": Company.objects.filter(is_active=False).count(),

            # Global user metrics
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "inactive_users": User.objects.filter(is_active=False).count(),
        })

    # -----------------------------------
    # TENANT ADMIN / COMPANY USER
    # -----------------------------------
    else:
        tenant = user.tenant

        context.update({
            "total_companies": Company.objects.filter(tenant=tenant).count(),
            "active_companies": Company.objects.filter(
                tenant=tenant, is_active=True
            ).count(),
            "inactive_companies": Company.objects.filter(
                tenant=tenant, is_active=False
            ).count(),
            "total_users": User.objects.filter(tenant=tenant).count(),
            "active_users": User.objects.filter(
                tenant=tenant, is_active=True
            ).count(),
            "inactive_users": User.objects.filter(
                tenant=tenant, is_active=False
            ).count(),
        })

    return render(request, "dashboard/index.html", context)
