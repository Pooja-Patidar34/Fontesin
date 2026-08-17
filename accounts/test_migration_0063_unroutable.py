"""Migration 0063 closes only the franchise requests that cannot be approved.

The migration rejects open sub-franchise requests with no active franchise above
them. Getting the containment rule wrong in either direction is costly: too loose
and it closes requests a real parent could have approved; too tight and the stuck
rows stay stuck. The logic is exercised directly (it is pure, given the models),
so the assertions read as the rule rather than as a schema replay.
"""
from django.test import TestCase

from accounts.constants import FranchiseApplicationStatus, FranchiseLevel, FranchiseUnitStatus
from accounts.models import FranchiseApplication, Role, Tenant, User


def _migration():
    """Import the migration module by its real (numeric-prefixed) name."""
    import importlib

    return importlib.import_module(
        "accounts.migrations.0063_close_unroutable_franchise_requests",
    )


class Apps:
    """Stand-in for the migration's `apps` registry: the real models are
    schema-identical to the historical ones for the fields this migration reads.
    """

    def get_model(self, app_label, model_name):
        return {"Tenant": Tenant, "FranchiseApplication": FranchiseApplication}[model_name]


class CloseUnroutableRequestsTests(TestCase):

    def setUp(self):
        self.migration = _migration()
        self.tenant = Tenant.objects.create(name="Base", slug="base-0063")
        role = Role.objects.filter(code__iexact="business_user").first()
        if role is None:
            role = Role.objects.create(
                code="BUSINESS_USER", name="Business User", tier_level=5,
            )
        self.user = User.objects.create_user(
            email="stuck@0063.test", password="x", is_active=True,
            tenant=self.tenant, role=role, application_status="approved",
        )

    # -- helpers ----------------------------------------------------------
    def node(self, level, country, region="", city="", *,
             status=FranchiseUnitStatus.ACTIVE, deleted=False, name=None):
        name = name or f"{level}-{country}-{region or 'all'}"
        return Tenant.objects.create(
            name=name, slug=name.lower().replace(" ", "-"),
            franchise_level=level, franchise_status=status, is_deleted=deleted,
            owner_user=self.user, territory_country=country,
            territory_region=region, territory_city=city,
        )

    def request_for(self, level, country, region="", city="",
                    status=FranchiseApplicationStatus.SUBMITTED):
        return FranchiseApplication.objects.create(
            applicant_user=self.user, requested_level=level,
            requested_country=country, requested_region=region,
            requested_city=city, application_status=status,
        )

    def run_migration(self):
        self.migration.close_unroutable_requests(Apps(), None)

    def status_of(self, application):
        application.refresh_from_db()
        return application.application_status

    # -- closed -----------------------------------------------------------
    def test_closes_a_sub_request_with_no_franchise_above_it(self):
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN", region="Heilongjiang Sheng")

        self.run_migration()

        self.assertEqual(self.status_of(stuck), FranchiseApplicationStatus.REJECTED)
        stuck.refresh_from_db()
        self.assertIn("no active franchise covers this territory", stuck.board_note.lower())
        self.assertIsNotNone(stuck.rejected_at)

    def test_a_parent_in_another_country_does_not_save_the_request(self):
        self.node(FranchiseLevel.MASTER, "DE")
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN")

        self.run_migration()

        self.assertEqual(self.status_of(stuck), FranchiseApplicationStatus.REJECTED)

    def test_an_inactive_parent_does_not_save_the_request(self):
        self.node(FranchiseLevel.MASTER, "CN", status=FranchiseUnitStatus.PENDING_CONTRACT)
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN")

        self.run_migration()

        self.assertEqual(self.status_of(stuck), FranchiseApplicationStatus.REJECTED)

    def test_a_removed_parent_does_not_save_the_request(self):
        """Soft-deleted nodes are live rows in a migration's plain manager, so the
        exclusion has to be explicit — a removed franchise parents nothing."""
        self.node(FranchiseLevel.MASTER, "CN", deleted=True)
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN")

        self.run_migration()

        self.assertEqual(self.status_of(stuck), FranchiseApplicationStatus.REJECTED)

    def test_a_parent_covering_a_different_state_does_not_save_a_micro(self):
        self.node(FranchiseLevel.NATIONAL, "CN", region="Guangdong Sheng")
        stuck = self.request_for(
            FranchiseLevel.MICRO, "CN", region="Heilongjiang Sheng", city="Harbin",
        )

        self.run_migration()

        self.assertEqual(self.status_of(stuck), FranchiseApplicationStatus.REJECTED)

    # -- left alone -------------------------------------------------------
    def test_leaves_a_request_that_has_a_real_parent(self):
        self.node(FranchiseLevel.MASTER, "CN")
        approvable = self.request_for(FranchiseLevel.NATIONAL, "CN")

        self.run_migration()

        self.assertEqual(self.status_of(approvable), FranchiseApplicationStatus.SUBMITTED)

    def test_a_country_wide_master_covers_a_micro_deep_inside_it(self):
        """Tiers may be skipped (spec §4 note), so a Master parents a Micro."""
        self.node(FranchiseLevel.MASTER, "CN")
        approvable = self.request_for(
            FranchiseLevel.MICRO, "CN", region="Heilongjiang Sheng", city="Harbin",
        )

        self.run_migration()

        self.assertEqual(self.status_of(approvable), FranchiseApplicationStatus.SUBMITTED)

    def test_leaves_master_requests_alone(self):
        """A Master has no parent by design — it is never unroutable."""
        master = self.request_for(FranchiseLevel.MASTER, "CN")

        self.run_migration()

        self.assertEqual(self.status_of(master), FranchiseApplicationStatus.SUBMITTED)

    def test_leaves_already_decided_requests_alone(self):
        decided = self.request_for(
            FranchiseLevel.NATIONAL, "CN",
            status=FranchiseApplicationStatus.APPROVED,
        )

        self.run_migration()

        self.assertEqual(self.status_of(decided), FranchiseApplicationStatus.APPROVED)

    def test_keeps_an_existing_board_note(self):
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN")
        FranchiseApplication.objects.filter(id=stuck.id).update(board_note="Earlier note")

        self.run_migration()

        stuck.refresh_from_db()
        self.assertIn("Earlier note", stuck.board_note)
        self.assertIn("Master Franchise", stuck.board_note)

    def test_is_safe_to_run_twice(self):
        stuck = self.request_for(FranchiseLevel.NATIONAL, "CN")

        self.run_migration()
        self.run_migration()

        stuck.refresh_from_db()
        self.assertEqual(stuck.application_status, FranchiseApplicationStatus.REJECTED)
        # The note is appended once: the second pass no longer sees an open row.
        self.assertEqual(stuck.board_note.lower().count("no active franchise"), 1)
