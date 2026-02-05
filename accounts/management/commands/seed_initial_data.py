import random
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.utils.text import slugify

from faker import Faker

from accounts.models import (
    Tenant,
    Company,
    User,
    Permission,
    Role,
    RolePermission,
    UserRole,
    Classification,
    AuditLog,
)

fake = Faker()


class Command(BaseCommand):
    help = "Seed full system data with 20 tenants and mixed behavior"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("🌱 Seeding initial data..."))

        self.seed_permissions()
        self.seed_tenants()

        self.stdout.write(self.style.SUCCESS("✅ All data seeded successfully"))

    # --------------------------------------------------
    # Permissions (global)
    # --------------------------------------------------
    def seed_permissions(self):
        self.permissions = {}

        permission_list = [
            ("tenant.view", "View tenants"),
            ("company.view", "View companies"),
            ("company.manage", "Manage companies"),
            ("user.view", "View users"),
            ("user.manage", "Manage users"),
            ("role.view", "View roles"),
            ("role.manage", "Manage roles"),
            ("audit.view", "View audit logs"),
        ]

        for code, description in permission_list:
            perm, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"description": description},
            )
            self.permissions[code] = perm

    # --------------------------------------------------
    # Tenants (20 with active/inactive mix)
    # --------------------------------------------------
    def seed_tenants(self):
        for i in range(1, 21):
            tenant, _ = Tenant.objects.get_or_create(
                slug=f"tenant-{i}",
                defaults={
                    "name": f"Tenant {i}",
                    "is_active": i % 5 != 0,  # every 5th inactive
                },
            )

            self.seed_companies(tenant)
            self.seed_roles(tenant)
            self.seed_users(tenant)
            self.seed_classifications(tenant)

    # --------------------------------------------------
    # Companies (per tenant)
    # --------------------------------------------------
    def seed_companies(self, tenant):
        for i in range(1, 6):
            Company.objects.get_or_create(
                tenant=tenant,
                name=f"{tenant.name} Company {i}",
                defaults={
                    "registration_id": f"{tenant.slug.upper()}-{i}",
                    "is_active": i % 2 == 1,
                },
            )

    # --------------------------------------------------
    # Roles + permissions (per tenant)
    # --------------------------------------------------
    def seed_roles(self, tenant):
        role_permission_map = {
            "Admin": list(self.permissions.values()),
            "Manager": [
                self.permissions["company.view"],
                self.permissions["company.manage"],
                self.permissions["user.view"],
            ],
            "Viewer": [
                self.permissions["company.view"],
                self.permissions["user.view"],
            ],
        }

        self.roles = []

        for role_name, perms in role_permission_map.items():
            role, _ = Role.objects.get_or_create(
                tenant=tenant,
                name=role_name,
                defaults={
                    "is_system_role": role_name == "Admin",
                },
            )

            RolePermission.objects.filter(role=role).delete()

            for perm in perms:
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=perm,
                )

            self.roles.append(role)

    # --------------------------------------------------
    # Users + role assignments + audit logs
    # --------------------------------------------------
    def seed_users(self, tenant):
        for i in range(1, 11):  # 10 users per tenant
            user, _ = User.objects.get_or_create(
                tenant=tenant,
                email=f"user{i}@{tenant.slug}.com",
                defaults={
                    "full_name": fake.name(),
                    "password": make_password("password123"),
                    "is_active": i % 4 != 0,  # every 4th inactive
                    "is_staff": i == 1,
                },
            )

            # Assign 1–2 roles
            for role in random.sample(self.roles, random.randint(1, 2)):
                UserRole.objects.get_or_create(
                    user=user,
                    role=role,
                )

            # Immutable audit log
            AuditLog.objects.create(
                tenant=tenant,
                actor=user,
                action="user.created",
                entity_type="User",
                entity_id=user.id,
                metadata={"seeded": True},
                ip_address="127.0.0.1",
            )

    # --------------------------------------------------
    # Classifications (per tenant)
    # --------------------------------------------------
    def seed_classifications(self, tenant):
        classification_data = [
            ("STATUS_ACTIVE", "Active"),
            ("STATUS_INACTIVE", "Inactive"),
            ("STATUS_SUSPENDED", "Suspended"),
            ("LEVEL_BASIC", "Basic"),
            ("LEVEL_PREMIUM", "Premium"),
        ]

        for key, label in classification_data:
            Classification.objects.get_or_create(
                tenant=tenant,
                key=key,
                defaults={"label": label},
            )
