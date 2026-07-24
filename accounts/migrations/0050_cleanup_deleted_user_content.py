from django.db import migrations


def cleanup_deleted_user_content(apps, schema_editor):
    """Backfill the user-delete cascade for users deleted BEFORE it existed.

    Historically, deleting a user only soft-deleted the User row; the companies
    and listings they owned were left visible. This one-off pass applies the
    same cascade user_delete now performs: soft-delete owned companies (+ detach
    primary_company / UserCompany rows) and soft-delete owned listings.
    """
    User = apps.get_model("accounts", "User")
    Company = apps.get_model("accounts", "Company")
    UserCompany = apps.get_model("accounts", "UserCompany")
    Listing = apps.get_model("listings", "Listing")

    deleted_user_ids = list(
        User.objects.filter(is_deleted=True).values_list("id", flat=True)
    )
    if not deleted_user_ids:
        return

    company_ids = list(
        Company.objects.filter(
            owner_user_id__in=deleted_user_ids, is_deleted=False
        ).values_list("id", flat=True)
    )
    if company_ids:
        Company.objects.filter(id__in=company_ids).update(
            is_deleted=True, is_active=False
        )
        User.objects.filter(primary_company_id__in=company_ids).update(
            primary_company=None
        )
        UserCompany.objects.filter(company_id__in=company_ids).delete()

    Listing.objects.filter(
        owner_user_id__in=deleted_user_ids, is_deleted=False
    ).update(is_deleted=True)


def noop(apps, schema_editor):
    # Soft-deletes are intentionally not reversed (no way to know which rows
    # this pass touched vs. rows already deleted for other reasons).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0049_alter_consultantassignment_status"),
        ("listings", "0005_listing_is_deleted"),
    ]

    operations = [
        migrations.RunPython(cleanup_deleted_user_content, noop),
    ]
