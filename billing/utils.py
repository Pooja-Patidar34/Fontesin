from functools import wraps

from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.utils.translation import gettext as _

from accounts.constants import COUNTRY_CODES
from accounts.utils.country_matching import country_match_q, resolve_country_code
from billing.models import Subscription, CommercialPlan


def resolve_active_company(user):
    """The company whose plan governs THIS user's current session.

    Plans are company-scoped, so "what plan is this user on" is really "what
    plan is this user's ACTIVE company on". Resolution order:

      1. An explicit selection stashed on the user by the active-company
         middleware (`user._active_company`, read from the session). This is
         what the login-time company picker sets when a Business User owns
         more than one company.
      2. Auto-select when the user owns exactly ONE company — no picker
         needed, that company is always the active one.
      3. Otherwise fall back to the user's primary_company when they own it —
         a sane default for background/non-request contexts where no session
         selection is available.
      4. None — user owns no company yet (the Free floor / create-company
         onboarding window).

    Returns a Company instance or None.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    # 1. Explicit session selection (set by ActiveCompanyMiddleware). The
    #    sentinel attribute is only present when the middleware ran; a real
    #    Company means "act as this one".
    selected = getattr(user, "_active_company", None)
    if selected is not None:
        return selected

    from accounts.models import Company

    owned = list(Company.objects.filter(owner_user=user).order_by("created_at")[:2])
    # 2. Exactly one owned company → auto-select it.
    if len(owned) == 1:
        return owned[0]
    # 3. Multiple owned and nothing selected → primary_company if owned.
    if len(owned) > 1:
        primary = getattr(user, "primary_company", None)
        if primary and Company.objects.filter(
            owner_user=user, id=primary.id
        ).exists():
            return primary
        return owned[0]
    # 4. No owned company.
    return None


def get_active_subscription(user, company=None):
    """Get the *active* subscription governing this user's session.

    Plans are company-scoped: the returned subscription is the active/trial
    one on the user's ACTIVE company (see `resolve_active_company`), not on
    the user. When the user has no active company we fall back to a legacy
    user-level subscription with no company attached — this keeps accounts
    that predate the company link (or that only ever JOINED a company)
    resolving to their historical plan.

    Pending ("created") subs are deliberately excluded — those represent
    a paid upgrade that hasn't been admin-approved yet, and the real plan /
    feature set is whatever active sub exists today (Free while waiting). The
    pending sub is surfaced separately via `get_pending_subscription`.
    """
    if company is None:
        company = resolve_active_company(user)

    base = Subscription.objects.filter(status__in=["active", "trial"]).select_related("plan")

    if company is not None:
        # The company's plan is the company's regardless of who is viewing
        # (owner or a joined user acting as it), so scope by company only.
        return base.filter(company=company).first()

    # No active company → legacy user-level fallback (no company attached).
    return base.filter(user=user, company__isnull=True).first()


def ensure_free_subscription(company, user=None):
    """Guarantee `company` has an active plan, creating a Free one if it has
    none.

    Plans are company-scoped, so a company with NO active subscription would
    resolve to "no plan" — which the geographic-scope helper treats as
    "block everything", harsher than Free. Every company a Business User
    creates should behave as Free until they pick (and get approved for) a
    paid plan, so we drop a Free active subscription on it at creation time.

    Idempotent: returns the existing active/trial subscription untouched when
    one is already present. Returns the active subscription, or None when the
    company is missing or no Free plan is configured.
    """
    if company is None:
        return None
    existing = (
        Subscription.objects
        .filter(company=company, status__in=["active", "trial"])
        .select_related("plan")
        .first()
    )
    if existing:
        return existing

    free_plan = CommercialPlan.objects.filter(code="free", is_active=True).first()
    if not free_plan:
        return None

    from django.db import IntegrityError, transaction
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    now = timezone.now()
    owner = user or getattr(company, "owner_user", None)
    try:
        with transaction.atomic():
            return Subscription.objects.create(
                user=owner,
                company=company,
                plan=free_plan,
                billing_period=free_plan.billing_period,
                status="active",
                start_date=now,
                end_date=now + relativedelta(years=1),
            )
    except IntegrityError:
        # A concurrent request won the race and created the active sub first
        # (unique_active_subscription_per_company). Return the existing row.
        return (
            Subscription.objects
            .filter(company=company, status__in=["active", "trial"])
            .select_related("plan")
            .first()
        )


def ensure_account_free_subscription(user):
    """Guarantee a Business User is on the Free plan even before they own a
    company.

    Per the onboarding spec, a verified BU "is in the system with a free plan"
    immediately — before creating any company. Plans are company-scoped, so a
    company-less BU has no company subscription to resolve; without this they'd
    fall through to "no plan" (which blocks the directory entirely) instead of
    Free. This drops an account-level Free subscription (company=None) that the
    resolver's no-company fallback picks up.

    Idempotent and self-limiting: no-op if the user already has ANY active/trial
    subscription (company-scoped or account-level), so once they create a
    company (which gets its own Free sub) this never adds a duplicate. Only
    applies to business users.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
    if role_code != "business_user":
        return None
    if Subscription.objects.filter(user=user, status__in=["active", "trial"]).exists():
        return None

    free_plan = CommercialPlan.objects.filter(code="free", is_active=True).first()
    if not free_plan:
        return None

    from django.db import IntegrityError, transaction
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta

    now = timezone.now()
    try:
        with transaction.atomic():
            return Subscription.objects.create(
                user=user,
                company=None,
                plan=free_plan,
                billing_period=free_plan.billing_period,
                status="active",
                start_date=now,
                end_date=now + relativedelta(years=1),
            )
    except IntegrityError:
        # A concurrent login/registration created the account-level Free sub
        # first (unique_active_account_subscription_per_user). Return whatever
        # active/trial sub the user now has.
        return (
            Subscription.objects
            .filter(user=user, status__in=["active", "trial"])
            .select_related("plan")
            .first()
        )


def get_pending_subscription(user, company=None):
    """Return the pending (admin-approval-awaiting) subscription for the
    user's active company, if any. Falls back to a legacy user-level pending
    sub when there's no active company."""
    if company is None:
        company = resolve_active_company(user)
    base = Subscription.objects.filter(status="created").select_related("plan")
    if company is not None:
        return base.filter(company=company).order_by("-created_at").first()
    return base.filter(user=user, company__isnull=True).order_by("-created_at").first()


def get_user_plan(user, subscription=None, company=None):
    """Get the user's current CommercialPlan or None.

    Pass `company` when the caller has already resolved the acting company, so
    the lookup below doesn't resolve it a second time."""
    if subscription is None:
        subscription = get_active_subscription(user, company=company)
    return subscription.plan if subscription else None


def get_deactivated_paid_plan(user, subscription=None, company=None):
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

    Plans are company-scoped, so pass the `company` this check is FOR (the
    active company) to avoid a cancelled paid sub on ANOTHER owned company
    raising a false "deactivated by admin" banner. When omitted, the search
    is user-wide (legacy behaviour).
    """
    if subscription is None:
        subscription = get_active_subscription(user, company=company)
    # If the user is still on a non-Free plan, the helper doesn't apply —
    # they were not auto-moved.
    if not subscription or not subscription.plan_id:
        return None
    current_code = (subscription.plan.code or "").lower()
    if current_code != "free":
        return None

    from billing.models import Subscription
    cancelled_qs = Subscription.objects.filter(user=user, status="cancelled")
    if company is not None:
        cancelled_qs = cancelled_qs.filter(company=company)
    last_cancelled = (
        cancelled_qs
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
# Continent -> ISO 2-letter country codes on that continent. This is the Pro
# plan's reach: a Pro user sees the whole continent they sit on — an American
# sees all of North America, a Pole all of Europe, and so on.
#
# Continents, not commercial regions: "Middle East" used to be its own bucket,
# which left a UAE Pro user seeing only the UAE while every other Pro user got a
# multi-country reach. The UAE is in Asia.
#
# `africa` is deliberately present but empty — no African country is a supported
# market yet (accounts.constants.CountryChoices). It exists so adding one is a
# single-line change here, and the assert below makes forgetting impossible.
PLAN_REGIONS = {
    "europe": ["DE", "CZ", "GB", "FR", "NL", "PL", "AT", "CH", "SE"],
    "north_america": ["US", "CA", "MX"],
    "south_america": ["BR"],
    "africa": [],
    "asia": ["AE", "IN", "JP", "KR", "SG"],
    "australia_oceania": ["AU"],
}

# Every supported country must sit on exactly one continent, or a Pro user from
# the missing country silently gets an EMPTY scope (mode="region", countries=[])
# — they'd see nothing at all rather than too much, which is easy to miss.
_MAPPED_COUNTRIES = [code for codes in PLAN_REGIONS.values() for code in codes]
assert len(_MAPPED_COUNTRIES) == len(set(_MAPPED_COUNTRIES)), (
    "A country appears on two continents in PLAN_REGIONS: "
    f"{sorted({c for c in _MAPPED_COUNTRIES if _MAPPED_COUNTRIES.count(c) > 1})}"
)
assert set(_MAPPED_COUNTRIES) == set(COUNTRY_CODES), (
    "PLAN_REGIONS and accounts.constants.COUNTRY_CODES have drifted: "
    f"unmapped countries={sorted(set(COUNTRY_CODES) - set(_MAPPED_COUNTRIES))}, "
    f"unknown codes in PLAN_REGIONS={sorted(set(_MAPPED_COUNTRIES) - set(COUNTRY_CODES))}. "
    "Every supported country needs a continent."
)


# Countries where the BASIC plan reaches one STATE rather than the whole
# country. The spec's worked example is a BU in Arvada, Colorado, US whose
# ladder is Arvada → Colorado → North America → world: the USA itself is never
# a scope level, because in that model the US is a union of states the way
# Europe is a union of countries. The same spec lists "Germany, Poland" as
# Basic scopes — whole countries — so everywhere else Basic stays country-wide.
#
# Add a country here to move it to state-level Basic (e.g. if Canada should be
# province-wide rather than country-wide). Countries absent from COUNTRY_STATES
# fall back to country scope automatically, as does a user with no state on file.
BASIC_STATE_LEVEL_COUNTRIES = {"US"}


def _region_for_country(country_code):
    """Return the region key that contains the given country code, or None."""
    if not country_code:
        return None
    code = country_code.strip().upper()
    for region, codes in PLAN_REGIONS.items():
        if code in codes:
            return region
    return None


def get_user_geographic_scope(user, plan=None, company=None):
    """
    Return the allowed geographic scope for the user's ACTIVE company as a dict:
        {"mode": "city"|"state"|"country"|"region"|"worldwide"|"none",
         "countries": [list of country codes] | None,
         "city": <town name> | None,
         "state": <state / region name> | None}

    Each plan widens the reach by one geographic step:

    - FREE:   mode="city",      the user's own TOWN (countries pins the town's
                                country so "Springfield" doesn't match every
                                Springfield on earth)
    - BASIC:  mode="state",     the user's own STATE, in the countries listed in
                                BASIC_STATE_LEVEL_COUNTRIES (countries pins the
                                state's country, since state names repeat across
                                countries) …
              mode="country",   … and the whole country everywhere else
    - PRO:    mode="region",    countries=<every country on that continent>
    - GLOBAL: mode="worldwide", countries=None (no filter)
    - No plan: mode="none",     countries=[] (block everything)

    Plans are company-scoped, so the anchor is the active company's town /
    state / country (its plan's home market), falling back to the user's own
    when there is no active company (e.g. the Free floor before a company
    exists).

    `city` is only meaningful for mode="city" and `state` only for mode="state";
    both are None everywhere else.
    """
    if company is None:
        company = resolve_active_company(user)
    if plan is None:
        plan = get_user_plan(user, subscription=get_active_subscription(user, company=company))

    code = plan.code if plan else None
    anchor_country = (getattr(company, "country", None) if company else None) or getattr(user, "country", None)
    # Company.country is free text — it may hold "US", "United States" or
    # "USA". Resolve to an ISO code so the continent lookup and the downstream
    # country_match_q (which expands a CODE into all its spellings) work the
    # same either way; unresolvable values fall through as-is.
    user_country = (
        resolve_country_code(anchor_country) or (anchor_country or "").strip().upper() or None
    )

    if code == "free":
        anchor_city = (getattr(company, "city", None) if company else None) or getattr(user, "city", None)
        city = (anchor_city or "").strip() or None
        return {
            "mode": "city",
            "countries": [user_country] if (city and user_country) else [],
            "city": city,
            "state": None,
        }
    if code == "basic":
        if user_country in BASIC_STATE_LEVEL_COUNTRIES:
            # Company stores the state as `state`, User as `state_region`.
            anchor_state = (getattr(company, "state", None) if company else None) or getattr(
                user, "state_region", None
            )
            state = (anchor_state or "").strip() or None
            # No state on file → fall through to whole-country rather than
            # return an empty scope. Losing the state is a data gap, not a
            # reason to hide the directory the user is paying for.
            if state:
                return {
                    "mode": "state",
                    "countries": [user_country],
                    "city": None,
                    "state": state,
                }
        return {
            "mode": "country",
            "countries": [user_country] if user_country else [],
            "city": None,
            "state": None,
        }
    if code == "pro":
        region = _region_for_country(user_country)
        return {
            "mode": "region",
            "countries": PLAN_REGIONS.get(region, []) if region else [],
            "city": None,
            "state": None,
        }
    if code == "global":
        return {"mode": "worldwide", "countries": None, "city": None, "state": None}
    return {"mode": "none", "countries": [], "city": None, "state": None}


def filter_companies_by_plan_scope(queryset, user, country_field="country"):
    """
    Restrict a Company queryset to the user's plan geographic scope.

    Superusers bypass filtering. GLOBAL plan returns the queryset unchanged.
    For city/state/country/region-scoped plans, the country is matched on both
    ISO code and common full name (case-insensitive) since Company.country is a
    free-text field; a Free plan additionally pins the town, and a state-level
    Basic plan additionally pins the state.
    """
    from django.db.models import Q

    if getattr(user, "is_superuser", False):
        return queryset

    scope = get_user_geographic_scope(user)

    if scope["mode"] == "worldwide":
        return queryset

    if scope["mode"] == "none" or not scope["countries"]:
        return queryset.none()

    countries = [c for c in (scope.get("countries") or []) if c]
    if not countries:
        return queryset.none()

    country_q = Q()
    for code in countries:
        country_q |= country_match_q(code, field=country_field)
    queryset = queryset.filter(country_q)

    # Free plan: the user's own town only. Town names repeat across countries
    # (and states), so this always rides on top of the country filter above.
    if scope["mode"] == "city":
        queryset = queryset.filter(city__iexact=scope["city"])
    # Basic plan in a state-level country: the user's own state. Same reasoning
    # as the town — state names repeat across countries, so this rides on top of
    # the country filter rather than replacing it.
    elif scope["mode"] == "state":
        queryset = queryset.filter(state__iexact=scope["state"])
    return queryset


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
