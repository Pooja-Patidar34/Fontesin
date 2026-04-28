from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0005_reseed_plans_mvp"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="bank_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="invoice",
            name="sender_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="invoice",
            name="fx_source_currency",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="invoice",
            name="fx_source_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="fx_rate",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
    ]
