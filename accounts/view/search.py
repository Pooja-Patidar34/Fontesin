from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import redirect, render
from django.db.models import Q

from accounts.models import Company, User
from billing.utils import filter_companies_by_plan_scope


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
        # Tenant scope still applies for users (own org)
        user_qs = user_qs.filter(tenant=request.user.tenant)

        # Plan-scope filtering only makes sense for business users — they're
        # the ones with a paid plan that defines a country/region. Other roles
        # (consultant, coordinator, franchise, tenant_admin) have no plan, so
        # plan_scope returns mode="none" and zeroes the queryset. For those
        # roles we scope by linkage instead so they can find any company
        # they're connected to via their tenant or direct relationships.
        role_code = (request.user.role.code or "").lower() if request.user.role else ""
        if role_code == "business_user":
            company_qs = filter_companies_by_plan_scope(company_qs, request.user)
        else:
            company_qs = company_qs.filter(
                Q(tenant=request.user.tenant)
                | Q(consultant=request.user)
                | Q(owner_user=request.user)
                | Q(primary_users=request.user)
                | Q(usercompany__user=request.user)
            ).distinct()

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
