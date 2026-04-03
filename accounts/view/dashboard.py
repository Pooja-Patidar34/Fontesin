from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import Tenant, Company, User
from billing.utils import get_user_plan, get_active_subscription, has_plan_feature

@login_required
def dashboard(request):
    user = request.user

    context = {}

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

    elif user.role and user.role.name == "tenant_admin":
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

    else:
        # Regular user - show tenant-scoped data + plan features
        tenant = user.tenant
        plan = get_user_plan(user)
        subscription = get_active_subscription(user)

        context.update({
            # Tenant-scoped metrics (same data as tenant_admin)
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

            # Plan info
            "user_plan": plan,
            "subscription": subscription,
            "has_company_registry": has_plan_feature(user, "company_registry"),
            "has_advanced_analytics": has_plan_feature(user, "advanced_analytics"),
            "has_api_access": has_plan_feature(user, "api_access"),
            "has_data_export": has_plan_feature(user, "data_export"),
            "has_franchise_management": has_plan_feature(user, "franchise_management"),
        })

    # Role label for welcome banner
    if user.is_superuser:
        context["role_label"] = "Platform Admin"
    elif user.role:
        context["role_label"] = user.role.name.replace("_", " ").title()
    else:
        context["role_label"] = "User"

    context["active_menu"] = "dashboard"
    return render(request, "dashboard/index.html", context)
