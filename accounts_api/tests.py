import uuid
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    Tenant, Company, User, Role, Permission,
    UserRole, UserCompany, UserCompanyRole,
)
from billing.models import CommercialPlan, Subscription


class BaseAPITestCase(TestCase):
    """Shared setup for accounts_api tests."""

    def setUp(self):
        self.client = APIClient()

        self.tenant = Tenant.objects.create(name="API Tenant", slug="api-tenant")

        self.role = Role.objects.create(name="api_admin", tier_level=1)

        self.perm_view = Permission.objects.create(
            code="company.view", description="View companies"
        )
        self.perm_manage = Permission.objects.create(
            code="company.manage", description="Manage companies"
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

        # Give user a plan with company_registry access
        self.plan, _ = CommercialPlan.objects.get_or_create(
            code="basic",
            defaults={
                "name": "Basic", "price": Decimal("99.00"),
                "billing_period": "yearly",
                "comparison": {"company_registry": True},
            },
        )
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
