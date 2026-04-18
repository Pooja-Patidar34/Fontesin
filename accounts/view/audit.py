from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render

from accounts.models import AuditLog
from accounts.utils.permissions import has_permission
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

@login_required
def audit_logs(request):
    if not has_permission(request.user, "audit.view"):
        raise PermissionDenied()

    qs = AuditLog.objects.select_related(
        "tenant", "actor"
    ).order_by("-created_at")

    if request.user.is_superuser:
        pass
    elif request.user.tenant:
        qs = qs.filter(tenant=request.user.tenant)
    else:
        raise PermissionDenied()

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/audit_logs.html",
        {
            "logs": page_obj,
            "page_obj": page_obj,
            "active_menu": "audit",
        },
    )



@login_required
def audit_log_detail_ajax(request, log_id):
    if not has_permission(request.user, "audit.view"):
        raise PermissionDenied()

    qs = AuditLog.objects.select_related("tenant", "actor")

    if request.user.is_superuser:
        log = get_object_or_404(qs, id=log_id)
    elif request.user.tenant:
        log = get_object_or_404(qs, id=log_id, tenant=request.user.tenant)
    else:
        raise PermissionDenied()

    return JsonResponse({
        "actor": log.actor.email if log.actor else "System",
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": str(log.entity_id),
        "ip_address": log.ip_address,
        "metadata": log.metadata,
        "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    })

