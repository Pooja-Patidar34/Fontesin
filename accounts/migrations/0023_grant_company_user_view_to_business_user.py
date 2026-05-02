from django.db import migrations


BUSINESS_USER_ROLE_CODE = "BUSINESS_USER"

PERMISSIONS = [
    ("audit.view", "Can view audit logs."),
    ("company.manage", "Can create and update companies they are linked to."),
    ("company.view", "Can view companies they are linked to within their tenant."),
    ("role.view", "Can view roles."),
    ("user.manage", "Can create, update, and delete users within their own company."),
    ("user.view", "Can view users within their own company."),
]


def grant_business_user_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    role = Role.objects.filter(code=BUSINESS_USER_ROLE_CODE).first()
    if not role:
        return

    for code, description in PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": description},
        )
        role.permissions.add(perm)


def revoke_business_user_permissions(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Permission = apps.get_model("accounts", "Permission")

    role = Role.objects.filter(code=BUSINESS_USER_ROLE_CODE).first()
    if not role:
        return

    for code, _description in PERMISSIONS:
        try:
            perm = Permission.objects.get(code=code)
        except Permission.DoesNotExist:
            continue
        role.permissions.remove(perm)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_company_unique_company_registration_id"),
    ]

    operations = [
        migrations.RunPython(grant_business_user_permissions, revoke_business_user_permissions),
    ]
