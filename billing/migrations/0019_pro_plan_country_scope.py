from django.db import migrations


# Pro is the COUNTRY step, not the continent (bug report, Aug 2026). With Basic
# now state-based everywhere (0018), the ladder is town -> state -> country ->
# world, one level per tier. Pro previously jumped from a state straight to a
# continent, skipping the country a BU most wants: a German Pro user asked for
# every German company and was given all of Europe instead.
PRO_COPY = {
    "tagline": "Full access in your country",
    "best_for": (
        "Companies trading across a whole country who need visibility and "
        "services beyond their own state."
    ),
}

PRO_DETAIL_SCOPE = {
    "geographic_scope": "Your country",
    "search_scope": "Your country",
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
    # No reverse: the prior copy lives in 0015_realign_plan_geographic_copy and
    # is re-applied by rolling back to it.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0018_basic_plan_state_everywhere"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
