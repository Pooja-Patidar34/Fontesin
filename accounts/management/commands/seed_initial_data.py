import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password

from accounts.models import (
    Tenant, Company, User,
    Permission, Role, RolePermission,
    UserCompany, UserCompanyRole,
)

PASSWORD = "Test@123"


class Command(BaseCommand):
    help = "Seed large, clean RBAC data for dashboard testing"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("🌱 Seeding bulk RBAC data...")

        # -------------------------------------------------
        # PERMISSIONS (GLOBAL)
        # -------------------------------------------------
        permission_defs = [
            ("company.manage", "Manage companies"),
            ("user.manage", "Manage users"),
            ("role.manage", "Manage roles"),
            ("audit.view", "View audit logs"),
            ("dashboard.view", "View dashboard"),
        ]

        permissions = {}
        for code, desc in permission_defs:
            perm, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"description": desc}
            )
            permissions[code] = perm

        # -------------------------------------------------
        # SUPER ADMIN (SYSTEM USER)
        # -------------------------------------------------
        system_tenant, _ = Tenant.objects.get_or_create(
            name="System Tenant",
            slug="system",
            defaults={"is_active": True}
        )

        super_admin, _ = User.objects.get_or_create(
            email="superadmin@system.com",
            defaults={
                "full_name": "System Super Admin",
                "password": make_password(PASSWORD),
                "tenant": system_tenant,
                "is_superuser": True,
                "is_staff": True,
            }
        )

        # -------------------------------------------------
        # TENANTS, ROLES, COMPANIES, USERS
        # -------------------------------------------------
        for t in range(1, 6):  # 5 tenants
            tenant = Tenant.objects.create(
                name=f"Tenant {t}",
                slug=f"tenant-{t}",
                is_active=True,
            )

            # Tenant-scoped roles
            tenant_admin_role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name="tenant_admin",
            )

            company_user_role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name="company_user",
            )

            # Role permissions
            for code in ["company.manage", "user.manage", "audit.view", "dashboard.view"]:
                RolePermission.objects.get_or_create(
                    role=tenant_admin_role,
                    permission=permissions[code],
                )

            RolePermission.objects.get_or_create(
                role=company_user_role,
                permission=permissions["dashboard.view"],
            )

            # Tenant admin user
            tenant_admin = User.objects.create_user(
                email=f"tenant{t}_admin@test.com",
                password=PASSWORD,
                full_name=f"Tenant {t} Admin",
                tenant=tenant,
                is_staff=True,
            )

            # Companies
            for c in range(1, 11):  # 10 companies per tenant
                company = Company.objects.create(
                    tenant=tenant,
                    name=f"Company {t}-{c}",
                    is_active=True,
                )

                # Attach tenant admin to company
                admin_uc = UserCompany.objects.create(
                    user=tenant_admin,
                    company=company,
                    is_primary=(c == 1),
                )

                UserCompanyRole.objects.create(
                    user_company=admin_uc,
                    role=tenant_admin_role,
                )

                # Company users
                for u in range(1, 11):  # 10 users per company
                    user = User.objects.create_user(
                        email=f"user{t}{c}{u}@test.com",
                        password=PASSWORD,
                        full_name=f"User {t}-{c}-{u}",
                        tenant=tenant,
                        is_staff=False,
                    )

                    uc = UserCompany.objects.create(
                        user=user,
                        company=company,
                        is_primary=True,
                    )

                    UserCompanyRole.objects.create(
                        user_company=uc,
                        role=company_user_role,
                    )

        self.stdout.write(self.style.SUCCESS("✅ Bulk seed completed successfully"))
        self.stdout.write("🔑 Super Admin → superadmin@system.com / Test@123")
