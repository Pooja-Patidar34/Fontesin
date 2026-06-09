from django.db import migrations


def grandfather_existing_consultants(apps, schema_editor):
    """Consultants now require super-admin approval (added to the gated roles).
    Any consultant that already exists at the time of this deploy predates the
    approval gate, so mark them 'approved' to avoid locking already-onboarded
    consultants out of the dashboard. New consultant registrations start
    'pending' (the model default) and go Veriff -> region mask -> approval.

    This repeats migration 0040 because consultants created BETWEEN 0040 and
    this change are sitting at 'submitted' (they had instant access then) and
    would otherwise be bounced to the pending-review page once gating turns on.
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        role__code__in=["consultant", "CONSULTANT"]
    ).exclude(application_status="approved").update(application_status="approved")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0042_contactmessage'),
    ]

    operations = [
        migrations.RunPython(grandfather_existing_consultants, noop_reverse),
    ]
