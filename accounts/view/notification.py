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
from django.views.decorators.http import require_POST

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
    django_messages.success(request, "All notifications marked as read.")
    return redirect("messages")


@login_required
@require_POST
def message_delete(request, notification_id):
    note = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    note.delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("messages")