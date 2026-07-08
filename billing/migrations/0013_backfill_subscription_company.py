from django.db import migrations


def backfill_subscription_company(apps, schema_editor):
    """Attach every existing user-level subscription to a company the buying
    user OWNS.

    Plans became company-scoped (Subscription.company). Historically a
    subscription was tied only to the buying User, so every legacy row has a
    NULL company. A plan belongs to a company and is paid for by that
    company's OWNER, so we attach each user's subscriptions to the company
    they own — preferring their primary_company when they own it, otherwise
    their oldest owned company.

    Non-owners matter here: several users can share the same primary_company
    (the owner plus everyone who JOINED it). Attaching all of their
    subscriptions to that one company would put two active rows on it and
    violate unique_active_subscription_per_company. Scoping to owned companies
    avoids that — owner_user is a single FK, so each company has exactly one
    owner, and the OLD schema allowed that owner at most one active
    subscription. Users who own no company are left NULL (the Free floor
    until they create/select a company).
    """
    Subscription = apps.get_model("billing", "Subscription")
    Company = apps.get_model("accounts", "Company")

    qs = (
        Subscription.objects
        .filter(company__isnull=True, user__isnull=False)
        .select_related("user")
    )
    for sub in qs.iterator():
        user = sub.user
        target_company_id = None

        # Prefer the user's primary_company, but only if they OWN it.
        primary_company_id = getattr(user, "primary_company_id", None)
        if primary_company_id:
            owns_primary = Company.objects.filter(
                id=primary_company_id, owner_user_id=user.id
            ).exists()
            if owns_primary:
                target_company_id = primary_company_id

        # Otherwise fall back to the user's oldest owned company.
        if target_company_id is None:
            owned = (
                Company.objects
                .filter(owner_user_id=user.id)
                .order_by("created_at")
                .values_list("id", flat=True)
                .first()
            )
            if owned:
                target_company_id = owned

        if target_company_id:
            sub.company_id = target_company_id
            sub.save(update_fields=["company"])


def reverse_noop(apps, schema_editor):
    # No-op: we don't strip the company linkage on reverse. Re-running the
    # forward migration is idempotent (only touches company__isnull=True rows).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0012_remove_subscription_unique_active_subscription_per_user_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_subscription_company, reverse_noop),
    ]
