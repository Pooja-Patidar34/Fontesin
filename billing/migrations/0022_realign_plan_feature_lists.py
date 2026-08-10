from django.db import migrations


# The feature bullets on /membership/ are translated by matching the stored
# text against the canonical copy in billing.plan_i18n.PLAN_CANONICAL, position
# by position: a row whose text differs from the seed is assumed to be
# hand-edited and is rendered verbatim, untranslated.
#
# That match had broken. The stored lists still described the old
# country/region model ("1 country only (domicile by default)", "Access to one
# selected region"), so every bullet fell through to the raw English even in
# French, German and Spanish — and described a reach the product no longer has.
#
# These lists are the same text as PLAN_CANONICAL, in the same order. Change
# them together or the bullets silently stop translating again.
PLAN_FEATURES = {
    "free": [
        {"text": "Your own town only", "included": True},
        {"text": "Company names only — no further details", "included": True},
        {"text": "Account registration & login", "included": True},
        {"text": "Company profile creation", "included": True},
        {"text": "Edit own company profile", "included": True},
        {"text": "Company certification", "included": False},
        {"text": "Partnerships", "included": False},
        {"text": "Messaging", "included": False},
        {"text": "Saving selected databases", "included": False},
    ],
    "basic": [
        {"text": "Everything in FREE", "included": True},
        {"text": "Your whole state or region", "included": True},
        {"text": "Full company profile visibility", "included": True},
        {"text": "Company certification", "included": True},
        {"text": "Partnerships", "included": True},
        {"text": "Messaging", "included": True},
        {"text": "Saving selected databases", "included": True},
        {"text": "Visible & searchable within licensed scope", "included": True},
    ],
    "pro": [
        {"text": "Everything in BASIC", "included": True},
        {"text": "Your whole continent, every country on it", "included": True},
        {"text": "Europe / North America / South America", "included": True},
        {"text": "Africa / Asia / Australia & Oceania", "included": True},
        {"text": "Visible & searchable across the continent", "included": True},
    ],
    "global": [
        {"text": "Everything in PRO", "included": True},
        {"text": "Every country, worldwide", "included": True},
        {
            "text": "Searchable across all available countries / regions",
            "included": True,
        },
    ],
}


def realign(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")
    for code, features in PLAN_FEATURES.items():
        plan = CommercialPlan.objects.filter(code=code).first()
        if not plan:
            continue
        plan.features = features
        plan.save(update_fields=["features"])


def noop_reverse(apps, schema_editor):
    # No reverse: the previous bullets described the retired country/region
    # model, so restoring them would only re-break the copy and the matching.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0021_plan_comparison_geographic_scope"),
    ]

    operations = [
        migrations.RunPython(realign, noop_reverse),
    ]
