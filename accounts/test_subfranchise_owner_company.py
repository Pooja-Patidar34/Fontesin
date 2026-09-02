"""The Add Sub-Franchise form pins the sub-franchise to ONE of the owner's
companies.

A franchise is held by a company, not by the person: the application carries an
`applicant_company` and the node it becomes carries the same `owner_company`,
which is what scopes the franchise for its holder afterwards. The parent-holder
flow used to set neither, so every node it created landed company-less — and a
prospective owner with several companies had no way to say which one was
buying (bug report, Sep 2026).
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import (
    FranchiseApplicationStatus,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import Company, FranchiseApplication, Role, Tenant, User


class SubFranchiseOwnerCompanyTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-subfr-company")
        self.role = Role.objects.filter(code__iexact="franchise").first()
        if self.role is None:
            self.role = Role.objects.create(
                code="franchise", name="Franchise", tier_level=1,
            )
        # The proposing holder: an ACTIVE Master over India. `application_status`
        # is what lets a real holder past RequireApplicationApprovalMiddleware.
        self.holder = User.objects.create_user(
            email="master@subfr.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role, application_status="approved",
        )
        self.master = Tenant.objects.create(
            name="Master IN", slug="master-in-subfr",
            franchise_level=FranchiseLevel.MASTER,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.holder, territory_country="IN",
        )
        # The prospective sub-franchise owner.
        self.owner = User.objects.create_user(
            email="owner@subfr.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        self.client.force_login(self.holder)

    # -- helpers ----------------------------------------------------------

    def company(self, name):
        return Company.objects.create(
            tenant=self.tenant, name=name, owner_user=self.owner,
        )

    def propose(self, **extra):
        payload = {
            "parent_node_id": str(self.master.id),
            "requested_level": "REGIONAL",
            "requested_region": "Uttar Pradesh",
            "legal_name": "Regional Co",
            "contact_person": "Someone",
            "owner_email": "owner@subfr.test",
        }
        payload.update(extra)
        return self.client.post(
            reverse("franchise-subfranchise-submit"), payload, SERVER_NAME="localhost",
        )

    def created(self):
        return FranchiseApplication.objects.filter(applicant_user=self.owner).first()

    def lookup(self, email="owner@subfr.test"):
        response = self.client.get(
            reverse("franchise-subfranchise-owner-lookup"),
            {"email": email}, SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    # -- the choice itself ------------------------------------------------

    def test_multi_company_owner_requires_an_explicit_company(self):
        """The bug: with two companies there is nothing to guess from, so the
        proposal must be refused rather than silently landing company-less."""
        self.company("Company A")
        self.company("Company B")
        self.propose()
        self.assertIsNone(self.created())
        self.assertFalse(
            Tenant.objects.filter(owner_user=self.owner, franchise_level="REGIONAL").exists()
        )

    def test_multi_company_owner_is_accepted_with_a_company(self):
        company_a = self.company("Company A")
        self.company("Company B")
        self.propose(owner_company=str(company_a.id))
        application = self.created()
        self.assertIsNotNone(application)
        self.assertEqual(application.applicant_company, company_a)
        # ...and the choice reaches the node, which is what scopes it later.
        node = Tenant.objects.filter(owner_user=self.owner, franchise_level="REGIONAL").first()
        self.assertIsNotNone(node)
        self.assertEqual(node.owner_company, company_a)

    def test_single_company_owner_needs_no_choice(self):
        """One company is not a choice — it is resolved server-side, which also
        closes the old gap where such a node was left company-less."""
        only = self.company("Only Co")
        self.propose()
        self.assertEqual(self.created().applicant_company, only)

    def test_company_less_owner_still_works(self):
        """Consultants and coordinators own no company at all; the node stays
        company-less for them, exactly as before."""
        self.propose()
        application = self.created()
        self.assertIsNotNone(application)
        self.assertIsNone(application.applicant_company)

    # -- one franchise per company ----------------------------------------

    def test_company_that_already_holds_a_franchise_is_refused(self):
        taken = self.company("Taken Co")
        Tenant.objects.create(
            name="Held JP", slug="held-jp-subfr",
            franchise_level=FranchiseLevel.NATIONAL,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.owner, owner_company=taken, territory_country="JP",
        )
        free = self.company("Free Co")
        self.propose(owner_company=str(taken.id))
        self.assertIsNone(self.created())
        # The free company is still a valid target.
        self.propose(owner_company=str(free.id))
        self.assertEqual(self.created().applicant_company, free)

    def test_owner_whose_every_company_is_taken_is_still_accepted(self):
        """No company left to stamp is NOT a refusal: this flow accepted such
        proposals before it recorded a company at all, so the node just stays
        company-less rather than the holder losing something that worked."""
        taken = self.company("Taken Co")
        Tenant.objects.create(
            name="Held JP", slug="held-jp-alltaken",
            franchise_level=FranchiseLevel.NATIONAL,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.owner, owner_company=taken, territory_country="JP",
        )
        self.propose()
        application = self.created()
        self.assertIsNotNone(application)
        self.assertIsNone(application.applicant_company)

    def test_company_with_an_open_request_is_refused(self):
        pending = self.company("Pending Co")
        FranchiseApplication.objects.create(
            applicant_user=self.owner, applicant_company=pending,
            requested_level=FranchiseLevel.MASTER, requested_country="DE",
            application_status=FranchiseApplicationStatus.SUBMITTED,
        )
        # A second, free company: with a real choice available, explicitly aiming
        # at the blocked one is a mistake worth refusing rather than a case with
        # nowhere else to go.
        self.company("Free Co")
        self.propose(owner_company=str(pending.id))
        self.assertIsNone(
            FranchiseApplication.objects.filter(
                applicant_user=self.owner, requested_level="REGIONAL",
            ).first()
        )

    def test_a_company_belonging_to_someone_else_is_refused(self):
        """The id is attacker-controlled: only the named owner's own companies
        may be chosen, or a holder could attach the node to any company."""
        stranger = User.objects.create_user(
            email="stranger@subfr.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role,
        )
        theirs = Company.objects.create(
            tenant=self.tenant, name="Not Theirs", owner_user=stranger,
        )
        self.company("Company A")
        self.company("Company B")
        self.propose(owner_company=str(theirs.id))
        self.assertIsNone(self.created())

    # -- the lookup endpoint the picker is built from ----------------------

    def test_lookup_lists_the_owners_companies(self):
        self.company("Company A")
        self.company("Company B")
        data = self.lookup()
        self.assertTrue(data["found"])
        self.assertEqual(
            {c["name"] for c in data["companies"]}, {"Company A", "Company B"},
        )
        self.assertTrue(all(c["eligible"] for c in data["companies"]))

    def test_lookup_marks_a_taken_company_ineligible_with_a_reason(self):
        taken = self.company("Taken Co")
        Tenant.objects.create(
            name="Held JP", slug="held-jp-lookup",
            franchise_level=FranchiseLevel.NATIONAL,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.owner, owner_company=taken, territory_country="JP",
        )
        entry = next(c for c in self.lookup()["companies"] if c["name"] == "Taken Co")
        self.assertFalse(entry["eligible"])
        self.assertIn("Held JP", entry["reason"])

    def test_lookup_reports_an_unknown_email_as_not_found(self):
        data = self.lookup(email="nobody@subfr.test")
        self.assertFalse(data["found"])
        self.assertEqual(data["companies"], [])

    def test_lookup_is_closed_to_non_holders(self):
        outsider = User.objects.create_user(
            email="outsider@subfr.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role, application_status="approved",
        )
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("franchise-subfranchise-owner-lookup"),
            {"email": "owner@subfr.test"}, SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 403)
