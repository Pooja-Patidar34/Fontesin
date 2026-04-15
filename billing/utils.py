from functools import wraps

from django.shortcuts import redirect, render
from django.http import JsonResponse

from billing.models import Subscription, CommercialPlan


def get_active_subscription(user):
    """Get the user's current active/trial/created subscription."""
    return (
        Subscription.objects
        .filter(user=user, status__in=["active", "trial", "created"])
        .select_related("plan")
        .first()
    )


def get_user_plan(user, subscription=None):
    """Get the user's current CommercialPlan or None."""
    if subscription is None:
        subscription = get_active_subscription(user)
    return subscription.plan if subscription else None


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
                return JsonResponse({"error": "Authentication required"}, status=401)

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Fetch plan once for all checks
            plan = get_user_plan(request.user)

            if min_plan:
                required_tier = PLAN_TIERS.get(min_plan, 0)
                user_tier = get_plan_tier(request.user, plan=plan)
                if user_tier < required_tier:
                    return JsonResponse({
                        "error": "Plan upgrade required",
                        "required_plan": min_plan,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            if feature:
                if not has_plan_feature(request.user, feature, plan=plan):
                    return JsonResponse({
                        "error": "This feature is not available on your current plan",
                        "feature": feature,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
