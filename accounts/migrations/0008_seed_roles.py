from django.db import migrations


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")

    roles = [
        {
            "name": "business_user",
            "code": "BUSINESS_USER",
            "tier_level": 1,
            "is_franchise": False,
        },
        {
            "name": "consultant",
            "code": "CONSULTANT",
            "tier_level": 2,
            "is_franchise": False,
        },
        {
            "name": "coordinator",
            "code": "COORDINATOR",
            "tier_level": 3,
            "is_franchise": False,
        },
        {
            "name": "franchise",
            "code": "FRANCHISE",
            "tier_level": 4,
            "is_franchise": True,
        },
    ]

    for role_data in roles:
        Role.objects.get_or_create(
            code=role_data["code"],
            defaults=role_data,
        )


def reverse_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(
        code__in=["BUSINESS_USER", "CONSULTANT", "COORDINATOR", "FRANCHISE"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_alter_role_code"),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_roles),
    ]
