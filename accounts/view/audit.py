from accounts.models import AuditLog
from accounts.utils.permissions import has_permission
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.exceptions import PermissionDenied

@login_required
def audit_logs(request):
    if not has_permission(request.user, "audit.view"):
        raise PermissionDenied()

    logs = AuditLog.objects.filter(
        tenant=request.user.tenant
    )[:200]

    return render(
        request,
        "dashboard/audit_logs.html",
        {"logs": logs},
    )
