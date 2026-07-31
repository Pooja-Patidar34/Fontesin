"""Backfill Tenant rows that were saved with an empty slug.

`Tenant` carried two `save()` definitions: the slug generator, and a later one
enforcing the franchise owner rule. The second silently shadowed the first, so
every node created through approval got `slug = ""`. The first such row saved
fine; the next one hit the unique constraint on `slug`, which is why approving a
franchise application failed with an IntegrityError.

`save()` is now a single method that does both, and this backfills the rows the
shadowed version left behind so they stop occupying the empty-string slug.
"""

from django.db import migrations
from django.utils.text import slugify


def fill_blank_slugs(apps, schema_editor):
    Tenant = apps.get_model("accounts", "Tenant")
    max_len = Tenant._meta.get_field("slug").max_length

    for tenant in Tenant.objects.filter(slug=""):
        base = slugify(tenant.name)[:max_len] or f"tenant-{str(tenant.id)[:8]}"
        slug = base
        counter = 1
        while Tenant.objects.filter(slug=slug).exclude(id=tenant.id).exists():
            suffix = f"-{counter}"
            slug = base[: max_len - len(suffix)] + suffix
            counter += 1
        tenant.slug = slug
        tenant.save(update_fields=["slug"])


def noop(apps, schema_editor):
    """No reverse — blanking the slugs again would just restore the clash."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0053_restore_business_user_franchise_holders"),
    ]

    operations = [
        migrations.RunPython(fill_blank_slugs, noop),
    ]
