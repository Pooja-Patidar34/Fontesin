from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render

from accounts.models import AuditLog
from accounts.utils.permissions import has_permission

@login_required
def audit_logs(request):
    if not has_permission(request.user, "audit.view"):
        raise PermissionDenied()

    page_number = request.GET.get("page", 1)

    qs = AuditLog.objects.select_related(
        "tenant", "actor"
    ).order_by("-created_at")

    if not request.user.is_superuser:
        qs = qs.filter(tenant=request.user.tenant)

    paginator = Paginator(qs, 7)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/audit_logs.html",
        {
            "logs": page_obj,      # ← MUST be Page
            "page_obj": page_obj,
        },
    )
