from django.db import migrations


APPLICANT_ROLE_CODES = ["CONSULTANT", "COORDINATOR", "FRANCHISE"]
PERMISSION_CODE = "company.view"
PERMISSION_DESCRIPTION = "Can view companies they are linked to within their tenant."


def grant_company_view(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    perm, _ = Permission.objects.get_or_create(
        code=PERMISSION_CODE,
        defaults={"description": PERMISSION_DESCRIPTION},
    )

    for role in Role.objects.filter(code__in=APPLICANT_ROLE_CODES):
        role.permissions.add(perm)


def revoke_company_view(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    try:
        perm = Permission.objects.get(code=PERMISSION_CODE)
    except Permission.DoesNotExist:
        return

    for role in Role.objects.filter(code__in=APPLICANT_ROLE_CODES):
        role.permissions.remove(perm)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_merge_20260415_1141"),
    ]

    operations = [
        migrations.RunPython(grant_company_view, revoke_company_view),
    ]
