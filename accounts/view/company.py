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

    # -------------------------------
    # VIEW PERMISSION
    # -------------------------------
    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    next_url = request.POST.get("next") or request.GET.get("next")

    # -------------------------------
    # CREATE / UPDATE
    # -------------------------------
    if request.method == "POST":

        if not has_permission(request.user, "company.manage"):
            raise PermissionDenied()

        company_id = request.POST.get("company_id")

        if company_id in ("", None, "undefined"):
            company_id = None

        # ---------- UPDATE ----------
        if company_id:
            if request.user.is_superuser:
                company = get_object_or_404(Company, id=company_id)
            else:
                company = get_object_or_404(
                    Company,
                    id=company_id,
                    tenant=request.user.tenant,
                )

            old_data = {
                "name": company.name,
                "registration_id": company.registration_id,
                "classification": company.classification,
                "is_active": company.is_active,
            }

            form = CompanyForm(
                request.POST,
                instance=company,
                user=request.user,
            )
            action = "company.updated"

        # ---------- CREATE ----------
        else:
            company = None
            old_data = None

            form = CompanyForm(
                request.POST,
                user=request.user,
            )
            action = "company.created"

        if form.is_valid():
            company = form.save(commit=False)

            # Enforce tenant safety
            if not request.user.is_superuser:
                company.tenant = request.user.tenant

            company.save()
            form.save_m2m()

            # ---------- AUDIT LOG ----------
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
                            "classification": company.classification,
                            "is_active": company.is_active,
                        },
                    },
                    ip_address=get_client_ip(request),
                )
            except Exception:
                # Never block core flow for audit failures
                pass

            messages.success(
                request,
                "Company updated successfully."
                if company_id
                else "Company created successfully."
            )

            return redirect(next_url or "companies")

    # -------------------------------
    # GET (LIST + EMPTY FORM)
    # -------------------------------
    else:
        form = CompanyForm(user=request.user)

    # -------------------------------
    # FILTERING / PAGINATION
    # -------------------------------
    selected_tenant_id = request.GET.get("tenant")
    page_number = request.GET.get("page", 1)

    if request.user.is_superuser:
        queryset = Company.objects.select_related("tenant")

        if selected_tenant_id:
            queryset = queryset.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.order_by("name")

    else:
        queryset = Company.objects.filter(
            tenant=request.user.tenant
        )
        tenants = Tenant.objects.filter(
            id=request.user.tenant_id
        )

    paginator = Paginator(queryset.order_by("name"), 10)
    page_obj = paginator.get_page(page_number)

    # -------------------------------
    # RENDER
    # -------------------------------
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





# @login_required
# @transaction.atomic
# def company_list(request):

#     if not has_permission(request.user, "company.view"):
#         raise PermissionDenied()

#     next_url = request.POST.get("next") or request.GET.get("next")

#     if request.method == "POST":

#         if not has_permission(request.user, "company.manage"):
#             raise PermissionDenied()

#         company_id = request.POST.get("company_id")

#         if company_id:
#             if request.user.is_superuser:
#                 company = get_object_or_404(Company, id=company_id)
#             else:
#                 company = get_object_or_404(
#                     Company,
#                     id=company_id,
#                     tenant=request.user.tenant
#                 )

#             old_data = {
#                 "name": company.name,
#                 "registration_id": company.registration_id,
#                 "is_active": company.is_active,
#                 "classification": company.classification,
#             }

#             form = CompanyForm(request.POST, instance=company, user=request.user)
#             action = "company.updated"

#         else:
#             form = CompanyForm(request.POST, user=request.user)
#             old_data = None
#             action = "company.created"

#         if form.is_valid():
#             company = form.save(commit=False)

#             # Enforce tenant restriction
#             if not request.user.is_superuser:
#                 company.tenant = request.user.tenant

#             company.save()

#             try:
#                 AuditLog.objects.create(
#                     tenant=company.tenant,
#                     actor=request.user,
#                     action=action,
#                     entity_type="Company",
#                     entity_id=company.id,
#                     metadata={
#                         "old": old_data,
#                         "new": {
#                             "name": company.name,
#                             "registration_id": company.registration_id,
#                             "is_active": company.is_active,
#                             "classification": company.classification,
#                         },
#                     },
#                     ip_address=get_client_ip(request),
#                 )
#             except Exception:
#                 pass

#             messages.success(request, "Company saved successfully.")

#             return redirect(next_url or "companies")

#     else:
#         form = CompanyForm(user=request.user)


#     selected_tenant_id = request.GET.get("tenant")
#     page_number = request.GET.get("page", 1)

#     if request.user.is_superuser:
#         queryset = Company.objects.select_related("tenant")

#         if selected_tenant_id:
#             queryset = queryset.filter(tenant_id=selected_tenant_id)

#         tenants = Tenant.objects.order_by("name")

#     else:
#         queryset = Company.objects.filter(tenant=request.user.tenant)
#         tenants = Tenant.objects.filter(id=request.user.tenant_id)


#     paginator = Paginator(queryset.order_by("name"), 10)
#     page_obj = paginator.get_page(page_number)

#     return render(
#         request,
#         "dashboard/companies.html",
#         {
#             "companies": page_obj,
#             "page_obj": page_obj,
#             "tenants": tenants,
#             "selected_tenant_id": selected_tenant_id,
#             "form": form,
#             "can_manage": has_permission(request.user, "company.manage"),
#             "can_view": has_permission(request.user, "company.view"),
#             "active_menu": "companies",
#             "next": request.get_full_path(),
#         },
#     )


@login_required
@transaction.atomic
def company_delete(request, company_id):

    # -------------------------------
    # PERMISSION CHECK
    # -------------------------------
    if not has_permission(request.user, "company.manage"):
        raise PermissionDenied()

    if request.method != "POST":
        raise PermissionDenied()

    # -------------------------------
    # FETCH COMPANY (TENANT SAFE)
    # -------------------------------
    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    else:
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )

    company_name = company.name
    tenant = company.tenant

    # -------------------------------
    # DELETE
    # -------------------------------
    company.delete()

    # -------------------------------
    # AUDIT LOG
    # -------------------------------
    try:
        AuditLog.objects.create(
            tenant=tenant,
            actor=request.user,
            action="company.deleted",
            entity_type="Company",
            entity_id=company_id,
            metadata={
                "company_name": company_name,
            },
            ip_address=get_client_ip(request),
        )
    except Exception:
        pass

    messages.success(request, "Company deleted successfully.")

    referer = request.META.get("HTTP_REFERER")

    if referer:
        return redirect(referer)

    return redirect(reverse("companies"))


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

    return redirect(reverse("companies"))



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

    enrichment = getattr(company, "enrichment", None)

    return JsonResponse({
        # --------------------
        # Company (Core)
        # --------------------
        "company": {
            "id": str(company.id),
            "tenant": str(company.tenant.id),
            "name": company.name,
            "registration_id": company.registration_id,
            "classification": company.classification,

            "address_line1": company.address_line1,
            "address_line2": company.address_line2,
            "city": company.city,
            "state": company.state,
            "postal_code": company.postal_code,
            "country": company.country,

            "latitude": str(company.latitude) if company.latitude else None,
            "longitude": str(company.longitude) if company.longitude else None,

            "phone": company.phone,
            "phone_secondary": company.phone_secondary,
            "fax": company.fax,
            "website": company.website,

            "is_active": company.is_active,
        },

        # --------------------
        # Company Enrichment
        # --------------------
        "enrichment": {
            "naics_code": enrichment.naics_code if enrichment else None,
            "naics_description": enrichment.naics_description if enrichment else None,

            "sic2_code": enrichment.sic2_code if enrichment else None,
            "sic4_code": enrichment.sic4_code if enrichment else None,
            "sic6_code": enrichment.sic6_code if enrichment else None,

            "sic2_description": enrichment.sic2_description if enrichment else None,
            "sic4_description": enrichment.sic4_description if enrichment else None,
            "sic6_description": enrichment.sic6_description if enrichment else None,
            "sic_division": enrichment.sic_division if enrichment else None,

            "exact_sales_volume": (
                str(enrichment.exact_sales_volume)
                if enrichment and enrichment.exact_sales_volume else None
            ),
            "sales_range": enrichment.sales_range if enrichment else None,
            "sales_code": enrichment.sales_code if enrichment else None,

            "exact_employee_count": enrichment.exact_employee_count if enrichment else None,
            "employee_range": enrichment.employee_range if enrichment else None,
            "employee_code": enrichment.employee_code if enrichment else None,

            "business_type": enrichment.business_type if enrichment else None,
            "location_type": enrichment.location_type if enrichment else None,

            "year_started": enrichment.year_started if enrichment else None,
            "month_started": enrichment.month_started if enrichment else None,

            "franchise": enrichment.franchise if enrichment else None,
            "chain": enrichment.chain if enrichment else None,
            "home_office": enrichment.home_office if enrichment else None,

            "median_income_census_area": (
                str(enrichment.median_income_census_area)
                if enrichment and enrichment.median_income_census_area else None
            ),
            "mean_housing_census_area": (
                str(enrichment.mean_housing_census_area)
                if enrichment and enrichment.mean_housing_census_area else None
            ),

            "ebiz_score": enrichment.ebiz_score if enrichment else None,
            "ebiz_decile": enrichment.ebiz_decile if enrichment else None,
            "ebiz_percentile": enrichment.ebiz_percentile if enrichment else None,

            "monthly_telco_spend": (
                str(enrichment.monthly_telco_spend)
                if enrichment and enrichment.monthly_telco_spend else None
            ),
            "monthly_data_spend": (
                str(enrichment.monthly_data_spend)
                if enrichment and enrichment.monthly_data_spend else None
            ),
            "number_of_lines": enrichment.number_of_lines if enrichment else None,
            "number_of_pcs": enrichment.number_of_pcs if enrichment else None,

            "is_manufacturing": enrichment.is_manufacturing if enrichment else None,
            "is_subsidiary": enrichment.is_subsidiary if enrichment else None,
            "is_foreign_company": enrichment.is_foreign_company if enrichment else None,
            "fortune_company": enrichment.fortune_company if enrichment else None,

            "source": enrichment.source if enrichment else None,
        },
    })