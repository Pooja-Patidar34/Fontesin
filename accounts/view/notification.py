"""In-app messages / notifications inbox.

Every authenticated account type (consultant, coordinator, franchise,
business user, tenant_admin, superuser) sees the same Messages page,
populated from the Notification model. Used today for certification
events, but designed as the catch-all inbox for future event types.
"""

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from accounts.models import Notification


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@login_required
def messages_list(request):
    qs = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("sender", "related_company")
        .order_by("-created_at")
    )

    unread_count = qs.filter(is_read=False).count()

    return render(
        request,
        "dashboard/messages.html",
        {
            "active_menu": "messages",
            "notifications": qs[:100],
            "unread_count": unread_count,
            "total_count": qs.count(),
        },
    )


@login_required
@require_POST
def message_mark_read(request, notification_id):
    note = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.read_at = timezone.now()
        note.save(update_fields=["is_read", "read_at"])
    if _is_ajax(request):
        return JsonResponse({"ok": True, "id": str(note.id)})
    return redirect("messages")


@login_required
@require_POST
def messages_mark_all_read(request):
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    django_messages.success(request, _("All notifications marked as read."))
    return redirect("messages")


@login_required
@require_POST
def message_delete(request, notification_id):
    note = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    note.delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("messages")


@login_required
def message_open(request, notification_id):
    """Mark the notification as read, then redirect to its `link_url`.

    Wired to the inbox "Open" link so clicking through to the target page
    also clears the unread badge. Without this, the badge stayed stuck
    because the raw `link_url` href bypassed any read-tracking. GET-only
    on purpose — this is a navigation action, not a state-change form.
    Falls back to the inbox if the notification has no link, or if the
    link points off-host (defense against open-redirects via crafted
    notification payloads).
    """
    note = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.read_at = timezone.now()
        note.save(update_fields=["is_read", "read_at"])
    target = note.link_url or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("messages")