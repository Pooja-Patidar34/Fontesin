from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0006_invoice_snapshots"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="subscription",
            name="unique_active_subscription_per_user",
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["active", "trial"])),
                fields=("user",),
                name="unique_active_subscription_per_user",
            ),
        ),
    ]
