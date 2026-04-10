from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import redirect, render
from django.db.models import Q

from accounts.models import Company, User


PAGE_SIZE = 10


def _paginate(qs, request, page_param):
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get(page_param)
    try:
        return paginator.page(page_number)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


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

    company_qs = company_qs.filter(
        Q(name__icontains=q) | Q(city__icontains=q) | Q(country__icontains=q)
    ).select_related("tenant").order_by("name")

    user_qs = user_qs.filter(
        Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
    ).select_related("tenant").order_by("email")

    companies_page = _paginate(company_qs, request, "cpage")
    users_page = _paginate(user_qs, request, "upage")

    return render(request, "dashboard/search.html", {
        "q": q,
        "companies": companies_page,
        "users": users_page,
        "companies_total": company_qs.count(),
        "users_total": user_qs.count(),
        "active_menu": "",
    })
