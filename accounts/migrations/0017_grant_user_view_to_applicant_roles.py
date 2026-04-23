from django.db import migrations


APPLICANT_ROLE_CODES = ["CONSULTANT", "COORDINATOR", "FRANCHISE"]
PERMISSION_CODE = "user.view"
PERMISSION_DESCRIPTION = "Can view users within their own company."


def grant_user_view(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    perm, _ = Permission.objects.get_or_create(
        code=PERMISSION_CODE,
        defaults={"description": PERMISSION_DESCRIPTION},
    )

    for role in Role.objects.filter(code__in=APPLICANT_ROLE_CODES):
        role.permissions.add(perm)


def revoke_user_view(apps, schema_editor):
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
        ("accounts", "0016_grant_company_view_to_applicant_roles"),
    ]

    operations = [
        migrations.RunPython(grant_user_view, revoke_user_view),
    ]
