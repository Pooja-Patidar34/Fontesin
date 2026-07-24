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


def visible_modules(user):
    """Enabled modules the user is allowed to see, in registry order."""
    tokens = _user_role_tokens(user)
    return [
        m for m in MODULE_REGISTRY
        if m["enabled"] and tokens.intersection(m["allowed_roles"])
    ]


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
    return bool(_user_role_tokens(user).intersection(module["allowed_roles"]))


def user_can_access_id(user, module_id):
    """Access check by module id (Section 19.6). False for unknown ids."""
    module = get_module_by_id(module_id)
    return bool(module) and user_can_access(user, module)
