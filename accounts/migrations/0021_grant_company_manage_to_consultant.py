from django.db import migrations


CONSULTANT_ROLE_CODE = "CONSULTANT"
PERMISSION_CODE = "company.manage"
PERMISSION_DESCRIPTION = "Can create and update companies they are linked to."


def grant_company_manage(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    perm, _ = Permission.objects.get_or_create(
        code=PERMISSION_CODE,
        defaults={"description": PERMISSION_DESCRIPTION},
    )

    for role in Role.objects.filter(code=CONSULTANT_ROLE_CODE):
        role.permissions.add(perm)


def revoke_company_manage(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    try:
        perm = Permission.objects.get(code=PERMISSION_CODE)
    except Permission.DoesNotExist:
        return

    for role in Role.objects.filter(code=CONSULTANT_ROLE_CODE):
        role.permissions.remove(perm)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_rename_accounts_co_user_id_b1f4d2_idx_accounts_co_user_id_77e206_idx"),
    ]

    operations = [
        migrations.RunPython(grant_company_manage, revoke_company_manage),
    ]
