import uuid
from decimal import Decimal
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.db import DatabaseError
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import (
    Tenant, Company, User, Role, Permission,
    UserRole, UserCompany, UserCompanyRole,
    NaceCode, NaicsCode,
)
from billing.models import CommercialPlan, Subscription


class BaseAPITestCase(TestCase):
    """Shared setup for accounts_api tests."""

    def setUp(self):
        self.client = APIClient()

        self.tenant = Tenant.objects.create(name="API Tenant", slug="api-tenant")

        self.role = Role.objects.create(name="api_admin", tier_level=1)

        self.perm_view, _ = Permission.objects.get_or_create(
            code="company.view",
            defaults={"description": "View companies"},
        )
        self.perm_manage, _ = Permission.objects.get_or_create(
            code="company.manage",
            defaults={"description": "Manage companies"},
        )
        self.role.permissions.add(self.perm_view, self.perm_manage)

        self.user = User.objects.create_user(
            email="apiuser@test.com", password="test123",
            tenant=self.tenant, role=self.role, is_active=True,
        )
        UserRole.objects.create(user=self.user, role=self.role)

        self.company = Company.objects.create(
            tenant=self.tenant, name="API Company",
        )

        self.superadmin = User.objects.create_superuser(
            email="apiadmin@test.com", password="admin123",
            tenant=self.tenant,
        )

        # Give user a plan with company_registry access.
        # NOTE: migrations seed a "basic" plan whose `comparison` does NOT
        # include `company_registry`, so get_or_create returns that seeded
        # row and ignores `defaults`. We therefore force the feature flag on
        # explicitly after fetching, otherwise the plan-gate in
        # CompanyListAPIView.get rejects every non-superuser with 403.
        self.plan, _ = CommercialPlan.objects.get_or_create(
            code="basic",
            defaults={
                "name": "Basic", "price": Decimal("99.00"),
                "billing_period": "yearly",
                "comparison": {"company_registry": True},
            },
        )
        self.plan.comparison = {**(self.plan.comparison or {}), "company_registry": True}
        self.plan.save(update_fields=["comparison"])
        now = timezone.now()
        Subscription.objects.create(
            user=self.user, plan=self.plan, status="active",
            start_date=now, end_date=now + timedelta(days=30),
        )


# ═══════════════════════════════════════════════════════════════════════
# CompanyListAPIView GET tests
# ═══════════════════════════════════════════════════════════════════════

class CompanyListGETTests(BaseAPITestCase):

    def test_unauthenticated_denied(self):
        response = self.client.get("/api/companies/")
        self.assertIn(response.status_code, [401, 403])

    def test_superadmin_lists_all_companies(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])
        self.assertGreaterEqual(len(response.data["data"]), 1)

    def test_superadmin_filters_by_tenant(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(
            "/api/companies/", {"tenant_id": str(self.tenant.id)}
        )
        self.assertEqual(response.status_code, 200)
        for c in response.data["data"]:
            self.assertIn("name", c)

    def test_superadmin_invalid_tenant_id(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(
            "/api/companies/", {"tenant_id": "not-a-uuid"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["status"])

    def test_user_with_plan_and_permission_lists_companies(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])

    def test_user_without_plan_denied(self):
        # Create user without subscription
        no_plan_user = User.objects.create_user(
            email="noplan@test.com", password="test123",
            tenant=self.tenant, role=self.role, is_active=True,
        )
        UserRole.objects.create(user=no_plan_user, role=self.role)
        self.client.force_authenticate(user=no_plan_user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("plan", response.data["message"].lower())

    def test_user_with_plan_sees_tenant_scoped_data(self):
        # Verify the user only sees companies from their own tenant
        other_tenant = Tenant.objects.create(name="Other T", slug="other-t")
        Company.objects.create(tenant=other_tenant, name="Hidden Co")
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)
        names = [c["name"] for c in response.data["data"]]
        self.assertIn("API Company", names)
        self.assertNotIn("Hidden Co", names)

    def test_user_without_role_denied(self):
        no_role_user = User.objects.create_user(
            email="norole@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        # Give plan
        plan, _ = CommercialPlan.objects.get_or_create(
            code="basic", defaults={"name": "Basic", "price": Decimal("99"), "billing_period": "yearly", "comparison": {"company_registry": True}},
        )
        Subscription.objects.create(
            user=no_role_user, plan=plan, status="active",
            start_date=timezone.now(), end_date=timezone.now() + timedelta(days=30),
        )
        self.client.force_authenticate(user=no_role_user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 403)
        self.assertIn("role", response.data["message"].lower())

    def test_user_without_view_permission_denied(self):
        # Role with no permissions
        bare_role = Role.objects.create(name="bare_role", tier_level=1)
        no_perm_user = User.objects.create_user(
            email="noperm@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=no_perm_user, role=bare_role)
        plan, _ = CommercialPlan.objects.get_or_create(
            code="basic", defaults={"name": "Basic", "price": Decimal("99"), "billing_period": "yearly", "comparison": {"company_registry": True}},
        )
        Subscription.objects.create(
            user=no_perm_user, plan=plan, status="active",
            start_date=timezone.now(), end_date=timezone.now() + timedelta(days=30),
        )
        self.client.force_authenticate(user=no_perm_user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 403)

    def test_tenant_admin_lists_own_companies(self):
        admin_role = Role.objects.create(name="tenant_admin", tier_level=2)
        ta_user = User.objects.create_user(
            email="ta@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=ta_user, role=admin_role)
        plan, _ = CommercialPlan.objects.get_or_create(
            code="basic", defaults={"name": "Basic", "price": Decimal("99"), "billing_period": "yearly", "comparison": {"company_registry": True}},
        )
        Subscription.objects.create(
            user=ta_user, plan=plan, status="active",
            start_date=timezone.now(), end_date=timezone.now() + timedelta(days=30),
        )
        self.client.force_authenticate(user=ta_user)
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════
# CompanyListAPIView POST tests
# ═══════════════════════════════════════════════════════════════════════

class CompanyListPOSTTests(BaseAPITestCase):

    def test_unauthenticated_denied(self):
        response = self.client.post("/api/companies/", {"name": "New"})
        self.assertIn(response.status_code, [401, 403])

    def test_user_without_manage_permission_denied(self):
        bare_role = Role.objects.create(name="viewer", tier_level=1)
        viewer = User.objects.create_user(
            email="viewer@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=viewer, role=bare_role)
        self.client.force_authenticate(user=viewer)
        response = self.client.post("/api/companies/", {"name": "Hack"})
        self.assertEqual(response.status_code, 403)

    def test_superadmin_creates_company(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post("/api/companies/", {
            "name": "New API Company",
            "tenant": str(self.tenant.id),
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["status"])
        self.assertEqual(response.data["data"]["name"], "New API Company")

    def test_tenant_user_creates_company_auto_tenant(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/companies/", {
            "name": "User Created Co",
        })
        self.assertEqual(response.status_code, 201)
        new_co = Company.objects.get(name="User Created Co")
        self.assertEqual(new_co.tenant, self.tenant)

    def test_invalid_data_returns_400(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.post("/api/companies/", {})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["status"])
        self.assertIn("errors", response.data)


# ═══════════════════════════════════════════════════════════════════════
# CompanyUpdateAPIView PUT tests
# ═══════════════════════════════════════════════════════════════════════

class CompanyUpdatePUTTests(BaseAPITestCase):

    def test_unauthenticated_denied(self):
        response = self.client.put(
            f"/api/companies/{self.company.id}/", {"name": "Updated"}
        )
        self.assertIn(response.status_code, [401, 403])

    def test_user_without_manage_permission_denied(self):
        bare_role = Role.objects.create(name="viewer2", tier_level=1)
        viewer = User.objects.create_user(
            email="viewer2@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=viewer, role=bare_role)
        self.client.force_authenticate(user=viewer)
        response = self.client.put(
            f"/api/companies/{self.company.id}/", {"name": "Hack"}
        )
        self.assertEqual(response.status_code, 403)

    def test_superadmin_updates_company(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.put(
            f"/api/companies/{self.company.id}/",
            {"name": "Updated Company"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Updated Company")

    def test_tenant_user_updates_own_company(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            f"/api/companies/{self.company.id}/",
            {"name": "My Updated Co"},
        )
        self.assertEqual(response.status_code, 200)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "My Updated Co")

    def test_tenant_user_cannot_update_other_tenant_company(self):
        other_tenant = Tenant.objects.create(name="Other", slug="other")
        other_co = Company.objects.create(tenant=other_tenant, name="Other Co")
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            f"/api/companies/{other_co.id}/", {"name": "Hack"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("outside your tenant", response.data["message"])

    def test_company_not_found(self):
        self.client.force_authenticate(user=self.superadmin)
        fake_id = uuid.uuid4()
        response = self.client.put(
            f"/api/companies/{fake_id}/", {"name": "Ghost"}
        )
        self.assertEqual(response.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════
# CompanyDetailAPIView GET tests
# ═══════════════════════════════════════════════════════════════════════

class CompanyDetailGETTests(BaseAPITestCase):

    def test_unauthenticated_denied(self):
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertIn(response.status_code, [401, 403])

    def test_superadmin_gets_detail(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])
        self.assertEqual(response.data["data"]["name"], "API Company")

    def test_tenant_user_with_permission_gets_detail(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertEqual(response.status_code, 200)

    def test_tenant_user_cannot_see_other_tenant_company(self):
        other_tenant = Tenant.objects.create(name="Other2", slug="other2")
        other_co = Company.objects.create(tenant=other_tenant, name="Secret Co")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/companies/{other_co.id}/detail/"
        )
        self.assertEqual(response.status_code, 403)

    def test_user_without_role_denied(self):
        norole = User.objects.create_user(
            email="norole2@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        self.client.force_authenticate(user=norole)
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertEqual(response.status_code, 403)

    def test_user_without_view_permission_denied(self):
        bare_role = Role.objects.create(name="empty_role", tier_level=1)
        noperm = User.objects.create_user(
            email="noperm2@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=noperm, role=bare_role)
        self.client.force_authenticate(user=noperm)
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertEqual(response.status_code, 403)

    def test_company_not_found(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(
            f"/api/companies/{uuid.uuid4()}/detail/"
        )
        self.assertEqual(response.status_code, 404)

    def test_tenant_admin_gets_detail(self):
        admin_role = Role.objects.create(name="tenant_admin2", tier_level=2)
        # Name must be tenant_admin to pass the check
        admin_role.name = "tenant_admin"
        admin_role.save()
        ta = User.objects.create_user(
            email="ta2@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=ta, role=admin_role)
        self.client.force_authenticate(user=ta)
        response = self.client.get(
            f"/api/companies/{self.company.id}/detail/"
        )
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════
# accounts_api/utils.py tests
# ═══════════════════════════════════════════════════════════════════════

class APIUtilTests(BaseAPITestCase):

    def test_get_user_role_returns_role(self):
        from accounts_api.utils import get_user_role
        role = get_user_role(self.user)
        self.assertIsNotNone(role)
        self.assertEqual(role.name, "api_admin")

    def test_get_user_role_none_when_no_role(self):
        from accounts_api.utils import get_user_role
        norole = User.objects.create_user(
            email="norole3@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        role = get_user_role(norole)
        self.assertIsNone(role)

    def test_can_manage_company_superuser(self):
        from accounts_api.utils import can_manage_company
        self.assertTrue(can_manage_company(self.superadmin))

    def test_can_manage_company_with_permission(self):
        from accounts_api.utils import can_manage_company
        self.assertTrue(can_manage_company(self.user))

    def test_can_manage_company_without_permission(self):
        from accounts_api.utils import can_manage_company
        norole = User.objects.create_user(
            email="norole4@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        self.assertFalse(can_manage_company(norole))

    def test_can_manage_company_role_without_manage_perm(self):
        # Role exists but lacks company.manage -> False (covers the final
        # permissions.filter(...).exists() branch returning False).
        from accounts_api.utils import can_manage_company
        bare_role = Role.objects.create(name="util_bare", tier_level=1)
        user = User.objects.create_user(
            email="utilbare@test.com", password="test123",
            tenant=self.tenant, is_active=True,
        )
        UserRole.objects.create(user=user, role=bare_role)
        self.assertFalse(can_manage_company(user))


# ═══════════════════════════════════════════════════════════════════════
# UserProfileAPIView tests
# ═══════════════════════════════════════════════════════════════════════

class UserProfileAPITests(BaseAPITestCase):

    URL = "/api/profile/"

    def test_unauthenticated_denied(self):
        response = self.client.get(self.URL)
        self.assertIn(response.status_code, [401, 403])

    def test_authenticated_returns_profile(self):
        UserCompany.objects.create(user=self.user, company=self.company)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])
        data = response.data["data"]
        self.assertEqual(data["email"], "apiuser@test.com")
        self.assertEqual(str(data["tenant_id"]), str(self.tenant.id))
        self.assertEqual(data["role"], "api_admin")

    def test_profile_companies_field_currently_omitted(self):
        # Characterization test for a known bug: UserProfileSerializer points
        # `companies` at source="companies_through_user", which is NOT a
        # relation/attribute on User. Because the field is read-only
        # (required=False), DRF raises SkipField and silently drops it, so
        # the linked companies never appear in the response. The endpoint
        # still returns 200. If/when the serializer source is fixed, update
        # this test to assert the company list is present.
        UserCompany.objects.create(user=self.user, company=self.company)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("companies", response.data["data"])

    def test_profile_user_not_found_returns_404(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch("accounts_api.view.profile.User.objects") as m:
            chain = m.select_related.return_value.prefetch_related.return_value
            chain.get.side_effect = User.DoesNotExist
            response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["status"])

    def test_profile_database_error_returns_500(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch("accounts_api.view.profile.User.objects") as m:
            chain = m.select_related.return_value.prefetch_related.return_value
            chain.get.side_effect = DatabaseError("boom")
            response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database error", response.data["message"])

    def test_profile_unexpected_error_returns_500(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch("accounts_api.view.profile.User.objects") as m:
            chain = m.select_related.return_value.prefetch_related.return_value
            chain.get.side_effect = RuntimeError("unexpected")
            response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.data["status"])


# ═══════════════════════════════════════════════════════════════════════
# Industry code helper-function unit tests
# ═══════════════════════════════════════════════════════════════════════

class IndustryCodeHelperTests(TestCase):

    def test_parse_int_valid(self):
        from accounts_api.view.industry_codes import _parse_int
        self.assertEqual(_parse_int("5", default=20), 5)

    def test_parse_int_none_returns_default(self):
        from accounts_api.view.industry_codes import _parse_int
        self.assertEqual(_parse_int(None, default=20), 20)

    def test_parse_int_non_numeric_returns_default(self):
        from accounts_api.view.industry_codes import _parse_int
        self.assertEqual(_parse_int("abc", default=7), 7)

    def test_parse_int_clamps_to_lower_bound(self):
        from accounts_api.view.industry_codes import _parse_int
        self.assertEqual(_parse_int("0", default=20, lower=1, upper=100), 1)

    def test_parse_int_clamps_to_upper_bound(self):
        from accounts_api.view.industry_codes import _parse_int
        self.assertEqual(_parse_int("9999", default=20, lower=1, upper=100), 100)

    def test_serialize_without_parent(self):
        from accounts_api.view.industry_codes import _serialize
        node = NaceCode.objects.create(code="A", title="Agriculture", level=1)
        result = _serialize(node)
        self.assertEqual(result["code"], "A")
        self.assertEqual(result["title"], "Agriculture")
        self.assertEqual(result["level"], 1)
        self.assertIsNone(result["parent_code"])
        self.assertEqual(result["id"], str(node.id))

    def test_serialize_with_parent(self):
        from accounts_api.view.industry_codes import _serialize
        parent = NaceCode.objects.create(code="A", title="Agriculture", level=1)
        child = NaceCode.objects.create(
            code="A01", title="Crop production", level=2, parent=parent
        )
        result = _serialize(child)
        self.assertEqual(result["parent_code"], "A")

    def test_search_filters_inactive_and_matches_prefix(self):
        from accounts_api.view.industry_codes import _search
        NaceCode.objects.create(code="A", title="Agriculture", level=1)
        NaceCode.objects.create(code="A01", title="Crop production", level=2)
        NaceCode.objects.create(
            code="Z99", title="Hidden", level=1, is_active=False
        )
        results = _search(NaceCode, "A", None, None, 20)
        codes = [n.code for n in results]
        self.assertIn("A", codes)
        self.assertIn("A01", codes)
        self.assertNotIn("Z99", codes)

    def test_search_matches_title_substring(self):
        from accounts_api.view.industry_codes import _search
        NaceCode.objects.create(code="A01", title="Crop production", level=2)
        results = _search(NaceCode, "crop", None, None, 20)
        self.assertEqual([n.code for n in results], ["A01"])

    def test_search_filters_by_level(self):
        from accounts_api.view.industry_codes import _search
        NaceCode.objects.create(code="A", title="Agriculture", level=1)
        NaceCode.objects.create(code="A01", title="Crop production", level=2)
        results = _search(NaceCode, "", "2", None, 20)
        self.assertEqual([n.code for n in results], ["A01"])

    def test_search_invalid_level_is_ignored(self):
        from accounts_api.view.industry_codes import _search
        NaceCode.objects.create(code="A", title="Agriculture", level=1)
        # Non-numeric level -> _parse_int returns None -> no level filter.
        results = _search(NaceCode, "", "bad", None, 20)
        self.assertEqual(len(results), 1)

    def test_search_filters_by_parent_code(self):
        from accounts_api.view.industry_codes import _search
        parent = NaceCode.objects.create(code="A", title="Agriculture", level=1)
        NaceCode.objects.create(
            code="A01", title="Crop production", level=2, parent=parent
        )
        results = _search(NaceCode, "", None, "A", 20)
        self.assertEqual([n.code for n in results], ["A01"])

    def test_search_respects_limit(self):
        from accounts_api.view.industry_codes import _search
        for i in range(5):
            NaceCode.objects.create(code=f"B0{i}", title=f"Code {i}", level=2)
        results = _search(NaceCode, "B", None, None, 2)
        self.assertEqual(len(results), 2)


# ═══════════════════════════════════════════════════════════════════════
# NACE / NAICS list endpoint tests
# ═══════════════════════════════════════════════════════════════════════

class NaceCodeListAPITests(BaseAPITestCase):

    URL = "/api/industry-codes/nace/"

    def setUp(self):
        super().setUp()
        self.parent = NaceCode.objects.create(
            code="A", title="Agriculture", level=1
        )
        self.child = NaceCode.objects.create(
            code="A01", title="Crop production", level=2, parent=self.parent
        )

    def test_unauthenticated_denied(self):
        response = self.client.get(self.URL)
        self.assertIn(response.status_code, [401, 403])

    def test_list_all(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["status"])
        self.assertEqual(len(response.data["data"]), 2)

    def test_search_by_code_prefix(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"q": "A01"})
        codes = [r["code"] for r in response.data["data"]]
        self.assertEqual(codes, ["A01"])

    def test_filter_by_level(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"level": 2})
        codes = [r["code"] for r in response.data["data"]]
        self.assertEqual(codes, ["A01"])

    def test_filter_by_parent_code(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"parent_code": "A"})
        codes = [r["code"] for r in response.data["data"]]
        self.assertEqual(codes, ["A01"])

    def test_limit(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"limit": 1})
        self.assertEqual(len(response.data["data"]), 1)


class NaicsCodeListAPITests(BaseAPITestCase):

    URL = "/api/industry-codes/naics/"

    def setUp(self):
        super().setUp()
        self.parent = NaicsCode.objects.create(
            code="11", title="Agriculture", level=2
        )
        self.child = NaicsCode.objects.create(
            code="111", title="Crop Production", level=3, parent=self.parent
        )

    def test_unauthenticated_denied(self):
        response = self.client.get(self.URL)
        self.assertIn(response.status_code, [401, 403])

    def test_list_all(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)

    def test_search_by_title(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"q": "crop"})
        codes = [r["code"] for r in response.data["data"]]
        self.assertEqual(codes, ["111"])

    def test_filter_by_parent_code(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL, {"parent_code": "11"})
        codes = [r["code"] for r in response.data["data"]]
        self.assertEqual(codes, ["111"])


# ═══════════════════════════════════════════════════════════════════════
# Company view error-handling (DatabaseError / unexpected Exception) tests
# ═══════════════════════════════════════════════════════════════════════

class CompanyViewErrorHandlingTests(BaseAPITestCase):

    SERIALIZER = "accounts_api.view.companies.CompanyCreateUpdateSerializer"

    # ---- GET ----
    def test_list_database_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        with mock.patch("accounts_api.view.companies.Company.objects") as m:
            m.select_related.side_effect = DatabaseError("boom")
            response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database error", response.data["message"])

    def test_list_unexpected_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        with mock.patch("accounts_api.view.companies.Company.objects") as m:
            m.select_related.side_effect = RuntimeError("boom")
            response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Unable to fetch companies", response.data["message"])

    # ---- POST ----
    def _mock_serializer(self, save_side_effect):
        patcher = mock.patch(self.SERIALIZER)
        S = patcher.start()
        self.addCleanup(patcher.stop)
        inst = S.return_value
        inst.is_valid.return_value = True
        inst.save.side_effect = save_side_effect
        return S

    def test_create_database_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        self._mock_serializer(DatabaseError("boom"))
        response = self.client.post(
            "/api/companies/", {"name": "X", "tenant": str(self.tenant.id)}
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database error", response.data["message"])

    def test_create_unexpected_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        self._mock_serializer(RuntimeError("boom"))
        response = self.client.post(
            "/api/companies/", {"name": "X", "tenant": str(self.tenant.id)}
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Unable to create company", response.data["message"])

    # ---- PUT ----
    def test_update_database_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        self._mock_serializer(DatabaseError("boom"))
        response = self.client.put(
            f"/api/companies/{self.company.id}/", {"name": "X"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database error", response.data["message"])

    def test_update_unexpected_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        self._mock_serializer(RuntimeError("boom"))
        response = self.client.put(
            f"/api/companies/{self.company.id}/", {"name": "X"}
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("Unable to update company", response.data["message"])

    # ---- DETAIL GET ----
    def test_detail_database_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        with mock.patch("accounts_api.view.companies.Company.objects") as m:
            m.select_related.return_value.get.side_effect = DatabaseError("boom")
            response = self.client.get(f"/api/companies/{self.company.id}/detail/")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database error", response.data["message"])

    def test_detail_unexpected_error_returns_500(self):
        self.client.force_authenticate(user=self.superadmin)
        with mock.patch("accounts_api.view.companies.Company.objects") as m:
            m.select_related.return_value.get.side_effect = RuntimeError("boom")
            response = self.client.get(f"/api/companies/{self.company.id}/detail/")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Unable to fetch company details", response.data["message"])


# ═══════════════════════════════════════════════════════════════════════
# CompanyCreateUpdateSerializer.validate_tenant tests
# ═══════════════════════════════════════════════════════════════════════

class CompanySerializerTests(BaseAPITestCase):

    def _request_for(self, user):
        request = APIRequestFactory().post("/")
        request.user = user
        return request

    def test_validate_tenant_rejects_other_tenant_for_normal_user(self):
        from accounts_api.serializers.company_serializers import (
            CompanyCreateUpdateSerializer,
        )
        other_tenant = Tenant.objects.create(name="Other S", slug="other-s")
        serializer = CompanyCreateUpdateSerializer(
            data={"name": "X", "tenant": str(other_tenant.id)},
            context={"request": self._request_for(self.user)},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("tenant", serializer.errors)

    def test_validate_tenant_allows_own_tenant_for_normal_user(self):
        from accounts_api.serializers.company_serializers import (
            CompanyCreateUpdateSerializer,
        )
        serializer = CompanyCreateUpdateSerializer(
            data={"name": "X", "tenant": str(self.tenant.id)},
            context={"request": self._request_for(self.user)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_tenant_allows_any_tenant_for_superuser(self):
        from accounts_api.serializers.company_serializers import (
            CompanyCreateUpdateSerializer,
        )
        other_tenant = Tenant.objects.create(name="Other SU", slug="other-su")
        serializer = CompanyCreateUpdateSerializer(
            data={"name": "X", "tenant": str(other_tenant.id)},
            context={"request": self._request_for(self.superadmin)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_tenant_without_request_context(self):
        from accounts_api.serializers.company_serializers import (
            CompanyCreateUpdateSerializer,
        )
        serializer = CompanyCreateUpdateSerializer(
            data={"name": "X", "tenant": str(self.tenant.id)},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


# ═══════════════════════════════════════════════════════════════════════
# Module import coverage (trivial placeholder modules)
# ═══════════════════════════════════════════════════════════════════════

class ModuleImportTests(TestCase):

    def test_modules_import(self):
        import importlib
        for name in (
            "accounts_api.views",
            "accounts_api.models",
            "accounts_api.admin",
            "accounts_api.apps",
            "accounts_api.serializers.profile_serializers",
            "accounts_api.serializers.company_serializers",
        ):
            self.assertIsNotNone(importlib.import_module(name))
