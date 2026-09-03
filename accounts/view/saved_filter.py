from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from accounts.models import Company, CompanyConnection, SavedFilter


FILTER_FIELDS = (
    "country", "state", "city", "name",
    "entity_type", "classification",
    "naics", "keywords",
)


def _plan_code_for_business_user(user):
    if not user.is_authenticated or user.is_superuser:
        return None
    role_code = ""
    if user.role and user.role.code:
        role_code = user.role.code.lower()
    if role_code != "business_user":
        return None
    from billing.utils import get_user_plan
    plan = get_user_plan(user)
    return plan.code if plan else None


def _is_basic_business_user(user):
    return _plan_code_for_business_user(user) == "basic"


def _is_paid_business_user(user):
    return _plan_code_for_business_user(user) in ("basic", "pro", "global")


# Back-compat alias — older callsites used the basic-or-pro name; semantics
# now include global since global business users get every paid feature.
_is_basic_or_pro_business_user = _is_paid_business_user


def _require_paid_business_user(user):
    if not _is_paid_business_user(user):
        raise PermissionDenied()


_require_basic_or_pro_business_user = _require_paid_business_user


def _can_use_saved_filters(user):
    """Who may use Favorites (saved company filters).

    Must match the sidebar gate in templates/base/base.html, which shows the
    Favorites row to the Platform Admin, franchise holders, consultants and
    paid Business Users. The view previously accepted ONLY a paid Business
    User, so every other audience the sidebar advertised the tab to clicked it
    and got a 403 (bug report, Sep 2026) — the Platform Admin included, since
    `_plan_code_for_business_user` returns None for a superuser and for any
    non-business role, which then fails the paid check.

    Favorites are per-user rows (SavedFilter.user), so widening this exposes
    nobody else's data: each of these accounts gets their own empty list to
    fill. The Free plan stays out (spec B) and so does the Coordinator
    (spec E) — the two audiences the sidebar also hides the row from.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    role_code = ""
    if user.role and user.role.code:
        role_code = user.role.code.lower()
    if role_code == "coordinator":
        return False
    if role_code == "consultant":
        return True

    from accounts.utils.franchise_access import is_franchise_holder
    if is_franchise_holder(user):
        return True

    return _is_paid_business_user(user)


def _require_saved_filter_access(user):
    if not _can_use_saved_filters(user):
        raise PermissionDenied()


def _clean_filters(raw):
    cleaned = {}
    for key in FILTER_FIELDS:
        value = (raw.get(key) or "").strip()
        if value:
            cleaned[key] = value
    return cleaned


@login_required
def saved_filter_list(request):
    _require_saved_filter_access(request.user)

    return render(
        request,
        "dashboard/saved_filters.html",
        {
            "saved_filters": SavedFilter.objects.filter(user=request.user),
            "active_menu": "favorites",
        },
    )


@login_required
@require_POST
@transaction.atomic
def saved_filter_save(request):
    _require_saved_filter_access(request.user)

    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "message": _("Please give this filter a name.")}, status=400)

    filters = _clean_filters(request.POST)
    if not filters:
        return JsonResponse(
            {"ok": False, "message": _("Apply at least one filter (country / state / city) before saving.")},
            status=400,
        )

    try:
        saved, created = SavedFilter.objects.update_or_create(
            user=request.user,
            name=name,
            defaults={"filters": filters},
        )
    except IntegrityError:
        return JsonResponse({"ok": False, "message": _("A filter with that name already exists.")}, status=400)

    return JsonResponse({
        "ok": True,
        "created": created,
        "id": str(saved.id),
        "name": saved.name,
        "message": _("Filter saved to your Favorites."),
    })


@login_required
@require_POST
@transaction.atomic
def saved_filter_delete(request, filter_id):
    _require_saved_filter_access(request.user)

    saved = get_object_or_404(SavedFilter, id=filter_id, user=request.user)
    saved.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": _("Filter removed.")})

    messages.success(request, _("Filter removed."))
    return redirect(reverse("saved-filters"))


@login_required
def saved_filter_apply(request, filter_id):
    """One-click jump: resolve saved filter → redirect to Companies with filter params."""
    _require_saved_filter_access(request.user)

    saved = get_object_or_404(SavedFilter, id=filter_id, user=request.user)
    params = {k: v for k, v in (saved.filters or {}).items() if k in FILTER_FIELDS and v}
    query = urlencode(params)
    url = reverse("companies")
    return redirect(f"{url}?{query}" if query else url)


@login_required
@require_POST
@transaction.atomic
def company_connect(request, company_id):
    # Connecting is a paid-plan feature. Only Basic / Pro / Global business
    # users may send a partnership request — the company owner then approves
    # or declines per the existing flow. Free-plan users (and non-business
    # users) are blocked; the row template greys out their Connect button to
    # match. This is the server-side counterpart so a free user can't bypass
    # the disabled button by POSTing directly.
    plan_code = _plan_code_for_business_user(request.user)
    if plan_code is None:
        raise PermissionDenied()
    if plan_code == "free":
        msg = _("Connecting with companies is available on paid plans. Upgrade to connect.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect(request.META.get("HTTP_REFERER") or reverse("companies"))

    # Block connecting while a paid-plan upgrade is awaiting admin approval.
    # During that window the user is on temporary Free access (the paid sub is
    # status="created"); they shouldn't get partnership rights until approved.
    # This is the server-side counterpart to the disabled "Connect" button.
    from billing.models import Subscription
    if Subscription.objects.filter(user=request.user, status="created").exists():
        msg = _("Connecting is available once your plan upgrade is approved.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect(request.META.get("HTTP_REFERER") or reverse("companies"))

    company = get_object_or_404(Company, id=company_id, is_active=True)

    connection, created = CompanyConnection.objects.get_or_create(
        user=request.user,
        company=company,
        defaults={"message": (request.POST.get("message") or "").strip() or None},
    )

    # Re-request after a rejection: (user, company) is unique, so a previously
    # rejected request lingers as a row and get_or_create returns it with
    # created=False — which previously meant no new request and no owner
    # notification. Allow the business user to send a fresh request by resetting
    # a REJECTED connection back to pending (and updating the message). Pending
    # / accepted connections are left as-is (no spam, no downgrade).
    resent = False
    if not created and connection.status == CompanyConnection.STATUS_REJECTED:
        connection.status = CompanyConnection.STATUS_PENDING
        new_msg = (request.POST.get("message") or "").strip() or None
        if new_msg is not None:
            connection.message = new_msg
        connection.save()  # bumps updated_at; status back to pending
        resent = True

    # Drop a notification into the company owner's inbox on a fresh request —
    # either a brand-new one or a re-sent one after a previous rejection. No-op
    # on a still-pending / already-accepted duplicate (don't spam the owner).
    if (created or resent) and company.owner_user_id and company.owner_user_id != request.user.id:
        try:
            from accounts.utils.notifications import notify
            from accounts.utils.i18n_messages import Msg
            from accounts.models import Notification

            requester = request.user
            requester_label = (
                f"{requester.first_name} {requester.last_name}".strip()
                or requester.email
            )
            notify(
                recipient=company.owner_user,
                sender=requester,
                kind=Notification.KIND_GENERIC,
                title=Msg("New partnership request from %(name)s", name=requester_label),
                body=Msg(
                    "%(name)s has requested a partnership with %(company)s. "
                    "Open the Partnerships tab to confirm or decline.",
                    name=requester_label, company=company.name,
                ),
                link_url=reverse("partnerships"),
                related_company=company,
            )
        except Exception:
            pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "created": created or resent,
            "status": connection.status,
            "message": (
                "Connection request sent." if (created or resent)
                else f"Already requested ({connection.get_status_display()})."
            ),
        })

    messages.success(
        request,
        _("Connection request sent.")
        if (created or resent)
        else "You already requested a connection with this company.",
    )
    referer = request.META.get("HTTP_REFERER")
    return redirect(referer or reverse("companies"))
