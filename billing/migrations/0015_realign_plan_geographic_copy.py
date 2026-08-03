from django.db import migrations


# Re-aligns the plan copy with the geographic scope the code now enforces
# (billing.utils.get_user_geographic_scope). Each tier is one step wider than
# the last:
#   FREE   → the user's own TOWN, names only (was: their state/country)
#   BASIC  → their country, full details
#   PRO    → their whole CONTINENT, full details (was: a single country)
#   GLOBAL → worldwide
#
# Supersedes the copy written by 0010_realign_plan_best_for. Without this the
# /membership cards keep advertising the old reach and contradict what the
# Company Database actually shows.
PLAN_COPY = {
    "free": {
        "tagline": "Explore companies in your town",
        "best_for": (
            "Companies exploring the platform within their own town — "
            "names only, no details. Upgrade for full visibility."
        ),
    },
    "basic": {
        "tagline": "Full access in your country",
        "best_for": (
            "Companies operating in a single country who need full visibility "
            "and services nationwide."
        ),
    },
    "pro": {
        "tagline": "Full access across your continent",
        "best_for": (
            "Companies operating across their continent who need full "
            "visibility and services beyond their own country."
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
# blob — the plan detail card on /membership/ reads these.
DETAIL_SCOPE = {
    "free":   {"geographic_scope": "Your town only",  "search_scope": "Your town only"},
    "basic":  {"geographic_scope": "Your country",    "search_scope": "Your country"},
    "pro":    {"geographic_scope": "Your continent",  "search_scope": "Your continent"},
    "global": {"geographic_scope": "Worldwide",       "search_scope": "Worldwide"},
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
    # No reverse: the prior copy lives in 0010_realign_plan_best_for and is
    # re-applied by rolling back to it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0014_unique_active_account_subscription_per_user"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
