from django.db import migrations


# Re-aligns the BEST FOR / tagline / scope copy so it matches what the company
# discovery scope actually enforces:
#   FREE   → state-level (same scope as BASIC), no details
#   BASIC  → state-level, full details
#   PRO    → country-level (single country, not a continent)
#   GLOBAL → worldwide
PLAN_COPY = {
    "free": {
        "tagline": "Explore companies in your state",
        "best_for": (
            "Companies exploring the platform within their own state — "
            "limited details, no contact info. Upgrade for full visibility."
        ),
    },
    "basic": {
        "tagline": "Full access in your state",
        "best_for": (
            "Companies operating in a single state who need full visibility "
            "and services within that state."
        ),
    },
    "pro": {
        "tagline": "Full access across your country",
        "best_for": (
            "Companies operating across one country who need full visibility "
            "and services nationwide."
        ),
    },
    "global": {
        "tagline": "Worldwide visibility & access",
        "best_for": (
            "Companies operating internationally who need worldwide visibility "
            "and search."
        ),
    },
}


# Per-plan "Geographic Access" / "Search Scope" values inside the JSON details
# blob — also worth updating so the plan detail card on /membership/ stays
# truthful.
DETAIL_SCOPE = {
    "free":   {"geographic_scope": "Your state only",   "search_scope": "Your state only"},
    "basic":  {"geographic_scope": "Your state only",   "search_scope": "Your state only"},
    "pro":    {"geographic_scope": "Your country",      "search_scope": "Your country"},
    "global": {"geographic_scope": "Worldwide",         "search_scope": "Worldwide"},
}


def realign(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")
    for code, copy in PLAN_COPY.items():
        plan = CommercialPlan.objects.filter(code=code).first()
        if not plan:
            continue
        plan.tagline = copy["tagline"]
        plan.best_for = copy["best_for"]

        # Patch the JSON `details` blob if present — leave shape intact.
        details = plan.details or {}
        if isinstance(details, dict):
            scope = DETAIL_SCOPE.get(code, {})
            # Patch the "Geographic Access" / "Search Scope" rows under
            # details.visibility[*] if they exist; otherwise leave alone.
            visibility = details.get("visibility")
            if isinstance(visibility, list):
                for row in visibility:
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").strip().lower()
                    if label == "geographic access" and scope.get("geographic_scope"):
                        row["value"] = scope["geographic_scope"]
                    elif label == "search scope" and scope.get("search_scope"):
                        row["value"] = scope["search_scope"]
            plan.details = details

        plan.save(update_fields=["tagline", "best_for", "details"])


def noop_reverse(apps, schema_editor):
    # No reverse: the prior copy is preserved in 0005_reseed_plans_mvp and
    # would be re-applied if you roll back to that migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0009_alter_consultantcommission_id"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
