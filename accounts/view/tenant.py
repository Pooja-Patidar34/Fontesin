from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import Tenant, AuditLog
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip


@login_required
def tenant_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    qs = Tenant.objects.order_by("name")

    paginator = Paginator(qs, 7)
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
            "active_menu": "tenants",

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
