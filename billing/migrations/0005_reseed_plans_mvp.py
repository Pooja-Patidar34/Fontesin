from django.db import migrations


def seed_plans_mvp(apps, schema_editor):
    CommercialPlan = apps.get_model("billing", "CommercialPlan")

    plans = [
        {
            "code": "free",
            "name": "FREE",
            "tagline": "Get started in your domicile country",
            "icon": "\U0001f331",
            "price": 0,
            "original_price": None,
            "currency": "USD",
            "billing_period": "yearly",
            "badge_text": "",
            "badge_style": "",
            "is_popular": False,
            "sort_order": 1,
            "best_for": "Companies exploring the platform within their domicile country before committing to a paid plan.",
            "best_for_style": "neutral",
            "features": [
                {"text": "1 country only (domicile by default)", "included": True},
                {"text": "Account registration & login", "included": True},
                {"text": "Company profile creation", "included": True},
                {"text": "Basic public listing (name, industry, country/region/city)", "included": True},
                {"text": "Edit own company profile", "included": True},
                {"text": "Company certification", "included": False},
                {"text": "Partnerships", "included": False},
                {"text": "Messaging", "included": False},
                {"text": "Saving selected databases", "included": False},
            ],
            "details": {
                "visibility": [
                    {"label": "Profile Visibility", "value": "Limited (basic fields only)", "positive": None},
                    {"label": "Geographic Access", "value": "Domicile country only", "positive": None},
                    {"label": "Search Scope", "value": "Domicile country", "positive": None},
                ],
                "services": [
                    {"label": "Company Certification", "value": "Not included", "positive": False},
                    {"label": "Partnerships", "value": "Not included", "positive": False},
                    {"label": "Messaging", "value": "Not included", "positive": False},
                    {"label": "Saving Databases", "value": "Not included", "positive": False},
                ],
            },
            "comparison": {
                "profile_visibility": "Limited",
                "geographic_scope": "Domicile country",
                "search_scope": "Domicile country",
                "company_certification": False,
                "partnerships": False,
                "messaging": False,
                "saving_databases": False,
            },
        },
        {
            "code": "basic",
            "name": "BASIC",
            "tagline": "Full access in one selected country",
            "icon": "\U0001f680",
            "price": 150,
            "original_price": 200,
            "currency": "USD",
            "billing_period": "yearly",
            "badge_text": "",
            "badge_style": "",
            "is_popular": False,
            "sort_order": 2,
            "best_for": "Companies operating in a single national market who need full visibility and services.",
            "best_for_style": "warning",
            "features": [
                {"text": "Everything in FREE", "included": True},
                {"text": "Full company profile visibility", "included": True},
                {"text": "Access to one selected country / local market", "included": True},
                {"text": "Company certification", "included": True},
                {"text": "Partnerships", "included": True},
                {"text": "Messaging", "included": True},
                {"text": "Saving selected databases", "included": True},
                {"text": "Visible & searchable within licensed scope", "included": True},
            ],
            "details": {
                "visibility": [
                    {"label": "Profile Visibility", "value": "Full", "positive": True},
                    {"label": "Geographic Access", "value": "1 selected country", "positive": None},
                    {"label": "Search Scope", "value": "Selected country", "positive": None},
                ],
                "services": [
                    {"label": "Company Certification", "value": "Included", "positive": True},
                    {"label": "Partnerships", "value": "Included", "positive": True},
                    {"label": "Messaging", "value": "Included", "positive": True},
                    {"label": "Saving Databases", "value": "Included", "positive": True},
                ],
            },
            "comparison": {
                "profile_visibility": "Full",
                "geographic_scope": "1 country",
                "search_scope": "Selected country",
                "company_certification": True,
                "partnerships": True,
                "messaging": True,
                "saving_databases": True,
            },
        },
        {
            "code": "pro",
            "name": "PRO",
            "tagline": "Full access across one selected region",
            "icon": "\U0001f4bc",
            "price": 1000,
            "original_price": 1200,
            "currency": "USD",
            "billing_period": "yearly",
            "badge_text": "\u2b50 Most Popular",
            "badge_style": "primary",
            "is_popular": True,
            "sort_order": 3,
            "best_for": "Companies operating across a regional market (e.g. Europe, North America, Asia).",
            "best_for_style": "success",
            "features": [
                {"text": "Everything in BASIC", "included": True},
                {"text": "Access to one selected region", "included": True},
                {"text": "Europe / North America / South America", "included": True},
                {"text": "Asia / Middle East / Australia & Oceania", "included": True},
                {"text": "Visible & searchable within regional scope", "included": True},
            ],
            "details": {
                "visibility": [
                    {"label": "Profile Visibility", "value": "Full", "positive": True},
                    {"label": "Geographic Access", "value": "1 selected region", "positive": None},
                    {"label": "Search Scope", "value": "Selected region", "positive": None},
                ],
                "services": [
                    {"label": "Company Certification", "value": "Included", "positive": True},
                    {"label": "Partnerships", "value": "Included", "positive": True},
                    {"label": "Messaging", "value": "Included", "positive": True},
                    {"label": "Saving Databases", "value": "Included", "positive": True},
                ],
            },
            "comparison": {
                "profile_visibility": "Full",
                "geographic_scope": "1 region",
                "search_scope": "Selected region",
                "company_certification": True,
                "partnerships": True,
                "messaging": True,
                "saving_databases": True,
            },
        },
        {
            "code": "global",
            "name": "GLOBAL",
            "tagline": "Worldwide visibility & access",
            "icon": "\U0001f310",
            "price": 2000,
            "original_price": 2400,
            "currency": "USD",
            "billing_period": "yearly",
            "badge_text": "\U0001f30d Best Value",
            "badge_style": "save",
            "is_popular": False,
            "sort_order": 4,
            "best_for": "Companies operating internationally who need worldwide visibility and search.",
            "best_for_style": "info",
            "features": [
                {"text": "Everything in PRO", "included": True},
                {"text": "Global visibility", "included": True},
                {"text": "Searchable across all available countries / regions", "included": True},
            ],
            "details": {
                "visibility": [
                    {"label": "Profile Visibility", "value": "Full", "positive": True},
                    {"label": "Geographic Access", "value": "Worldwide", "positive": True},
                    {"label": "Search Scope", "value": "All countries / regions", "positive": True},
                ],
                "services": [
                    {"label": "Company Certification", "value": "Included", "positive": True},
                    {"label": "Partnerships", "value": "Included", "positive": True},
                    {"label": "Messaging", "value": "Included", "positive": True},
                    {"label": "Saving Databases", "value": "Included", "positive": True},
                ],
            },
            "comparison": {
                "profile_visibility": "Full",
                "geographic_scope": "Worldwide",
                "search_scope": "All countries / regions",
                "company_certification": True,
                "partnerships": True,
                "messaging": True,
                "saving_databases": True,
            },
        },
    ]

    for plan_data in plans:
        CommercialPlan.objects.update_or_create(
            code=plan_data["code"],
            defaults=plan_data,
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0004_alter_commercialplan_code_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_plans_mvp, reverse_noop),
    ]
