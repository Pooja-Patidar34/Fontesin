from django.db import migrations


def grandfather_existing_consultants(apps, schema_editor):
    """Existing consultants predate the 'consultant must complete the apply
    form' gate, so mark them 'approved' to avoid forcing already-onboarded
    consultants back onto the apply form. New consultant registrations start
    'pending' (the model default) and go through Veriff → apply as intended.
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        role__code__in=["consultant", "CONSULTANT"]
    ).exclude(application_status="approved").update(application_status="approved")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0039_user_application_decided_at_and_more'),
    ]

    operations = [
        migrations.RunPython(grandfather_existing_consultants, noop_reverse),
    ]
