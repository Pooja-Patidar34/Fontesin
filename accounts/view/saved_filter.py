from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

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


def _clean_filters(raw):
    cleaned = {}
    for key in FILTER_FIELDS:
        value = (raw.get(key) or "").strip()
        if value:
            cleaned[key] = value
    return cleaned


@login_required
def saved_filter_list(request):
    _require_basic_or_pro_business_user(request.user)

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
    _require_basic_or_pro_business_user(request.user)

    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "message": "Please give this filter a name."}, status=400)

    filters = _clean_filters(request.POST)
    if not filters:
        return JsonResponse(
            {"ok": False, "message": "Apply at least one filter (country / state / city) before saving."},
            status=400,
        )

    try:
        saved, created = SavedFilter.objects.update_or_create(
            user=request.user,
            name=name,
            defaults={"filters": filters},
        )
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "A filter with that name already exists."}, status=400)

    return JsonResponse({
        "ok": True,
        "created": created,
        "id": str(saved.id),
        "name": saved.name,
        "message": "Filter saved to your Favorites.",
    })


@login_required
@require_POST
@transaction.atomic
def saved_filter_delete(request, filter_id):
    _require_basic_or_pro_business_user(request.user)

    saved = get_object_or_404(SavedFilter, id=filter_id, user=request.user)
    saved.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": "Filter removed."})

    messages.success(request, "Filter removed.")
    return redirect(reverse("saved-filters"))


@login_required
def saved_filter_apply(request, filter_id):
    """One-click jump: resolve saved filter → redirect to Companies with filter params."""
    _require_basic_or_pro_business_user(request.user)

    saved = get_object_or_404(SavedFilter, id=filter_id, user=request.user)
    params = {k: v for k, v in (saved.filters or {}).items() if k in FILTER_FIELDS and v}
    query = urlencode(params)
    url = reverse("companies")
    return redirect(f"{url}?{query}" if query else url)


@login_required
@require_POST
@transaction.atomic
def company_connect(request, company_id):
    _require_basic_or_pro_business_user(request.user)

    company = get_object_or_404(Company, id=company_id, is_active=True)

    connection, created = CompanyConnection.objects.get_or_create(
        user=request.user,
        company=company,
        defaults={"message": (request.POST.get("message") or "").strip() or None},
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "created": created,
            "status": connection.status,
            "message": (
                "Connection request sent." if created
                else f"Already requested ({connection.get_status_display()})."
            ),
        })

    messages.success(
        request,
        "Connection request sent." if created else "You already requested a connection with this company.",
    )
    referer = request.META.get("HTTP_REFERER")
    return redirect(referer or reverse("companies"))
