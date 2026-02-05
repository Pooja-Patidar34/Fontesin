from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password

from accounts.models import (
    Tenant,
    Company,
    User,
    Permission,
    Role,
    RolePermission,
    UserRole,
    Classification,
)


class Command(BaseCommand):
    help = "Seed initial data for admin panel"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding initial data..."))

        # --------------------------------------------------
        # 1. Tenant
        # --------------------------------------------------
        tenant, _ = Tenant.objects.get_or_create(
            slug="default",
            defaults={
                "name": "Default Tenant",
                "is_active": True,
            },
        )

        # --------------------------------------------------
        # 2. Company
        # --------------------------------------------------
        company, _ = Company.objects.get_or_create(
            tenant=tenant,
            name="Default Company",
            defaults={
                "registration_id": "REG-001",
                "is_active": True,
            },
        )

        # --------------------------------------------------
        # 3. Permissions
        # --------------------------------------------------
        permission_codes = [
            ("tenant.view", "View tenants"),
            ("company.view", "View companies"),
            ("company.manage", "Create/update companies"),
            ("user.view", "View users"),
            ("user.manage", "Create/update users"),
            ("role.view", "View roles"),
            ("role.manage", "Create/update roles"),
            ("audit.view", "View audit logs"),
        ]

        permissions = {}
        for code, description in permission_codes:
            perm, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"description": description},
            )
            permissions[code] = perm

        # --------------------------------------------------
        # 4. Admin Role (system role)
        # --------------------------------------------------
        admin_role, _ = Role.objects.get_or_create(
            tenant=tenant,
            name="Admin",
            defaults={
                "is_system_role": True,
            },
        )

        # Attach all permissions to Admin role
        for perm in permissions.values():
            RolePermission.objects.get_or_create(
                role=admin_role,
                permission=perm,
            )

        # --------------------------------------------------
        # 5. Admin User
        # --------------------------------------------------
        admin_email = "admin@example.com"

        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            tenant=tenant,
            defaults={
                "full_name": "System Admin",
                "is_active": True,
                "is_staff": True,
                "password": make_password("admin123"),
            },
        )

        if not created:
            # Ensure flags are correct if user already exists
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.save(update_fields=["is_staff", "is_active"])

        # --------------------------------------------------
        # 6. Assign role to admin user
        # --------------------------------------------------
        UserRole.objects.get_or_create(
            user=admin_user,
            role=admin_role,
        )

        # --------------------------------------------------
        # 7. Sample classifications (optional)
        # --------------------------------------------------
        classifications = [
            ("STATUS_ACTIVE", "Active"),
            ("STATUS_INACTIVE", "Inactive"),
        ]

        for key, label in classifications:
            Classification.objects.get_or_create(
                tenant=tenant,
                key=key,
                defaults={"label": label},
            )

        self.stdout.write(self.style.SUCCESS("✅ Initial data seeded successfully"))
        self.stdout.write(self.style.SUCCESS("Admin login: admin@example.com / admin123"))
