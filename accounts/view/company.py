from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from accounts.models import Company
from accounts.utils.permissions import has_permission
from django.core.exceptions import PermissionDenied

@login_required
def company_list(request):
    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    companies = Company.objects.filter(
        tenant=request.user.tenant
    )
    return render(
        request,
        "dashboard/companies.html",
        {"companies": companies},
    )


@login_required
def toggle_company(request, company_id):
    if not has_permission(request.user, "company.manage"):
        raise PermissionDenied()

    company = get_object_or_404(
        Company,
        id=company_id,
        tenant=request.user.tenant,
    )

    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])

    return redirect("admin:companies")
