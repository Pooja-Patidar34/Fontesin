from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q

from accounts.models import Company, User


@login_required
def global_search(request):
    q = request.GET.get("q", "").strip()

    if not q:
        return redirect("dashboard")

    if request.user.is_superuser:
        companies = Company.objects.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q)
        ).select_related("tenant")[:20]

        users = User.objects.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        ).select_related("tenant")[:20]
    else:
        tenant = request.user.tenant
        companies = Company.objects.filter(
            tenant=tenant
        ).filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q)
        )[:20]

        users = User.objects.filter(
            tenant=tenant
        ).filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )[:20]

    return render(request, "dashboard/search.html", {
        "q": q,
        "companies": companies,
        "users": users,
        "active_menu": "",
    })
