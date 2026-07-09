# Add a partial-unique constraint guaranteeing at most one active/trial
# account-level (company IS NULL) subscription per user.
#
# Plans became company-scoped in 0012, which dropped the old
# `unique_active_subscription_per_user` constraint. That left account-level
# Free rows (created by `ensure_account_free_subscription` for company-less
# business users) with NO uniqueness guard, so a check-then-create race could
# produce duplicate active account-level subs and make the plan resolver's
# no-company fallback (`get_active_subscription`) non-deterministic.
#
# Before adding the constraint we defensively collapse any pre-existing
# duplicates: for each user with more than one active/trial company-less sub,
# keep the most recently created row and mark the rest "cancelled".

from django.db import migrations, models


def _dedupe_account_level_active_subs(apps, schema_editor):
    Subscription = apps.get_model("billing", "Subscription")
    dupes = (
        Subscription.objects
        .filter(status__in=["active", "trial"], company__isnull=True)
        .values("user")
        .annotate(n=models.Count("id"))
        .filter(n__gt=1)
    )
    for row in dupes:
        user_id = row["user"]
        subs = list(
            Subscription.objects
            .filter(status__in=["active", "trial"], company__isnull=True, user_id=user_id)
            .order_by("-created_at", "-id")
        )
        # Keep subs[0] (newest); cancel the rest.
        for sub in subs[1:]:
            sub.status = "cancelled"
            sub.save(update_fields=["status"])


def _noop_reverse(apps, schema_editor):
    # Cancelling duplicates isn't reversible (we can't know which were dupes);
    # dropping the constraint on reverse is handled by RemoveConstraint below.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0013_backfill_subscription_company'),
    ]

    operations = [
        migrations.RunPython(_dedupe_account_level_active_subs, _noop_reverse),
        migrations.AddConstraint(
            model_name='subscription',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status__in', ['active', 'trial']), ('company__isnull', True)),
                fields=('user',),
                name='unique_active_account_subscription_per_user',
            ),
        ),
    ]
