from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import (
    Tenant, Company, User, Role, Permission,
    UserCompany, UserCompanyRole
)

SUPERUSER_EMAIL = "admin@test.com"
SUPERUSER_PASSWORD = "admin123"


class Command(BaseCommand):
    help = "Seed tenants, companies, users, roles, permissions"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("🌱 Seeding data...")

        # -------------------------------------------------
        # Permissions
        # -------------------------------------------------
        permissions = [
            "tenant.view", "tenant.manage",
            "company.view", "company.manage",
            "user.view", "user.manage",
            "role.view", "role.manage",
            "audit.view",
        ]

        permission_objs = {}
        for code in permissions:
            permission_objs[code], _ = Permission.objects.get_or_create(
                code=code,
                defaults={"description": code.replace(".", " ").title()}
            )

        # -------------------------------------------------
        # Global tenant (for superuser)
        # -------------------------------------------------
        global_tenant, _ = Tenant.objects.get_or_create(
            name="Global Tenant"
        )

        # -------------------------------------------------
        # Superuser
        # -------------------------------------------------
        superuser, created = User.objects.get_or_create(
            email=SUPERUSER_EMAIL,
            defaults={
                "tenant": global_tenant,
                "full_name": "Global Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }
        )

        if created:
            superuser.set_password(SUPERUSER_PASSWORD)
            superuser.save()

        # -------------------------------------------------
        # Seed tenants
        # -------------------------------------------------
        for t in range(1, 11):
            tenant, _ = Tenant.objects.get_or_create(
                name=f"Tenant {t}"
            )

            # Tenant admin role
            tenant_admin_role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name="tenant_admin",
            )
            tenant_admin_role.permissions.set(permission_objs.values())

            # -------------------------------------------------
            # Companies
            # -------------------------------------------------
            for c in range(1, 6):
                company, _ = Company.objects.get_or_create(
                    tenant=tenant,
                    name=f"Tenant {t} Company {c}"
                )

                # -------------------------------------------------
                # Users
                # -------------------------------------------------
                for u in range(1, 6):
                    email = f"user{u}_c{c}_t{t}@test.com"

                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            "tenant": tenant,
                            "full_name": f"User {u} T{t} C{c}",
                            "is_active": True,
                        }
                    )

                    if created:
                        user.set_password("test123")
                        user.save()

                    user_company, _ = UserCompany.objects.get_or_create(
                        user=user,
                        company=company,
                        defaults={"is_primary": True}
                    )

                    UserCompanyRole.objects.get_or_create(
                        user_company=user_company,
                        role=tenant_admin_role
                    )

        self.stdout.write(self.style.SUCCESS("✅ Seeding completed"))
