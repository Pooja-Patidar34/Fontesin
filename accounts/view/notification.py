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
    from accounts.utils.notifications import scope_notifications_qs

    qs = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("sender", "related_company")
        .order_by("-created_at")
    )
    # Business users see only the active company's notifications + account-level
    # ones; other roles see everything.
    qs = scope_notifications_qs(qs, request.user)

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
    from accounts.utils.notifications import scope_notifications_qs

    # Scope to the active company's inbox so a business user acting as one
    # company can't clear (or even address) notifications belonging to their
    # other companies by guessing ids — mirrors the company-scoped list view.
    note = get_object_or_404(
        scope_notifications_qs(
            Notification.objects.filter(id=notification_id, recipient=request.user),
            request.user,
        )
    )
    if not note.is_read:
        note.is_read = True
        note.read_at = timezone.now()
        note.save(update_fields=["is_read", "read_at"])
    if _is_ajax(request):
        return JsonResponse({"ok": True, "id": str(note.id)})
    return redirect("messages")


@login_required
@require_POST
def messages_mark_read_bulk(request):
    """Mark a specific set of notifications read and report the new unread count.

    Backs the top-right bell: opening the dropdown marks read exactly the
    notifications it displayed, so the badge reflects what the user has
    actually seen. Deliberately not "mark all" — the dropdown shows only the
    8 most recent, and clearing unread items that were never on screen would
    hide them for good.
    """
    import uuid as _uuid

    from accounts.utils.notifications import scope_notifications_qs

    # Drop anything that isn't a well-formed UUID before it reaches the ORM:
    # `id__in=["nope"]` raises ValidationError rather than matching nothing.
    ids = []
    for raw in request.POST.getlist("ids[]") or request.POST.getlist("ids"):
        try:
            ids.append(_uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            continue

    updated = 0
    if ids:
        updated = scope_notifications_qs(
            Notification.objects.filter(
                recipient=request.user, id__in=ids, is_read=False
            ),
            request.user,
        ).update(is_read=True, read_at=timezone.now())

    unread = scope_notifications_qs(
        Notification.objects.filter(recipient=request.user, is_read=False),
        request.user,
    ).count()
    return JsonResponse({"ok": True, "updated": updated, "unread": unread})


@login_required
@require_POST
def messages_mark_all_read(request):
    from accounts.utils.notifications import scope_notifications_qs

    # Mark read only what's actually visible in the (possibly company-scoped)
    # inbox, so a business user acting as one company doesn't silently clear
    # unread notifications belonging to their other companies.
    scope_notifications_qs(
        Notification.objects.filter(recipient=request.user, is_read=False),
        request.user,
    ).update(is_read=True, read_at=timezone.now())
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    django_messages.success(request, _("All notifications marked as read."))
    return redirect("messages")


@login_required
@require_POST
def message_delete(request, notification_id):
    from accounts.utils.notifications import scope_notifications_qs

    # Same company scoping as mark-read: only notifications visible in the
    # active company's inbox can be deleted.
    note = get_object_or_404(
        scope_notifications_qs(
            Notification.objects.filter(id=notification_id, recipient=request.user),
            request.user,
        )
    )
    note.delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("messages")


@login_required
def message_open(request, notification_id):
    """Delete the notification, then redirect to its `link_url`.

    Opening a notification consumes it: the user has seen what it was telling
    them, so the row is removed from the inbox rather than lingering as a read
    entry. It previously only flipped `is_read`, which cleared the bell badge
    but left the inbox filling up indefinitely.

    Falls back to the inbox if the notification has no link, or if the link
    points off-host (defense against open-redirects via crafted notification
    payloads) — in both cases it is still consumed.

    GET-only, matching the plain link in the inbox. Worth knowing: that means
    anything issuing a GET on this URL destroys the notification, so it must
    not be exposed anywhere a link prefetcher or crawler could reach it.
    """
    from accounts.utils.notifications import scope_notifications_qs

    note = get_object_or_404(
        scope_notifications_qs(
            Notification.objects.filter(id=notification_id, recipient=request.user),
            request.user,
        )
    )
    # Read the destination before deleting — `note` is unusable afterwards.
    target = note.link_url or ""
    note.delete()
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("messages")