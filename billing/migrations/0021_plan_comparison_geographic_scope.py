from django.db import migrations


# The /membership/ comparison table still described the old country/region
# model — "Domicile country" for Free, "1 country" for Basic, "1 region" for
# Pro — while the code enforces town → state → continent → worldwide
# (billing.utils.get_user_geographic_scope). Migrations 0015 / 0016 / 0018 /
# 0020 realigned each plan's tagline, best_for and `details` blob, but
# `comparison` is a separate JSON column and was left behind.
#
# The values here are also the msgids in
# billing.plan_i18n.COMPARISON_VALUE_MSGIDS, which is what lets the table
# render in the viewer's language instead of always in English.
COMPARISON_SCOPE = {
    "free": {
        "geographic_scope": "Your town",
        "search_scope": "Your town",
    },
    "basic": {
        "geographic_scope": "Your state",
        "search_scope": "Your state",
    },
    "pro": {
        "geographic_scope": "Your continent",
        "search_scope": "Your continent",
    },
    "global": {
        "geographic_scope": "Worldwide",
        "search_scope": "All countries / regions",
    },
}


def realign(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")
    for code, scope in COMPARISON_SCOPE.items():
        plan = CommercialPlan.objects.filter(code=code).first()
        if not plan:
            continue
        comparison = plan.comparison or {}
        if not isinstance(comparison, dict):
            continue
        # Only the two scope cells change; every other key (the booleans the
        # table renders as ticks, and anything a deployment added by hand)
        # is left exactly as it was.
        comparison.update(scope)
        plan.comparison = comparison
        plan.save(update_fields=["comparison"])


def noop_reverse(apps, schema_editor):
    # No reverse: the previous values described a scope model the product no
    # longer has, so restoring them would only re-introduce the mismatch.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0020_pro_plan_continent_scope"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
