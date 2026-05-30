from django.db import migrations


def backfill_bu_primary_company(apps, schema_editor):
    """Set primary_company for business users who own a company but never had
    one linked as primary.

    The Company Database create modal historically set only Company.owner_user,
    not User.primary_company. Those companies showed under "My Companies"
    (owner_user) but not on the user's Profile page (which reads
    primary_company). This backfills the missing linkage for existing rows so
    the profile matches My Companies, the same way the view fix now does for
    new companies. Newest owned company wins when a user owns several.
    """
    User = apps.get_model("accounts", "User")
    Company = apps.get_model("accounts", "Company")
    UserCompany = apps.get_model("accounts", "UserCompany")

    bu_users = User.objects.filter(
        role__code__iexact="business_user",
        primary_company__isnull=True,
        is_deleted=False,
    )
    for user in bu_users:
        company = (
            Company.objects.filter(owner_user=user, is_deleted=False)
            .order_by("-created_at")
            .first()
        )
        if not company:
            continue
        user.primary_company = company
        user.save(update_fields=["primary_company"])
        UserCompany.objects.get_or_create(
            user=user,
            company=company,
            defaults={"is_primary": True},
        )


def reverse_noop(apps, schema_editor):
    # Can't reliably tell backfilled links apart from genuine ones; leave them.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0037_notification_new_user_kind"),
    ]

    operations = [
        migrations.RunPython(backfill_bu_primary_company, reverse_noop),
    ]
