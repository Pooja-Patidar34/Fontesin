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
