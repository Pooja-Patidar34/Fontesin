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
        # Tenant scope still applies for users (own org)
        user_qs = user_qs.filter(tenant=request.user.tenant)

        # Company scope MUST match what the user can see in their Company
        # Database — otherwise a company that's visible in the list can't be
        # found by the top search (the original bug). We reuse the exact same
        # visibility helpers instead of a separate, stricter plan-scope filter:
        #
        #   • business_user → business_user_visible_companies (linkage + the
        #     plan-based discovery scope: free = their own country, basic =
        #     their selected country, pro = their region, global = all active
        #     companies worldwide — with country-name aliases like
        #     "USA"/"US"/"United States").
        #   • coordinator   → linkage + the certified companies in the region
        #     they manage (coordinator_territory_q), so vetted region companies
        #     are searchable (uncertified region companies are held out).
        #   • everyone else → companies they're linked to (tenant / consultant /
        #     owner / primary / partnership).
        from accounts.view.company import (
            business_user_visible_companies,
            coordinator_territory_q,
        )

        role_code = (request.user.role.code or "").lower() if request.user.role else ""
        if role_code == "business_user":
            company_qs = business_user_visible_companies(request.user)
        else:
            linkage_q = (
                Q(tenant=request.user.tenant)
                | Q(consultant=request.user)
                | Q(owner_user=request.user)
                | Q(primary_users=request.user)
                | Q(usercompany__user=request.user)
            )
            coordinator_scope_q = coordinator_territory_q(request.user)
            if coordinator_scope_q is not None:
                linkage_q = linkage_q | coordinator_scope_q
            company_qs = company_qs.filter(linkage_q).distinct()

    # Match on name/city/country plus the typed NACE/NAICS FKs (so a
    # search for "J62" or "software" surfaces companies tagged with the
    # matching code) and the legacy free-text industry_code column so
    # older rows still come up while the picker migration is in progress.
    company_qs = company_qs.filter(
        Q(name__icontains=q)
        | Q(city__icontains=q)
        | Q(country__icontains=q)
        | Q(nace_code__code__istartswith=q)
        | Q(nace_code__title__icontains=q)
        | Q(naics_code__code__istartswith=q)
        | Q(naics_code__title__icontains=q)
        | Q(industry_code__icontains=q)
    ).select_related("tenant", "nace_code").distinct().order_by("name")

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
