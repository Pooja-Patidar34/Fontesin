"""Consultant Assignment is offered whenever the company being acted as holds an
ACTIVE franchise, and says WHY when it isn't.

Bug report (Sep 2026): a holder whose selected company had an active franchise
was told "You need an active franchise before you can assign consultants." That
message was the catch-all for four different situations, three of which are not
"you have no franchise" — so the page could not be trusted to say what was
wrong. These tests pin the gate itself (does the assign form appear?) separately
from the explanation shown when it doesn't.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import FranchiseLevel, FranchiseUnitStatus
from accounts.models import Company, Role, Tenant, User


class ConsultantAssignmentGateTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-consult-gate")
        self.role = Role.objects.filter(code__iexact="franchise").first()
        if self.role is None:
            self.role = Role.objects.create(
                code="franchise", name="Franchise", tier_level=1,
            )
        self.holder = User.objects.create_user(
            email="holder@consult.test", password="x", is_active=True,
            tenant=self.tenant, role=self.role, application_status="approved",
        )
        self.company_a = Company.objects.create(
            tenant=self.tenant, name="Company A", owner_user=self.holder,
        )
        self.company_b = Company.objects.create(
            tenant=self.tenant, name="Company B", owner_user=self.holder,
        )
        self.client.force_login(self.holder)

    # -- helpers ----------------------------------------------------------

    def node(self, company, level=FranchiseLevel.REGIONAL,
             status=FranchiseUnitStatus.ACTIVE, slug="node-consult",
             country="IN", region="Uttar Pradesh"):
        # One holder may own several franchises only where the territories don't
        # overlap (Tenant.validate_owner_territories_do_not_overlap), so tests
        # that give the holder a second node must place it in another country.
        return Tenant.objects.create(
            name="Node " + slug, slug=slug,
            franchise_level=level, franchise_status=status,
            owner_user=self.holder, owner_company=company,
            territory_country=country, territory_region=region,
        )

    def visit_as(self, company):
        session = self.client.session
        session["active_company_id"] = str(company.id)
        session.save()
        return self.client.get(reverse("franchise-consultants"), SERVER_NAME="localhost")

    def body(self, response):
        return response.content.decode()

    # -- the gate ---------------------------------------------------------

    def test_active_franchise_on_the_selected_company_offers_the_assign_form(self):
        """The reported case: acting as the company that holds the ACTIVE
        franchise must produce a usable assign form."""
        node = self.node(self.company_a)
        response = self.visit_as(self.company_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([n.id for n in response.context["active_nodes"]], [node.id])
        self.assertIn(reverse("assign-consultant"), self.body(response))

    def test_company_less_node_is_offered_under_every_company(self):
        """Nodes created before the company was recorded carry no owner_company;
        hiding them in every context would strand their holder."""
        node = self.node(None, slug="node-legacy")
        for company in (self.company_a, self.company_b):
            response = self.visit_as(company)
            self.assertEqual([n.id for n in response.context["active_nodes"]], [node.id])

    # -- the explanation when the form is absent --------------------------

    def test_micro_franchise_says_so_instead_of_no_franchise(self):
        self.node(self.company_a, level=FranchiseLevel.MICRO, slug="node-micro")
        response = self.visit_as(self.company_a)
        self.assertEqual(response.context["active_nodes"], [])
        self.assertTrue(response.context["micro_only"])
        # The reported symptom: an ACTIVE Micro was told it had no franchise.
        self.assertIn("smallest unit", self.body(response))
        self.assertNotIn("You need an active franchise", self.body(response))

    def test_a_node_awaiting_activation_does_not_reach_this_page_at_all(self):
        """PENDING_CONTRACT is not yet a franchise holder (`is_franchise_holder`
        counts ACTIVE and SUSPENDED only), so the franchise-manager gate refuses
        the page outright — which is why the empty state has no "not activated
        yet" case to explain."""
        self.node(
            self.company_a, status=FranchiseUnitStatus.PENDING_CONTRACT,
            slug="node-pending",
        )
        self.assertEqual(self.visit_as(self.company_a).status_code, 403)

    def test_suspended_says_so_instead_of_no_franchise(self):
        self.node(
            self.company_a, status=FranchiseUnitStatus.SUSPENDED, slug="node-susp",
        )
        response = self.visit_as(self.company_a)
        self.assertTrue(response.context["has_suspended"])
        self.assertIn("suspended", self.body(response))

    def test_other_companys_franchise_names_the_company_to_switch_from(self):
        """The franchise belongs to company A; acting as B the roster is empty,
        and the page has to say so in terms of B rather than claim the holder
        has no franchise at all."""
        self.node(self.company_a, slug="node-a")
        # B has its own (Micro) franchise purely so the holder still passes the
        # franchise-manager gate while acting as B — in another country, since
        # one holder's territories may not overlap.
        self.node(
            self.company_b, level=FranchiseLevel.MICRO, slug="node-b-micro",
            country="JP", region="Tokyo",
        )
        response = self.visit_as(self.company_b)
        self.assertEqual(response.context["scoped_company"], self.company_b)
        self.assertEqual(response.context["active_nodes"], [])
