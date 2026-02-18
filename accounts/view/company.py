from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator

from accounts.models import Company, Tenant,AuditLog
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction

from accounts.forms.company_form import CompanyForm

@login_required
@transaction.atomic
def company_list(request):

    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    next_url = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":

        if not has_permission(request.user, "company.manage"):
            raise PermissionDenied()

        company_id = request.POST.get("company_id")

        if company_id:
            if request.user.is_superuser:
                company = get_object_or_404(Company, id=company_id)
            else:
                company = get_object_or_404(
                    Company,
                    id=company_id,
                    tenant=request.user.tenant
                )

            old_data = {
                "name": company.name,
                "registration_id": company.registration_id,
                "is_active": company.is_active,
                "classification": company.classification,
            }

            form = CompanyForm(request.POST, instance=company, user=request.user)
            action = "company.updated"

        else:
            form = CompanyForm(request.POST, user=request.user)
            old_data = None
            action = "company.created"

        if form.is_valid():
            company = form.save(commit=False)

            # Enforce tenant restriction
            if not request.user.is_superuser:
                company.tenant = request.user.tenant

            company.save()

            try:
                AuditLog.objects.create(
                    tenant=company.tenant,
                    actor=request.user,
                    action=action,
                    entity_type="Company",
                    entity_id=company.id,
                    metadata={
                        "old": old_data,
                        "new": {
                            "name": company.name,
                            "registration_id": company.registration_id,
                            "is_active": company.is_active,
                            "classification": company.classification,
                        },
                    },
                    ip_address=get_client_ip(request),
                )
            except Exception:
                pass

            messages.success(request, "Company saved successfully.")

            return redirect(next_url or "admin:companies")

    else:
        form = CompanyForm(user=request.user)


    selected_tenant_id = request.GET.get("tenant")
    page_number = request.GET.get("page", 1)

    if request.user.is_superuser:
        queryset = Company.objects.select_related("tenant")

        if selected_tenant_id:
            queryset = queryset.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.order_by("name")

    else:
        queryset = Company.objects.filter(tenant=request.user.tenant)
        tenants = Tenant.objects.filter(id=request.user.tenant_id)


    paginator = Paginator(queryset.order_by("name"), 10)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dashboard/companies.html",
        {
            "companies": page_obj,
            "page_obj": page_obj,
            "tenants": tenants,
            "selected_tenant_id": selected_tenant_id,
            "form": form,
            "can_manage": has_permission(request.user, "company.manage"),
            "can_view": has_permission(request.user, "company.view"),
            "active_menu": "companies",
            "next": request.get_full_path(),
        },
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

    old_status = company.is_active
    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])

    action = "company.activated" if company.is_active else "company.deactivated"

    AuditLog.objects.create(
        tenant=company.tenant,
        actor=request.user,
        action=action,
        entity_type="Company",
        entity_id=company.id,
        metadata={
            "company_name": company.name,
            "old_status": old_status,
            "new_status": company.is_active,
        },
        ip_address=get_client_ip(request),
    )

    referer = request.META.get("HTTP_REFERER")

    if referer:
        return redirect(referer)

    return redirect(reverse("admin:companies"))



@login_required
def company_detail_ajax(request, company_id):

    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    else:
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant
        )

    return JsonResponse({
        "id": str(company.id),
        "tenant": str(company.tenant.id),
        "name": company.name,
        "registration_id": company.registration_id,
        "is_active": company.is_active,
    })
