from django.db import migrations, models


def backfill_billing_period(apps, schema_editor):
    """Copy each Subscription's current plan.billing_period onto the row.

    Run-once: future Subscriptions write the value at creation time, so
    this only matters for rows that existed before the column did.
    """
    Subscription = apps.get_model("billing", "Subscription")
    for sub in Subscription.objects.select_related("plan").iterator():
        period = getattr(sub.plan, "billing_period", "yearly") if sub.plan_id else "yearly"
        if sub.billing_period != period:
            sub.billing_period = period
            sub.save(update_fields=["billing_period"])


def noop_reverse(apps, schema_editor):
    # The field is dropped on reverse; nothing to undo at the data level.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0010_realign_plan_best_for"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="billing_period",
            field=models.CharField(
                choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
                default="yearly",
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_billing_period, noop_reverse),
    ]
