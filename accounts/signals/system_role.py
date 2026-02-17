# roles/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Tenant, Role, Permission, RolePermission


@receiver(post_save, sender=Tenant)
def create_default_tenant_roles(sender, instance, created, **kwargs):
    if not created:
        return

    # Create tenant_admin role
    role, created = Role.objects.get_or_create(
        tenant=instance,
        name="tenant_admin",
    )

    if not created:
        return

    # Assign ALL permissions
    permissions = Permission.objects.all()

    RolePermission.objects.bulk_create([
        RolePermission(role=role, permission=permission)
        for permission in permissions
    ])
