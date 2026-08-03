from django.db import migrations


# Re-aligns the BASIC plan copy after billing.utils.BASIC_STATE_LEVEL_COUNTRIES
# split that tier in two. Basic no longer means "your country" everywhere:
#
#   US (and anything added to BASIC_STATE_LEVEL_COUNTRIES) → the user's STATE
#   everywhere else                                        → their COUNTRY
#
# The spec's ladder for a BU in Arvada, Colorado is Arvada → Colorado → North
# America → world, so for an American the USA is never a scope level. The
# /membership cards previously advertised "Your country" flat out, which is
# wrong for exactly the audience the worked example describes.
#
# Only Basic changes here — free / pro / global keep the copy from
# 0015_realign_plan_geographic_copy.
BASIC_COPY = {
    "tagline": "Full access in your state or country",
    "best_for": (
        "Companies operating in a single state or country who need full "
        "visibility and services across it."
    ),
}

BASIC_DETAIL_SCOPE = {
    "geographic_scope": "Your state (US) or country",
    "search_scope": "Your state (US) or country",
}


def realign(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")
    plan = CommercialPlan.objects.filter(code="basic").first()
    if not plan:
        return

    plan.tagline = BASIC_COPY["tagline"]
    plan.best_for = BASIC_COPY["best_for"]

    # Patch the JSON `details` blob if present — leave shape intact.
    details = plan.details or {}
    if isinstance(details, dict):
        visibility = details.get("visibility")
        if isinstance(visibility, list):
            for row in visibility:
                if not isinstance(row, dict):
                    continue
                label = (row.get("label") or "").strip().lower()
                if label == "geographic access":
                    row["value"] = BASIC_DETAIL_SCOPE["geographic_scope"]
                elif label == "search scope":
                    row["value"] = BASIC_DETAIL_SCOPE["search_scope"]
        plan.details = details

    plan.save(update_fields=["tagline", "best_for", "details"])


def noop_reverse(apps, schema_editor):
    # No reverse: the prior copy lives in 0015_realign_plan_geographic_copy and
    # is re-applied by rolling back to it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0015_realign_plan_geographic_copy"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
