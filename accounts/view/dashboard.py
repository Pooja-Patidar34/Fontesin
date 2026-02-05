from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import Company, User

@login_required
def dashboard(request):
    tenant = request.user.tenant

    context = {
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
    }

    return render(request, "dashboard/index.html", context)
