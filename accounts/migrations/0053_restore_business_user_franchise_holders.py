"""Undo the role hijack performed by the old franchise activation flow.

Activation used to overwrite the holder's role with `franchise`. For a Business
User that was destructive: every business-user gate (the company switcher,
plans, partnerships, join requests) keys on the role, so a BU with three
companies could act as only one of them afterwards and could never switch back.

Franchise capabilities are now derived from the franchise nodes a user owns
(accounts.utils.franchise_access) and the role is left alone, so the accounts
that were flipped can simply be flipped back. Only accounts that own at least
one Company are touched — those are exactly the Business Users the old flow
converted. A franchise holder who owns no company (a consultant/coordinator who
registered through the staff flow) keeps whatever role they have.

Also backfills `Tenant.owner_company` for those holders when the attribution is
unambiguous (they own exactly one company), so My Franchises can show which
company holds the franchise.
"""

from django.db import migrations


def restore_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Role = apps.get_model("accounts", "Role")
    Company = apps.get_model("accounts", "Company")
    Tenant = apps.get_model("accounts", "Tenant")

    business_role = Role.objects.filter(code__iexact="business_user").first()
    if business_role is None:
        return

    holders = User.objects.filter(role__code__iexact="franchise")
    for user in holders:
        companies = list(Company.objects.filter(owner_user=user, is_deleted=False))
        if not companies:
            continue  # not a converted Business User — leave the role alone
        user.role = business_role
        user.save(update_fields=["role"])

        if len(companies) == 1:
            Tenant.objects.filter(
                owner_user=user,
                franchise_level__isnull=False,
                owner_company__isnull=True,
            ).update(owner_company=companies[0])


def noop(apps, schema_editor):
    """No reverse: re-applying the role hijack is the bug this undoes."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0052_franchiseapplication_applicant_company"),
    ]

    operations = [
        migrations.RunPython(restore_roles, noop),
    ]
