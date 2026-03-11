from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import Tenant, AuditLog
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip
from accounts.forms.tenant_form import TenantForm
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
import logging

business_logger = logging.getLogger("business")
technical_logger = logging.getLogger("technical")

# @login_required
# def tenant_list(request):
#     if not request.user.is_superuser:
#         raise PermissionDenied()

#     if request.method == "POST":

#         tenant_id = request.POST.get("tenant_id")

#         if tenant_id:
#             tenant = get_object_or_404(Tenant, id=tenant_id)
#             form = TenantForm(request.POST, instance=tenant)
#             action = "tenant.updated"
#             message = "Tenant updated successfully."
#         else:
#             form = TenantForm(request.POST)
#             action = "tenant.created"
#             message = "Tenant created successfully."

#         if form.is_valid():
#             tenant = form.save()

#             AuditLog.objects.create(
#                 tenant=tenant,
#                 actor=request.user,
#                 action=action,
#                 entity_type="Tenant",
#                 entity_id=tenant.id,
#                 metadata={
#                     "name": tenant.name,
#                     "is_active": tenant.is_active,
#                 },
#                 ip_address=get_client_ip(request),
#             )

#             messages.success(request, message)
#             return redirect("admin:tenants")
#     else:
#         form = TenantForm()
    
#     qs = Tenant.objects.filter(is_deleted=False).annotate(
#         company_count=Count("companies", distinct=True),
#         user_count=Count("users", distinct=True)
#     ).order_by("name")

#     paginator = Paginator(qs, 10)
#     page_number = request.GET.get("page", 1)

#     try:
#         page_obj = paginator.page(page_number)
#     except (PageNotAnInteger, EmptyPage):
#         page_obj = paginator.page(1)

#     return render(
#         request,
#         "dashboard/tenants.html",
#         {
#             "tenants": page_obj,
#             "page_obj": page_obj,
#             "form": form,
#             "active_menu": "tenants",
#         },
#     )

@login_required
def tenant_list(request):

    if not request.user.is_superuser:
        raise PermissionDenied()

    if request.method == "POST":

        tenant_id = request.POST.get("tenant_id")

        if tenant_id:
            tenant = get_object_or_404(Tenant, id=tenant_id)
            form = TenantForm(request.POST, instance=tenant)
            action = "tenant.updated"
            message = "Tenant updated successfully."
        else:
            form = TenantForm(request.POST)
            action = "tenant.created"
            message = "Tenant created successfully."

        if form.is_valid():
            tenant = form.save()

            AuditLog.objects.create(
                tenant=tenant,
                actor=request.user,
                action=action,
                entity_type="Tenant",
                entity_id=tenant.id,
                metadata={
                    "name": tenant.name,
                    "is_active": tenant.is_active,
                },
                ip_address=get_client_ip(request),
            )

            messages.success(request, message)
            return redirect("admin:tenants")

    else:
        form = TenantForm()

    # SEARCH
    q = request.GET.get("q", "").strip()

    qs = Tenant.objects.filter(is_deleted=False)

    if q:
        qs = qs.filter(name__icontains=q)

    qs = qs.annotate(
        company_count=Count("companies", distinct=True),
        user_count=Count("users", distinct=True)
    ).order_by("name")

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/tenants.html",
        {
            "tenants": page_obj,
            "page_obj": page_obj,
            "form": form,
            "active_menu": "tenants",
            "search_query": q,
        },
    )

@login_required
def toggle_tenant(request, tenant_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    old_status = tenant.is_active
    tenant.is_active = not tenant.is_active
    tenant.save(update_fields=["is_active"])

    action = (
        "tenant.activated"
        if tenant.is_active
        else "tenant.deactivated"
    )

    AuditLog.objects.create(
        tenant=tenant,
        actor=request.user,
        action=action,
        entity_type="Tenant",
        entity_id=tenant.id,
        metadata={
            "old_status": old_status,
            "new_status": tenant.is_active,
        },
        ip_address=get_client_ip(request),
    )

    return redirect(request.META.get("HTTP_REFERER", "admin:tenants"))


@login_required
def tenant_detail_ajax(request, tenant_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    return JsonResponse({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.strftime("%Y-%m-%d %H:%M"),
    })


@login_required
def tenant_delete(request, tenant_id):

    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    if request.method == "POST":

        tenant_name = tenant.name

        AuditLog.objects.create(
            tenant=tenant,   # FIXED
            actor=request.user,
            action="tenant.deleted",
            entity_type="Tenant",
            entity_id=str(tenant.id),
            metadata={
                "name": tenant_name,
            },
            ip_address=get_client_ip(request),
        )

        # Soft delete
        tenant.is_deleted = True
        tenant.save(update_fields=["is_deleted"])

        messages.success(request, "Tenant deleted successfully.")
        return redirect("admin:tenants")

    return render(
        request,
        "dashboard/tenant_confirm_delete.html",
        {
            "tenant": tenant,
            "active_menu": "tenants",
        },
    )