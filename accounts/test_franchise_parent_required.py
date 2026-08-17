"""A sub-franchise request needs an active franchise above it.

The tree has nothing to attach a National / Regional / Micro request to until a
higher tier covers that territory, so the Platform Admin cannot approve one:
they get "No active franchise covers this territory yet" and the applicant waits
on a request that can never be granted (bug report, Aug 2026). These requests are
therefore refused at submit time — only a Master, which has no parent, may be
requested into empty space.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import FranchiseLevel, FranchiseUnitStatus
from accounts.models import Company, FranchiseApplication, Role, Tenant, User


class SubFranchiseNeedsAnActiveParentTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-parent-req")
        role = Role.objects.filter(code__iexact="business_user").first()
        if role is None:
            role = Role.objects.create(
                code="BUSINESS_USER", name="Business User", tier_level=5,
            )
        self.applicant = User.objects.create_user(
            email="applicant@parent.test", password="x", is_active=True,
            tenant=self.tenant, role=role, application_status="approved",
        )
        # A single company, so there is no picker to satisfy and the company's
        # franchise slot is free.
        self.company = Company.objects.create(
            tenant=self.tenant, name="Solo Ltd", owner_user=self.applicant,
        )
        # Somebody else holds the parents — a territory under your OWN node is
        # added as a sub-franchise proposal, not bought through this form.
        self.other = User.objects.create_user(
            email="holder@parent.test", password="x", is_active=True,
            tenant=self.tenant, role=role, application_status="approved",
        )
        self.client.force_login(self.applicant)

    # -- helpers ----------------------------------------------------------
    def active_node(self, level, country, region="", city="", name="Node"):
        return Tenant.objects.create(
            name=name, slug=name.lower().replace(" ", "-"),
            franchise_level=level, franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.other, territory_country=country,
            territory_region=region, territory_city=city,
        )

    def submit(self, level, country, region="", city=""):
        return self.client.post(reverse("franchise-request-submit"), {
            "applicant_company": str(self.company.id),
            "requested_level": level,
            "requested_country": country,
            "requested_region": region,
            "requested_city": city,
        }, SERVER_NAME="localhost", follow=True)

    def messages_in(self, response):
        return " ".join(str(m) for m in response.context["messages"])

    # -- refusals ---------------------------------------------------------
    def test_national_is_refused_when_no_master_covers_the_country(self):
        resp = self.submit(FranchiseLevel.NATIONAL, "CN")

        self.assertEqual(FranchiseApplication.objects.count(), 0)
        self.assertIn("nothing to sit under", self.messages_in(resp))

    def test_master_for_another_country_does_not_count_as_cover(self):
        self.active_node(FranchiseLevel.MASTER, "DE", name="Master DE")

        self.submit(FranchiseLevel.NATIONAL, "CN")

        self.assertEqual(FranchiseApplication.objects.count(), 0)

    def test_an_inactive_master_does_not_count_as_cover(self):
        """Only an ACTIVE node can parent a child — the same rule the approval
        path applies, so a pending-contract Master must not let requests in."""
        node = self.active_node(FranchiseLevel.MASTER, "CN", name="Master CN")
        node.franchise_status = FranchiseUnitStatus.PENDING_CONTRACT
        node.save(update_fields=["franchise_status"])

        self.submit(FranchiseLevel.NATIONAL, "CN")

        self.assertEqual(FranchiseApplication.objects.count(), 0)

    def test_a_master_in_a_different_region_does_not_cover_a_micro(self):
        """A National that names its state covers only that state."""
        self.active_node(
            FranchiseLevel.NATIONAL, "CN", region="Guangdong Sheng",
            name="National Guangdong",
        )

        self.submit(
            FranchiseLevel.MICRO, "CN", region="Heilongjiang Sheng", city="Harbin",
        )

        self.assertEqual(FranchiseApplication.objects.count(), 0)

    # -- accepted ---------------------------------------------------------
    def test_master_needs_no_parent(self):
        self.submit(FranchiseLevel.MASTER, "CN")

        application = FranchiseApplication.objects.get()
        self.assertEqual(application.requested_level, FranchiseLevel.MASTER)
        self.assertIsNone(application.parent_franchise)

    def test_national_is_accepted_under_an_active_master(self):
        master = self.active_node(FranchiseLevel.MASTER, "CN", name="Master CN")

        self.submit(FranchiseLevel.NATIONAL, "CN")

        application = FranchiseApplication.objects.get()
        self.assertEqual(application.parent_franchise_id, master.id)

    def test_micro_is_accepted_under_a_master_that_covers_the_whole_country(self):
        """A Master names no state, so it covers every territory in the country —
        the tree allows skipping tiers (spec §4 note)."""
        master = self.active_node(FranchiseLevel.MASTER, "CN", name="Master CN")

        self.submit(
            FranchiseLevel.MICRO, "CN", region="Heilongjiang Sheng", city="Harbin",
        )

        application = FranchiseApplication.objects.get()
        self.assertEqual(application.parent_franchise_id, master.id)

    # -- the early, client-side version of the same "no" -------------------
    def test_the_form_ships_the_coverage_data_for_its_own_warning(self):
        master = self.active_node(FranchiseLevel.MASTER, "CN", name="Master CN")
        self.active_node(FranchiseLevel.MASTER, "DE", name="Master DE")

        page = self.client.get(reverse("franchise-request"), SERVER_NAME="localhost")

        coverage = page.context["parent_coverage"]
        self.assertEqual(
            {c["country"] for c in coverage}, {"CN", "DE"},
        )
        self.assertEqual(
            [c["rank"] for c in coverage if c["country"] == "CN"],
            [FranchiseLevel.RANK[master.franchise_level]],
        )
