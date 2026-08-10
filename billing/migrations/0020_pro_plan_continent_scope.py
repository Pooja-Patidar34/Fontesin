from django.db import migrations


# Pro reaches the whole CONTINENT again (product decision, Aug 2026), reverting
# the country-only step 0019 introduced: a Pro user who signed up in Asia sees
# the companies of every supported Asian country in the Company Database, not
# just their own. Continent is now an explicit sign-up choice
# (accounts.constants.CONTINENT_COUNTRIES / User.continent), which is what makes
# it a scope users understand rather than an invisible grouping.
#
# The country level is not lost: Basic still widens to the whole country when no
# state is on file.
PRO_COPY = {
    "tagline": "Full access across your continent",
    "best_for": (
        "Companies operating across their continent who need full "
        "visibility and services beyond their own country."
    ),
}

PRO_DETAIL_SCOPE = {
    "geographic_scope": "Your continent",
    "search_scope": "Your continent",
}


def realign(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")
    plan = CommercialPlan.objects.filter(code="pro").first()
    if not plan:
        return

    plan.tagline = PRO_COPY["tagline"]
    plan.best_for = PRO_COPY["best_for"]

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
                    row["value"] = PRO_DETAIL_SCOPE["geographic_scope"]
                elif label == "search scope":
                    row["value"] = PRO_DETAIL_SCOPE["search_scope"]
        plan.details = details

    plan.save(update_fields=["tagline", "best_for", "details"])


def noop_reverse(apps, schema_editor):
    # No reverse: the country-scope copy lives in 0019_pro_plan_country_scope
    # and is re-applied by rolling back to it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0019_pro_plan_country_scope"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
