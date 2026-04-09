from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db.models import Q

from accounts.models import Company, User


@login_required
def global_search(request):
    q = request.GET.get("q", "").strip()

    if not q:
        return redirect("dashboard")

    MAX_QUERY_LENGTH = 100
    if len(q) > MAX_QUERY_LENGTH:
        q = q[:MAX_QUERY_LENGTH]

    company_qs = Company.objects.all()
    user_qs = User.objects.all()

    if not request.user.is_superuser:
        tenant = request.user.tenant
        company_qs = company_qs.filter(tenant=tenant)
        user_qs = user_qs.filter(tenant=tenant)

    companies = company_qs.filter(
        Q(name__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q)
    ).select_related("tenant")[:20]

    users = user_qs.filter(
        Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
    ).select_related("tenant")[:20]

    return render(request, "dashboard/search.html", {
        "q": q,
        "companies": companies,
        "users": users,
        "active_menu": "",
    })
