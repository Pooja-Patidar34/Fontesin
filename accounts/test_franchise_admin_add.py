"""The Platform Admin can create a franchise outright, with no approval step.

Every other route to a franchise node is a request someone else has to approve —
and the last approver in the chain is the Admin, who had no way to simply create
one (gap noted in the sidebar template, filled Sep 2026). "No approval" means no
review round-trip, NOT fewer integrity rules: territory canon, one-per-territory
and the tree-containment rules all still run.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import (
    ContractStatus,
    FranchiseApplicationStatus,
    FranchiseFeeStatus,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import (
    Company,
    ConsultantAssignment,
    FranchiseApplication,
    Role,
    Tenant,
    User,
)


class FranchiseAdminAddTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-admin-add")
        self.role = Role.objects.filter(code__iexact="franchise").first()
        if self.role is None:
            self.role = Role.objects.create(
                code="franchise", name="Franchise", tier_level=1,
            )
        self.admin = User.objects.create_user(
            email="admin@add.test", password="x", is_active=True,
            tenant=self.tenant, is_staff=True, is_superuser=True,
            application_status="approved",
        )
        self.owner = User.objects.create_user(
            email="owner@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.client.force_login(self.admin)

    # -- helpers ----------------------------------------------------------

    def create(self, **extra):
        payload = {
            "requested_level": "MASTER",
            "requested_country": "AO",
            "legal_name": "Acme Angola",
            "contact_person": "Someone",
            "owner_email": "owner@add.test",
        }
        payload.update(extra)
        return self.client.post(
            reverse("franchise-admin-add-submit"), payload, SERVER_NAME="localhost",
        )

    def node_for(self, owner):
        return Tenant.objects.filter(
            owner_user=owner, franchise_level__isnull=False,
        ).first()

    # -- the point of the feature ----------------------------------------

    def test_admin_creates_a_master_that_is_immediately_active(self):
        self.create()
        node = self.node_for(self.owner)
        self.assertIsNotNone(node)
        self.assertEqual(node.franchise_level, FranchiseLevel.MASTER)
        # Live in one step — no PENDING_CONTRACT stop, no second approval.
        self.assertEqual(node.franchise_status, FranchiseUnitStatus.ACTIVE)
        self.assertEqual(node.contract_status, ContractStatus.SIGNED)
        self.assertEqual(node.franchise_fee_status, FranchiseFeeStatus.PAID)
        self.assertIsNotNone(node.activated_at)

    def test_it_leaves_an_approved_application_behind_for_the_audit_trail(self):
        self.create()
        application = FranchiseApplication.objects.filter(
            applicant_user=self.owner,
        ).first()
        self.assertIsNotNone(application)
        self.assertEqual(application.application_status, FranchiseApplicationStatus.APPROVED)
        self.assertEqual(application.created_franchise, self.node_for(self.owner))
        self.assertEqual(application.approved_by, self.admin)

    def test_the_owner_is_let_past_the_staff_application_gate(self):
        """Activation's own side effect: a holder who registered under a staff
        role would otherwise be bounced by RequireApplicationApprovalMiddleware."""
        self.create()
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.application_status, "approved")

    def test_a_micro_owner_is_recorded_on_its_own_roster(self):
        """The other activation side effect (spec §9.1.2) — proving the shared
        activation path really did run, not a partial copy of it."""
        self.create(requested_level="MASTER", requested_country="AO")
        self.create(
            requested_level="MICRO", requested_country="AO",
            requested_region="Benguela", requested_city="Lobito",
            owner_email="micro@add.test", legal_name="Micro Co",
        )
        micro_user = User.objects.create_user(
            email="micro@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.create(
            requested_level="MICRO", requested_country="AO",
            requested_region="Benguela", requested_city="Lobito",
            owner_email="micro@add.test", legal_name="Micro Co",
        )
        micro = Tenant.objects.filter(owner_user=micro_user).first()
        self.assertIsNotNone(micro)
        self.assertTrue(
            ConsultantAssignment.objects.filter(
                consultant_user=micro_user, franchise_node=micro,
            ).exists()
        )

    # -- integrity rules still apply --------------------------------------

    def test_a_sub_level_needs_an_active_franchise_above_it(self):
        """No Master over Angola yet, so a Regional has nothing to sit under."""
        self.create(
            requested_level="REGIONAL", requested_region="Benguela",
            legal_name="Orphan Co",
        )
        self.assertIsNone(self.node_for(self.owner))

    def test_the_resolved_parent_is_the_deepest_active_cover(self):
        self.create()  # Master AO for self.owner
        national_user = User.objects.create_user(
            email="national@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.create(
            requested_level="NATIONAL", requested_country="AO",
            owner_email="national@add.test", legal_name="National Co",
        )
        regional_user = User.objects.create_user(
            email="regional@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.create(
            requested_level="REGIONAL", requested_country="AO",
            requested_region="Benguela",
            owner_email="regional@add.test", legal_name="Regional Co",
        )
        regional = Tenant.objects.filter(owner_user=regional_user).first()
        self.assertIsNotNone(regional)
        self.assertEqual(regional.parent, self.node_for(national_user))

    def test_a_taken_territory_is_still_refused(self):
        self.create()
        second = User.objects.create_user(
            email="second@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.create(owner_email="second@add.test", legal_name="Rival Co")
        self.assertIsNone(self.node_for(second))

    def test_an_unknown_owner_email_is_refused(self):
        self.create(owner_email="nobody@add.test")
        self.assertFalse(Tenant.objects.filter(name="Acme Angola").exists())

    def test_a_multi_company_owner_must_be_pinned_to_one_company(self):
        Company.objects.create(tenant=self.tenant, name="A", owner_user=self.owner)
        Company.objects.create(tenant=self.tenant, name="B", owner_user=self.owner)
        self.create()
        self.assertIsNone(self.node_for(self.owner))

    def test_the_chosen_company_is_stamped_on_the_node(self):
        company_a = Company.objects.create(
            tenant=self.tenant, name="A", owner_user=self.owner,
        )
        Company.objects.create(tenant=self.tenant, name="B", owner_user=self.owner)
        self.create(owner_company=str(company_a.id))
        self.assertEqual(self.node_for(self.owner).owner_company, company_a)

    # -- who may use it ---------------------------------------------------

    def test_the_page_is_superuser_only(self):
        # Approved, so RequireApplicationApprovalMiddleware lets them through and
        # what we observe really is this view's own gate rather than that one's
        # redirect to /apply/.
        outsider = User.objects.create_user(
            email="outsider@add.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role, application_status="approved",
        )
        self.client.force_login(outsider)
        for name in ("franchise-admin-add", "franchise-admin-add-submit"):
            method = self.client.get if name == "franchise-admin-add" else self.client.post
            self.assertEqual(
                method(reverse(name), SERVER_NAME="localhost").status_code, 403,
                msg=name,
            )

    def test_the_admin_can_open_the_form(self):
        response = self.client.get(
            reverse("franchise-admin-add"), SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("franchise-admin-add-submit"), response.content.decode())
