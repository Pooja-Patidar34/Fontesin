# from django.contrib.auth.decorators import login_required
# from django.shortcuts import render, get_object_or_404, redirect
# from accounts.models import Company
# from accounts.utils.permissions import has_permission
# from django.core.exceptions import PermissionDenied

# @login_required
# def company_list(request):
#     if not has_permission(request.user, "company.view"):
#         raise PermissionDenied()

#     companies = Company.objects.filter(
#         tenant=request.user.tenant
#     )
#     return render(
#         request,
#         "dashboard/companies.html",
#         {"companies": companies},
#     )


# @login_required
# def toggle_company(request, company_id):
#     if not has_permission(request.user, "company.manage"):
#         raise PermissionDenied()

#     company = get_object_or_404(
#         Company,
#         id=company_id,
#         tenant=request.user.tenant,
#     )

#     company.is_active = not company.is_active
#     company.save(update_fields=["is_active"])

#     return redirect("admin:companies")


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator

from accounts.models import Company, Tenant
from accounts.utils.permissions import has_permission


@login_required
def company_list(request):
    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    selected_tenant_id = request.GET.get("tenant")
    page_number = request.GET.get("page", 1)

    # -------------------------
    # SUPER ADMIN
    # -------------------------
    if request.user.is_superuser:
        queryset = Company.objects.all().select_related("tenant")

        if selected_tenant_id:
            queryset = queryset.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.all().order_by("name")

    # -------------------------
    # TENANT ADMIN / OTHERS
    # -------------------------
    else:
        queryset = Company.objects.filter(
            tenant=request.user.tenant
        )
        tenants = None

    # -------------------------
    # PAGINATION
    # -------------------------
    paginator = Paginator(queryset.order_by("name"), 7)  # 10 per page
    page_obj = paginator.get_page(page_number)

    context = {
        "companies": page_obj,
        "page_obj": page_obj,
        "tenants": tenants,
        "selected_tenant_id": selected_tenant_id,
    }

    return render(
        request,
        "dashboard/companies.html",
        context,
    )


@login_required
def toggle_company(request, company_id):
    if not has_permission(request.user, "company.manage"):
        raise PermissionDenied()

    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    else:
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )

    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])

    return redirect(request.META.get("HTTP_REFERER", "admin:companies"))
