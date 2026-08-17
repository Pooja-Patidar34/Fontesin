"""My Requests is scoped to the company the applicant is acting as.

A franchise is bought by a company, not by the person: the request carries an
`applicant_company` and the node it becomes carries the same `owner_company`.
The request list has to follow that boundary, or a Business User switching from
company A to company B still sees A's franchise request (bug report, Aug 2026).
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import FranchiseApplicationStatus, FranchiseLevel
from accounts.models import Company, FranchiseApplication, Role, Tenant, User


class FranchiseRequestCompanyScopeTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-scope")
        role = Role.objects.filter(code__iexact="business_user").first()
        if role is None:
            role = Role.objects.create(code="BUSINESS_USER", name="Business User", tier_level=5)
        self.user = User.objects.create_user(
            email="owner@scope.test", password="x", is_active=True,
            tenant=self.tenant, role=role, application_status="approved",
        )
        self.company_a = Company.objects.create(
            tenant=self.tenant, name="Company A", owner_user=self.user,
        )
        self.company_b = Company.objects.create(
            tenant=self.tenant, name="Company B", owner_user=self.user,
        )
        self.request_a = self.application(self.company_a, "FR")
        self.client.force_login(self.user)

    def application(self, company, country):
        return FranchiseApplication.objects.create(
            applicant_user=self.user,
            applicant_company=company,
            requested_level=FranchiseLevel.MASTER,
            requested_country=country,
            application_status=FranchiseApplicationStatus.APPROVED,
        )

    def acting_as(self, company):
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()
        return self.client.get(reverse("franchise-request"), SERVER_NAME="localhost")

    def listed(self, response):
        return {a.id for a in response.context["applications"]}

    def test_request_is_visible_only_while_acting_as_its_company(self):
        self.assertIn(self.request_a.id, self.listed(self.acting_as(self.company_a)))
        self.assertNotIn(self.request_a.id, self.listed(self.acting_as(self.company_b)))

    def test_each_company_sees_only_its_own_requests(self):
        request_b = self.application(self.company_b, "DE")
        self.assertEqual(self.listed(self.acting_as(self.company_a)), {self.request_a.id})
        self.assertEqual(self.listed(self.acting_as(self.company_b)), {request_b.id})

    def test_company_less_request_stays_visible_everywhere(self):
        """Pre-Jul-2026 rows and consultant/coordinator requests carry no
        company; hiding them in every context would strand their applicant."""
        legacy = self.application(None, "ES")
        self.assertIn(legacy.id, self.listed(self.acting_as(self.company_a)))
        self.assertIn(legacy.id, self.listed(self.acting_as(self.company_b)))

    def test_under_review_banner_follows_the_company(self):
        """`has_open_application` reads the same list, so the "under review"
        notice must not fire for a request another company has in flight."""
        FranchiseApplication.objects.filter(id=self.request_a.id).update(
            application_status=FranchiseApplicationStatus.PENDING_REVIEW,
        )
        self.assertTrue(self.acting_as(self.company_a).context["has_open_application"])
        self.assertFalse(self.acting_as(self.company_b).context["has_open_application"])


class OneFranchisePerCompanyTests(FranchiseRequestCompanyScopeTests):
    """A company holds ONE franchise. Approval spends that company's slot and the
    request form disappears for it; the owner's other companies keep theirs, and a
    rejection gives the slot back."""

    def franchise_for(self, company, country="FR", city="Lyon"):
        from accounts.constants import FranchiseUnitStatus
        return Tenant.objects.create(
            name=f"Micro {city}", slug=f"micro-{city.lower()}",
            franchise_level=FranchiseLevel.MICRO,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.user, owner_company=company,
            territory_country=country, territory_region="Rhone", territory_city=city,
        )

    def form_action(self):
        return reverse("franchise-request-submit")

    def act_as(self, company):
        """Stash the company selection without loading the page. A multi-company
        owner with nothing selected is sent to the picker by
        ActiveCompanyMiddleware before any view runs, so a POST without this
        never reaches the guard under test."""
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()

    def submit_for(self, company, country="DE"):
        self.act_as(company)
        return self.client.post(self.form_action(), {
            "applicant_company": str(company.id),
            "requested_level": FranchiseLevel.MASTER,
            "requested_country": country,
        }, SERVER_NAME="localhost", follow=True)

    def messages_in(self, response):
        return " ".join(str(m) for m in response.context["messages"])

    def test_holding_a_franchise_hides_the_form_for_that_company_only(self):
        self.franchise_for(self.company_a)

        as_a = self.acting_as(self.company_a)
        self.assertFalse(as_a.context["can_request_franchise"])
        self.assertNotContains(as_a, self.form_action())

        as_b = self.acting_as(self.company_b)
        self.assertTrue(as_b.context["can_request_franchise"])
        self.assertContains(as_b, self.form_action())

    def test_open_request_hides_the_form_until_it_is_decided(self):
        FranchiseApplication.objects.filter(id=self.request_a.id).update(
            application_status=FranchiseApplicationStatus.PENDING_REVIEW,
        )
        as_a = self.acting_as(self.company_a)
        self.assertFalse(as_a.context["can_request_franchise"])
        self.assertNotContains(as_a, self.form_action())

    def test_a_rejection_gives_the_slot_back(self):
        FranchiseApplication.objects.filter(id=self.request_a.id).update(
            application_status=FranchiseApplicationStatus.REJECTED,
        )
        as_a = self.acting_as(self.company_a)
        self.assertTrue(as_a.context["can_request_franchise"])
        self.assertContains(as_a, self.form_action())

    def test_removing_the_franchise_frees_the_company_again(self):
        """The slot is held by the franchise, not by the paperwork: once the node
        is gone the company may buy a new territory."""
        node = self.franchise_for(self.company_a)
        self.assertFalse(self.acting_as(self.company_a).context["can_request_franchise"])

        node.is_deleted = True
        node.save(update_fields=["is_deleted"])
        self.assertTrue(self.acting_as(self.company_a).context["can_request_franchise"])

    def test_picker_offers_only_companies_with_a_free_slot(self):
        self.franchise_for(self.company_a)
        offered = {c.id for c in self.acting_as(self.company_b).context["owned_companies"]}
        self.assertEqual(offered, {self.company_b.id})

    def test_submit_refuses_a_second_franchise_for_the_same_company(self):
        """The page hides the form and drops the company from the picker, so this
        can only arrive from a stale page or a hand-made POST — the server is the
        authority either way."""
        self.franchise_for(self.company_a)
        before = FranchiseApplication.objects.count()

        resp = self.submit_for(self.company_a)

        self.assertEqual(FranchiseApplication.objects.count(), before)
        self.assertIn("already holds the franchise", self.messages_in(resp))

    def test_submit_refuses_while_a_request_is_still_open(self):
        FranchiseApplication.objects.filter(id=self.request_a.id).update(
            application_status=FranchiseApplicationStatus.PENDING_REVIEW,
        )
        before = FranchiseApplication.objects.count()

        resp = self.submit_for(self.company_a)

        self.assertEqual(FranchiseApplication.objects.count(), before)
        self.assertIn("under review", self.messages_in(resp))

    def test_a_free_company_can_still_submit(self):
        self.franchise_for(self.company_a)
        before = FranchiseApplication.objects.count()

        self.submit_for(self.company_b)

        self.assertEqual(FranchiseApplication.objects.count(), before + 1)
        self.assertEqual(
            FranchiseApplication.objects.latest("created_at").applicant_company_id,
            self.company_b.id,
        )


class BuyingCompanyBecomesThePartnerTests(TestCase):
    """The whole flow, through the real views: a Business User with companies A,
    B and C logs in as A and buys a franchise. Only A becomes a Franchise
    Partner account — B and C stay plain Business Users with the restricted
    franchise rights.

    Deliberately end-to-end (submit -> admin approve -> activate -> switch
    company) rather than asserting on the scoping helper: the wiring that makes
    this work is `applicant_company` surviving into the node's `owner_company`,
    and only the real approval path exercises it.
    """

    def setUp(self):
        from accounts.constants import FranchiseUnitStatus
        self.status = FranchiseUnitStatus
        self.tenant = Tenant.objects.create(name="Base", slug="base-partner")
        role = Role.objects.filter(code__iexact="business_user").first()
        if role is None:
            role = Role.objects.create(
                code="BUSINESS_USER", name="Business User", tier_level=5,
            )
        self.bu = User.objects.create_user(
            email="bu@partner.test", password="x", is_active=True,
            tenant=self.tenant, role=role, application_status="approved",
        )
        self.admin = User.objects.create_user(
            email="admin@partner.test", password="x", is_active=True,
            tenant=self.tenant, is_staff=True, is_superuser=True,
            application_status="approved",
        )
        self.a, self.b, self.c = [
            Company.objects.create(tenant=self.tenant, name=n, owner_user=self.bu)
            for n in ("Company A", "Company B", "Company C")
        ]

    # -- helpers ----------------------------------------------------------
    def login_as_bu(self, company):
        self.client.force_login(self.bu)
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()

    def page(self):
        return self.client.get(reverse("franchise-request"), SERVER_NAME="localhost")

    def role_label(self):
        """The label the header shows for the session's company context."""
        from accounts.role_i18n import localized_role_label
        user = self.page().context["user"]
        return str(localized_role_label(user))

    def buy_franchise_for(self, company):
        """The real purchase: submit as `company`, Admin approves, Admin activates."""
        self.login_as_bu(company)
        self.client.post(reverse("franchise-request-submit"), {
            "applicant_company": str(company.id),
            "requested_level": FranchiseLevel.MASTER,
            "requested_country": "DE",
        }, SERVER_NAME="localhost")
        application = FranchiseApplication.objects.get(applicant_company=company)

        self.client.force_login(self.admin)
        self.client.post(
            reverse("franchise-application-action", args=[application.id]),
            {"decision": "approve"}, SERVER_NAME="localhost",
        )
        application.refresh_from_db()
        node = application.created_franchise
        self.client.post(
            reverse("franchise-activate", args=[node.id]), {}, SERVER_NAME="localhost",
        )
        node.refresh_from_db()
        return node

    # -- the flow ---------------------------------------------------------
    def test_approval_attributes_the_node_to_the_buying_company(self):
        node = self.buy_franchise_for(self.a)
        self.assertEqual(node.owner_company_id, self.a.id)
        self.assertEqual(node.owner_user_id, self.bu.id)
        self.assertEqual(node.franchise_status, self.status.ACTIVE)

    def test_only_the_buying_company_is_a_franchise_partner(self):
        self.buy_franchise_for(self.a)

        self.login_as_bu(self.a)
        self.assertEqual(self.role_label(), "Franchise Partner")
        self.assertTrue(self.page().context["is_franchise_holder"])

        for other in (self.b, self.c):
            self.login_as_bu(other)
            self.assertEqual(self.role_label(), "Business User", msg=other.name)
            self.assertFalse(self.page().context["is_franchise_holder"], msg=other.name)

    def test_franchise_management_opens_only_under_the_buying_company(self):
        self.buy_franchise_for(self.a)

        self.login_as_bu(self.a)
        self.assertEqual(
            self.client.get(reverse("franchise-tree"), SERVER_NAME="localhost").status_code, 200,
        )
        for other in (self.b, self.c):
            self.login_as_bu(other)
            self.assertEqual(
                self.client.get(reverse("franchise-tree"), SERVER_NAME="localhost").status_code,
                403, msg=other.name,
            )

    def test_the_other_companies_keep_their_restricted_rights(self):
        """"Restricted" means they can still ASK for a franchise of their own —
        they see the request form and none of A's franchise data."""
        self.buy_franchise_for(self.a)

        for other in (self.b, self.c):
            self.login_as_bu(other)
            page = self.page()
            self.assertTrue(page.context["can_request_franchise"], msg=other.name)
            self.assertContains(page, reverse("franchise-request-submit"))
            self.assertEqual(list(page.context["owned_franchises"]), [], msg=other.name)

        self.login_as_bu(self.a)
        page = self.page()
        self.assertFalse(page.context["can_request_franchise"])
        self.assertEqual(len(page.context["owned_franchises"]), 1)

    def test_a_second_company_can_buy_its_own_franchise(self):
        """Each company gets one franchise, so B can buy a different territory
        and become a partner in its own right."""
        node_a = self.buy_franchise_for(self.a)

        self.login_as_bu(self.b)
        self.client.post(reverse("franchise-request-submit"), {
            "applicant_company": str(self.b.id),
            "requested_level": FranchiseLevel.MASTER,
            "requested_country": "ES",
        }, SERVER_NAME="localhost")
        application_b = FranchiseApplication.objects.get(applicant_company=self.b)
        self.assertEqual(application_b.requested_country, "ES")

        self.client.force_login(self.admin)
        self.client.post(
            reverse("franchise-application-action", args=[application_b.id]),
            {"decision": "approve"}, SERVER_NAME="localhost",
        )
        application_b.refresh_from_db()
        self.assertEqual(application_b.created_franchise.owner_company_id, self.b.id)
        # A's franchise is untouched by B's purchase.
        node_a.refresh_from_db()
        self.assertEqual(node_a.owner_company_id, self.a.id)
