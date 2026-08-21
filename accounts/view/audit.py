from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.utils import timezone

from accounts.models import AuditLog
from accounts.utils.permissions import has_permission
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required


def _can_view_audit(user):
    """Who may open the audit log (spec §14): Platform Admin, any role granted the
    `audit.view` permission, and — for their own subtree only — a franchise owner."""
    if user.is_superuser:
        return True
    if has_permission(user, "audit.view"):
        return True
    from accounts.view.franchise import _owns_any_node
    return _owns_any_node(user)


def _visible_audit_tenant_ids(request_user):
    """Tenant ids whose audit rows `request_user` may see (spec §14).

    A franchise owner sees their own franchise subtree (own nodes + descendants),
    plus their own tenant's rows. Everyone else sees only their own tenant."""
    from accounts.view.franchise import visible_node_ids
    tenant_ids = set(visible_node_ids(request_user))  # franchise subtree; empty otherwise
    if getattr(request_user, "tenant_id", None):
        tenant_ids.add(request_user.tenant_id)
    return tenant_ids


@login_required
def audit_logs(request):
    if not _can_view_audit(request.user):
        raise PermissionDenied()

    qs = AuditLog.objects.select_related(
        "tenant", "actor"
    ).order_by("-created_at")

    if request.user.is_superuser:
        pass
    else:
        # A franchise owner may see the audit trail for actions inside their own
        # subtree (spec §14, optional visibility): every franchise node they own
        # plus its descendants, alongside their own tenant's rows. Non-franchise
        # users get just their own tenant (visible_tenant_ids returns none).
        tenant_ids = _visible_audit_tenant_ids(request.user)
        if not tenant_ids:
            raise PermissionDenied()
        qs = qs.filter(tenant_id__in=tenant_ids)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        "logs": page_obj,
        "page_obj": page_obj,
        # Windowed page numbers, so 100+ pages render as 1 ... 97 98 [99] 100
        # instead of one link per page (which overflows the card footer).
        "page_range": paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=1
        ),
        "active_menu": "audit",
    }

    # AJAX pagination clicks ask only for the inner panel.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "dashboard/_audit_logs_panel.html", context)

    return render(request, "dashboard/audit_logs.html", context)



@login_required
def audit_log_detail_ajax(request, log_id):
    if not _can_view_audit(request.user):
        raise PermissionDenied()

    qs = AuditLog.objects.select_related("tenant", "actor")

    if request.user.is_superuser:
        log = get_object_or_404(qs, id=log_id)
    else:
        tenant_ids = _visible_audit_tenant_ids(request.user)
        if not tenant_ids:
            raise PermissionDenied()
        log = get_object_or_404(qs, id=log_id, tenant_id__in=tenant_ids)

    return JsonResponse({
        "actor": log.actor.email if log.actor else "System",
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": str(log.entity_id),
        "ip_address": log.ip_address,
        "metadata": log.metadata,
        "created_at": timezone.localtime(log.created_at).strftime("%Y-%m-%d %H:%M:%S"),
    })

