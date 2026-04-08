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


def get_user_plan(user):
    """Get the user's current CommercialPlan or None."""
    sub = get_active_subscription(user)
    return sub.plan if sub else None


def get_plan_feature(user, feature_key):
    """
    Get a specific feature value from the user's plan comparison data.
    Returns False if user has no plan or feature doesn't exist.
    """
    plan = get_user_plan(user)
    if not plan or not plan.comparison:
        return False
    return plan.comparison.get(feature_key, False)


def has_plan_feature(user, feature_key):
    """
    Check if user's plan grants access to a feature.
    Returns True if the feature value is truthy (True, a string, a number > 0).
    Returns False if the value is False, None, or empty.
    """
    value = get_plan_feature(user, feature_key)
    if value is False or value is None:
        return False
    return True


# ── Plan hierarchy for tier checks ──
PLAN_TIERS = {
    "free": 0,
    "basic": 1,
    "pro": 2,
    "global": 3,
}


def get_plan_tier(user):
    """Get the numeric tier level of the user's plan. 0 = free/no plan."""
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

            # Check minimum plan tier
            if min_plan:
                required_tier = PLAN_TIERS.get(min_plan, 0)
                user_tier = get_plan_tier(request.user)
                if user_tier < required_tier:
                    return render(request, "website/upgrade_required.html", {
                        "required_plan": min_plan,
                        "current_plan": get_user_plan(request.user),
                        "feature": feature,
                    })

            # Check specific feature
            if feature:
                if not has_plan_feature(request.user, feature):
                    return render(request, "website/upgrade_required.html", {
                        "required_plan": min_plan,
                        "current_plan": get_user_plan(request.user),
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

            if min_plan:
                required_tier = PLAN_TIERS.get(min_plan, 0)
                user_tier = get_plan_tier(request.user)
                if user_tier < required_tier:
                    plan = get_user_plan(request.user)
                    return JsonResponse({
                        "error": "Plan upgrade required",
                        "required_plan": min_plan,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            if feature:
                if not has_plan_feature(request.user, feature):
                    plan = get_user_plan(request.user)
                    return JsonResponse({
                        "error": "This feature is not available on your current plan",
                        "feature": feature,
                        "current_plan": plan.code if plan else "none",
                    }, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
