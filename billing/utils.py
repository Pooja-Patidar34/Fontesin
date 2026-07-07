from functools import wraps

from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.utils.translation import gettext as _

from billing.models import Subscription, CommercialPlan


def get_active_subscription(user):
    """Get the user's currently *active* subscription.

    Pending ("created") subs are deliberately excluded — those represent
    a paid upgrade that hasn't been admin-approved yet, and the user's
    real plan / feature set is whatever active sub they have today (Free
    while waiting). The pending sub is surfaced separately via
    `get_pending_subscription` for UI that needs to show the upgrade
    request status.
    """
    return (
        Subscription.objects
        .filter(user=user, status__in=["active", "trial"])
        .select_related("plan")
        .first()
    )


def get_pending_subscription(user):
    """Return the user's pending (admin-approval-awaiting) subscription, if any."""
    return (
        Subscription.objects
        .filter(user=user, status="created")
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def get_user_plan(user, subscription=None):
    """Get the user's current CommercialPlan or None."""
    if subscription is None:
        subscription = get_active_subscription(user)
    return subscription.plan if subscription else None


def get_deactivated_paid_plan(user, subscription=None):
    """If the user was auto-moved off a paid plan because an admin
    deactivated it, return the now-inactive CommercialPlan; otherwise None.

    The admin "deactivate plan" action (see `plan_toggle` /
    `_move_subscribers_to_free` in billing/views.py) cancels the paid sub
    and creates a Free sub for the user. We detect that state here by:
      • the user's *current* active sub is on the Free plan, AND
      • there's a more recently cancelled sub whose plan is still flagged
        `is_active=False` (i.e. admin hasn't re-enabled it since), AND
        that plan isn't Free itself.

    Returning the plan (not just a bool) lets the template name it in the
    banner: "Your Pro plan was deactivated by the admin."
    """
    if subscription is None:
        subscription = get_active_subscription(user)
    # If the user is still on a non-Free plan, the helper doesn't apply —
    # they were not auto-moved.
    if not subscription or not subscription.plan_id:
        return None
    current_code = (subscription.plan.code or "").lower()
    if current_code != "free":
        return None

    from billing.models import Subscription
    last_cancelled = (
        Subscription.objects
        .filter(user=user, status="cancelled")
        .exclude(plan__code__iexact="free")
        .select_related("plan")
        .order_by("-end_date", "-updated_at")
        .first()
    )
    if not last_cancelled or not last_cancelled.plan_id:
        return None
    # Only flag the auto-move if the previously-held plan is still
    # deactivated. Once the admin re-enables it, the banner stops — the
    # user can choose to re-subscribe via the membership page.
    if last_cancelled.plan.is_active:
        return None
    # Defensive: also require end_date to be set (it always is for auto-
    # moved cancellations, but a manual cancellation without end_date
    # shouldn't trigger the "deactivated by admin" message).
    if last_cancelled.end_date is None:
        return None
    return last_cancelled.plan


def get_plan_feature(user, feature_key, plan=None):
    """
    Get a specific feature value from the user's plan comparison data.
    Returns False if user has no plan or feature doesn't exist.
    """
    if plan is None:
        plan = get_user_plan(user)
    if not plan or not plan.comparison:
        return False
    return plan.comparison.get(feature_key, False)


def has_plan_feature(user, feature_key, plan=None):
    """
    Check if user's plan grants access to a feature.
    Returns True if the feature value is truthy (True, a non-empty string, a number > 0).
    Returns False if the value is False, None, 0, or empty.
    """
    value = get_plan_feature(user, feature_key, plan=plan)
    return bool(value)


# ── Plan hierarchy for tier checks ──
PLAN_TIERS = {
    "free": 0,
    "basic": 1,
    "pro": 2,
    "global": 3,
}


# ── Geographic scope by plan ──
# Region -> list of ISO 2-letter country codes that belong to that region.
PLAN_REGIONS = {
    "europe": ["DE", "CZ", "GB", "FR", "NL", "PL", "AT", "CH", "SE"],
    "north_america": ["US", "CA", "MX"],
    "south_america": ["BR"],
    "asia": ["JP", "SG", "IN", "KR"],
    "middle_east": ["AE"],
    "australia_oceania": ["AU"],
}


def _region_for_country(country_code):
    """Return the region key that contains the given country code, or None."""
    if not country_code:
        return None
    code = country_code.strip().upper()
    for region, codes in PLAN_REGIONS.items():
        if code in codes:
            return region
    return None


def get_user_geographic_scope(user, plan=None):
    """
    Return the user's allowed geographic scope as a dict:
        {"mode": "country"|"region"|"worldwide"|"none",
         "countries": [list of country codes] | None}

    - FREE:   mode="country", countries=[user.country] (domicile only)
    - BASIC:  mode="country", countries=[user.country] (selected country)
    - PRO:    mode="region",  countries=<all codes in user's region>
    - GLOBAL: mode="worldwide", countries=None (no filter)
    - No plan: mode="none", countries=[] (block everything)
    """
    if plan is None:
        plan = get_user_plan(user)

    code = plan.code if plan else None
    user_country = (getattr(user, "country", None) or "").strip().upper() or None

    if code in ("free", "basic"):
        return {"mode": "country", "countries": [user_country] if user_country else []}
    if code == "pro":
        region = _region_for_country(user_country)
        return {"mode": "region", "countries": PLAN_REGIONS.get(region, []) if region else []}
    if code == "global":
        return {"mode": "worldwide", "countries": None}
    return {"mode": "none", "countries": []}


# Map ISO codes to common full-name spellings used in legacy free-text Company.country values
_COUNTRY_NAME_BY_CODE = {
    "US": "United States", "DE": "Germany", "CZ": "Czech Republic",
    "GB": "United Kingdom", "FR": "France", "NL": "Netherlands",
    "PL": "Poland", "AT": "Austria", "CH": "Switzerland", "SE": "Sweden",
    "AE": "United Arab Emirates", "SG": "Singapore", "CA": "Canada",
    "AU": "Australia", "JP": "Japan", "BR": "Brazil", "IN": "India",
    "MX": "Mexico", "KR": "South Korea",
}


def filter_companies_by_plan_scope(queryset, user, country_field="country"):
    """
    Restrict a Company queryset to the user's plan geographic scope.

    Superusers bypass filtering. GLOBAL plan returns the queryset unchanged.
    For country/region-scoped plans, matches both ISO code and common full name
    (case-insensitive) since Company.country is a free-text field.
    """
    from django.db.models import Q

    if getattr(user, "is_superuser", False):
        return queryset

    scope = get_user_geographic_scope(user)

    if scope["mode"] == "worldwide":
        return queryset

    if scope["mode"] == "none" or not scope["countries"]:
        return queryset.none()

    q = Q()
    for code in scope["countries"]:
        if not code:
            continue
        q |= Q(**{f"{country_field}__iexact": code})
        full = _COUNTRY_NAME_BY_CODE.get(code)
        if full:
            q |= Q(**{f"{country_field}__iexact": full})
    return queryset.filter(q)


def get_plan_tier(user, plan=None):
    """Get the numeric tier level of the user's plan. 0 = free/no plan."""
    if plan is None:
        plan = get_user_plan(user)
    if not plan:
        return 0
    return PLAN_TIERS.get(plan.code, 0)


def requires_plan(min_plan=None, feature=None):
    """
    Decorator that restricts view access based on the user's subscription plan.

    Usage:
        @requires_plan(min_plan="basic")          # requires Basic or higher
        @requires_plan(feature="api_access")       # requires specific feature
        @requires_plan(min_plan="pro", feature="advanced_analytics")  # both checks

    For API views (returns JSON), use requires_plan_api instead.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            # Superusers bypass all plan checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Fetch plan once for all checks
            plan = get_user_plan(request.user)

            # Check minimum plan tier
            if min_plan:
                required_tier = PLAN_TIERS.get(min_plan, 0)
                user_tier = get_plan_tier(request.user, plan=plan)
                if user_tier < required_tier:
                    return render(request, "website/upgrade_required.html", {
                        "required_plan": min_plan,
                        "current_plan": plan,
                        "feature": feature,
                    })

            # Check specific feature
            if feature:
                if not has_plan_feature(request.user, feature, plan=plan):
                    return render(request, "website/upgrade_required.html", {
                        "required_plan": min_plan,
                        "current_plan": plan,
                        "feature": feature,
                    })

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def requires_plan_api(min_plan=None, feature=None):
    """
    Same as requires_plan but returns JSON 403 for API views.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": _("Authentication required")}, status=401)

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Fetch plan once for all checks
            plan = get_user_plan(request.user)

            if min_plan:
                required_tier = PLAN_TIERS.get(min_plan, 0)
                user_tier = get_plan_tier(request.user, plan=plan)
                if user_tier < required_tier:
                    return JsonResponse({
                        "error": _("Plan upgrade required"),
                        "required_plan": min_plan,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            if feature:
                if not has_plan_feature(request.user, feature, plan=plan):
                    return JsonResponse({
                        "error": _("This feature is not available on your current plan"),
                        "feature": feature,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
