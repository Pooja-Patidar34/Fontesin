"""
Module Registry (cookbook Section 19.3).

The single source of truth for which professional modules exist, how they are
presented (icon / name / slug), who may access them, and which sections they
expose. All three modules are live and share the same offers/demands/reactions/
admin/audit logic; each adds its own professional fields purely by
configuration (MODULE_FIELD_CONFIGS), demonstrating the repeatable architecture
without rewriting core code (Section 19.11/19.13/19.14).

`allowed_roles` uses the cookbook's role vocabulary; `visible_modules()`
normalises it against this project's role codes (uppercase + superuser=admin).

Professional modules are a PAID feature: `min_plan` names the lowest
commercial plan that unlocks a module, and every module defaults to
`MODULE_MIN_PLAN_DEFAULT` ("basic") when it doesn't say otherwise. A Free
plan therefore unlocks no module at all, and any module added here in the
future inherits that rule without touching a view.
"""

MODULE_REGISTRY = [
    {
        "id": "products_services",
        "name": "Products & Services",
        "slug": "products-services",
        "icon": "fas fa-store",
        "description": "Publish and discover product & service offers and demands.",
        "enabled": True,
        "status": "live",
        "allowed_roles": ["master_admin", "consultant", "business_user"],
        "min_plan": "basic",
        "sections": ["companies", "offers", "demands"],
        "form_config": "products_services_listing_config",
    },
    {
        "id": "investments",
        "name": "Investments",
        "slug": "investments",
        "icon": "fas fa-chart-line",
        "description": "Investment opportunities, capital raising and investor demand.",
        "enabled": True,
        "status": "live",
        "allowed_roles": ["master_admin", "consultant", "business_user"],
        "min_plan": "basic",
        "sections": ["companies", "offers", "demands", "ai_analytics"],
        "form_config": "investment_listing_config",
    },
    {
        "id": "education",
        "name": "Education",
        "slug": "education",
        "icon": "fas fa-graduation-cap",
        "description": "Study programs, training, scholarships and education demand.",
        "enabled": True,
        "status": "live",
        "allowed_roles": ["master_admin", "consultant", "business_user"],
        "min_plan": "basic",
        "sections": ["companies", "offers", "demands", "ai_analytics"],
        "form_config": "education_listing_config",
    },
]

# ---------------------------------------------------------------------------
# Config-driven module-specific form fields (cookbook Section 19.11).
#
# These extra fields are stored on `Listing.module_specific_data` (JSON), so a
# new professional module is added by *configuration* here, not by rewriting
# the core listing form. `type` maps to the same input types the shared form
# already renders (text / textarea / select / decimal / boolean).
# ---------------------------------------------------------------------------
MODULE_FIELD_CONFIGS = {
    "products_services": [],
    "investments": [
        {"key": "investment_type", "label": "Investment Type", "type": "select", "required": True,
         "options": ["Equity", "Debt", "Convertible", "Real Estate", "Fund"]},
        {"key": "investment_stage", "label": "Investment Stage", "type": "select", "required": False,
         "options": ["Seed", "Series A", "Series B", "Growth", "Mature"]},
        {"key": "ticket_size", "label": "Ticket Size", "type": "text", "required": False},
        {"key": "investment_horizon", "label": "Investment Horizon", "type": "text", "required": False},
        {"key": "risk_factor_notes", "label": "Risk Factor Notes", "type": "textarea", "required": False},
    ],
    "education": [
        {"key": "program_type", "label": "Program Type", "type": "select", "required": True,
         "options": ["Course", "Training", "Degree", "Certification", "Scholarship"]},
        {"key": "study_language", "label": "Study Language", "type": "select", "required": False,
         "options": ["English", "German", "Czech", "French", "Other"]},
        {"key": "program_duration", "label": "Program Duration", "type": "text", "required": False},
        {"key": "tuition_fee", "label": "Tuition Fee", "type": "text", "required": False},
        {"key": "scholarship_available", "label": "Scholarship Available", "type": "boolean", "required": False},
        {"key": "target_profession", "label": "Target Profession", "type": "text", "required": False},
    ],
}


def module_fields(module_id):
    return MODULE_FIELD_CONFIGS.get(module_id, [])


# Map the cookbook's role names to this project's role codes.
_ROLE_ALIASES = {
    "master_admin": {"master_admin", "admin"},
    "consultant": {"consultant"},
    "business_user": {"business_user"},
}


def _user_role_tokens(user):
    """Set of cookbook role-name tokens the user satisfies."""
    tokens = set()
    if getattr(user, "is_superuser", False):
        tokens.add("master_admin")
    code = (getattr(getattr(user, "role", None), "code", "") or "").lower()
    for cookbook_role, codes in _ROLE_ALIASES.items():
        if code in codes:
            tokens.add(cookbook_role)
    return tokens


# Lowest plan that unlocks a professional module when the module itself does
# not name one. "basic" means: every paid plan (Basic / Pro / Global) is in,
# Free is out. Keep this in step with billing.utils.PLAN_TIERS.
MODULE_MIN_PLAN_DEFAULT = "basic"


def module_min_plan(module):
    """The lowest plan code that unlocks `module`."""
    return module.get("min_plan") or MODULE_MIN_PLAN_DEFAULT


def user_role_allows(user, module):
    """Role half of the access check (cookbook Section 19.6)."""
    return bool(_user_role_tokens(user).intersection(module["allowed_roles"]))


def user_meets_plan(user, module):
    """Plan half of the access check: professional modules are paid-only.

    Only Business Users are gated. Plans are company-scoped and bought BY a
    Business User for a company they own, so admins and consultants hold no
    subscription of their own — running them through the tier check would
    resolve to tier 0 (Free) and lock them out of every module. Superusers
    bypass all plan checks, exactly as `billing.utils.requires_plan` does.
    """
    if getattr(user, "is_superuser", False):
        return True
    if "business_user" not in _user_role_tokens(user):
        return True

    # Imported lazily: billing.utils imports the accounts models, and this
    # registry is pulled in at module scope by listings.web / listings.api.
    from billing.utils import PLAN_TIERS, get_plan_tier

    # The tier costs a subscription lookup (plus resolving the active company),
    # and the modules dashboard asks once per module. Memoise it on the user
    # for the life of the request/object.
    tier = getattr(user, "_module_plan_tier", None)
    if tier is None:
        tier = get_plan_tier(user)
        try:
            user._module_plan_tier = tier
        except AttributeError:  # pragma: no cover - immutable/proxy user objects
            pass

    return tier >= PLAN_TIERS.get(module_min_plan(module), 0)


def module_locked_for_user(user, module):
    """True when the user's ROLE allows the module but their PLAN does not —
    i.e. the module should be shown as an upgrade prompt rather than hidden."""
    return user_role_allows(user, module) and not user_meets_plan(user, module)


def visible_modules(user):
    """Enabled modules the user's ROLE may see, in registry order.

    Plan-locked modules are included: the dashboard still lists them so a Free
    user can see what upgrading buys, but every entry point runs through
    `user_can_access`, which also enforces the plan. Use `accessible_modules`
    when you need only the ones the user may actually open.
    """
    tokens = _user_role_tokens(user)
    return [
        m for m in MODULE_REGISTRY
        if m["enabled"] and tokens.intersection(m["allowed_roles"])
    ]


def accessible_modules(user):
    """Enabled modules the user may actually open (role AND plan)."""
    return [m for m in visible_modules(user) if user_meets_plan(user, m)]


def get_module(slug):
    for m in MODULE_REGISTRY:
        if m["slug"] == slug:
            return m
    return None


def get_module_by_id(module_id):
    for m in MODULE_REGISTRY:
        if m["id"] == module_id:
            return m
    return None


def user_can_access(user, module):
    """Full access check: the user's role is allowed AND their plan is paid."""
    return user_role_allows(user, module) and user_meets_plan(user, module)


def user_can_access_id(user, module_id):
    """Access check by module id (Section 19.6). False for unknown ids."""
    module = get_module_by_id(module_id)
    return bool(module) and user_can_access(user, module)
