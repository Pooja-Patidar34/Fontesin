from django.db import migrations


# Basic is a STATE tier everywhere, not only in the US (bug report, Aug 2026).
# 0016 split the tier by country — state for the US, country for the rest — so a
# BU who signed up in India / Madhya Pradesh was shown every company in India.
# The ladder is the same shape in every market: town → state → continent → world,
# so the copy no longer promises "your country".
#
# The whole country remains the fallback for a user with no state on file
# (countries without subdivisions, and accounts that predate the state field),
# which is a data gap rather than a tier, so the cards do not advertise it.
BASIC_COPY = {
    "tagline": "Full access in your state",
    "best_for": (
        "Companies operating in a single state or region who need full "
        "visibility and services across it."
    ),
}

BASIC_DETAIL_SCOPE = {
    "geographic_scope": "Your state",
    "search_scope": "Your state",
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
    # No reverse: the prior copy lives in 0016_realign_basic_plan_state_copy and
    # is re-applied by rolling back to it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0017_alter_subscription_company"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
