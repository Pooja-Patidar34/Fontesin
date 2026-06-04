"""Super Admin inbox for website "Contact" form submissions.

The public contact form (accounts.view.website.contact) writes a
ContactMessage row per enquiry; this module renders the Super Admin's
"Messages" sidebar page and the read/delete actions for it. Access is
restricted to superusers — these are platform-wide enquiries, not per-tenant.
"""

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import ContactMessage


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def contact_messages_list(request):
    """Super Admin list of contact-form messages, newest first."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    qs = ContactMessage.objects.all().order_by("-created_at")
    unread_count = qs.filter(is_read=False).count()

    return render(
        request,
        "dashboard/contact_messages.html",
        {
            "active_menu": "contact-messages",
            "contact_messages": qs[:200],
            "unread_count": unread_count,
            "total_count": qs.count(),
        },
    )


@require_POST
def contact_message_mark_read(request, message_id):
    if not request.user.is_superuser:
        raise PermissionDenied()
    msg = get_object_or_404(ContactMessage, id=message_id)
    msg.mark_read()
    if _is_ajax(request):
        return JsonResponse({"ok": True, "id": str(msg.id)})
    return redirect("contact-messages")


@require_POST
def contact_messages_mark_all_read(request):
    if not request.user.is_superuser:
        raise PermissionDenied()
    ContactMessage.objects.filter(is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("contact-messages")


@require_POST
def contact_message_delete(request, message_id):
    if not request.user.is_superuser:
        raise PermissionDenied()
    msg = get_object_or_404(ContactMessage, id=message_id)
    msg.delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("contact-messages")
