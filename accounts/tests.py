from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
import uuid

from accounts.models import (
    Tenant,
    Company,
    User,
    Role,
    Permission,
    UserCompany,
    UserCompanyRole,
    AuditLog,
)
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip


# base test case to set up common data for IAM tests
class BaseIAMTestCase(TestCase):

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )

        # Company
        self.company = Company.objects.create(
            tenant=self.tenant,
            name="Company A",
        )

        # Permissions
        self.permission_view = Permission.objects.create(
            code="company.view",
            description="View companies",
        )
        self.permission_manage = Permission.objects.create(
            code="company.manage",
            description="Manage companies",
        )

        # Role
        self.role = Role.objects.create(
            tenant=self.tenant,
            name="Admin",
        )

        # Attach permissions directly to role (M2M)
        self.role.permissions.add(self.permission_view)

        # Tenant user
        self.user = User.objects.create_user(
            email="user@test.com",
            password="test123",
            tenant=self.tenant,
            is_active=True,
        )

        # User - Company mapping
        user_company = UserCompany.objects.create(
            user=self.user,
            company=self.company,
            is_primary=True,
        )

        # Assign role to user at company level
        UserCompanyRole.objects.create(
            user_company=user_company,
            role=self.role,
        )

        # Super admin
        self.superadmin = User.objects.create_superuser(
            email="admin@test.com",
            password="admin123",
            tenant=self.tenant,
        )

#permission logic tests
class PermissionLogicTests(BaseIAMTestCase):

    def test_user_has_permission(self):
        self.assertTrue(has_permission(self.user, "company.view"))

    def test_user_does_not_have_permission(self):
        self.assertFalse(has_permission(self.user, "company.manage"))

    def test_inactive_user_has_no_permission(self):
        self.user.is_active = False
        self.user.save()
        self.assertFalse(has_permission(self.user, "company.view"))

    def test_superadmin_has_all_permissions(self):
        self.assertTrue(has_permission(self.superadmin, "any.random.permission"))


class PermissionEdgeCaseTests(TestCase):

    def test_permission_with_no_user(self):
        self.assertFalse(has_permission(None, "company.view"))

    def test_permission_with_anonymous_user(self):
        self.assertFalse(has_permission(AnonymousUser(), "company.view"))


#company list view tests
class CompanyViewTests(BaseIAMTestCase):

    def test_company_list_requires_login(self):
        response = self.client.get(reverse("companies"))
        self.assertEqual(response.status_code, 302)

    def test_company_list_with_permission(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("companies"))
        self.assertEqual(response.status_code, 200)

    def test_company_list_without_permission(self):
        UserCompanyRole.objects.all().delete()

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("companies"))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_company_list_with_tenant_filter(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.get(
            reverse("companies"),
            {"tenant": str(self.tenant.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Company A")


#company toggle view tests
class CompanyToggleTests(BaseIAMTestCase):

    def test_toggle_company_creates_audit_log(self):
        self.client.login(email="admin@test.com", password="admin123")

        self.client.get(
            reverse("company-toggle", args=[self.company.id])
        )

        self.company.refresh_from_db()
        self.assertFalse(self.company.is_active)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.entity_type, "Company")
        self.assertEqual(log.action, "company.deactivated")

    def test_tenant_admin_cannot_toggle_other_tenant_company(self):
        other_tenant = Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b",
        )

        other_company = Company.objects.create(
            tenant=other_tenant,
            name="Other Company",
        )

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("company-toggle", args=[other_company.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_toggle_company_redirects_without_referer(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.get(
            reverse("company-toggle", args=[self.company.id]),
            HTTP_REFERER="",
        )

        self.assertEqual(response.status_code, 302)

#audit log model tests
class AuditLogModelTests(BaseIAMTestCase):

    def test_audit_log_is_immutable(self):
        log = AuditLog.objects.create(
            tenant=self.tenant,
            actor=self.superadmin,
            action="test.action",
            entity_type="Test",
            entity_id=uuid.uuid4(),
            metadata={},
        )

        with self.assertRaises(RuntimeError):
            log.metadata = {"changed": True}
            log.save()


#audit log view tests
class AuditLogViewTests(BaseIAMTestCase):

    def setUp(self):
        super().setUp()

        # Create audit permission
        self.audit_permission = Permission.objects.create(
            code="audit.view",
            description="View audit logs",
        )

        # Attach permission directly to role (M2M)
        self.role.permissions.add(self.audit_permission)

        # Create an audit log entry
        AuditLog.objects.create(
            tenant=self.tenant,
            actor=self.superadmin,
            action="test.action",
            entity_type="Test",
            entity_id=uuid.uuid4(),
            metadata={},
        )

    def test_audit_logs_requires_login(self):
        response = self.client.get(reverse("audit-logs"))
        self.assertEqual(response.status_code, 302)

    def test_user_without_permission_is_denied(self):
        # Remove permission from role
        self.role.permissions.clear()

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("audit-logs"))

        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_can_view_logs(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("audit-logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test.action")

    def test_superadmin_sees_all_logs(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("audit-logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test.action")

    def test_invalid_page_falls_back_to_page_1(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(
            reverse("audit-logs") + "?page=invalid"
        )
        self.assertEqual(response.status_code, 200)


#role assignment tests
class RoleAssignmentTests(BaseIAMTestCase):

    def test_assign_roles_creates_audit_log(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.post(
            reverse("assign-roles", args=[self.user.id]),
            {"roles": [str(self.role.id)]},
        )

        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.action, "roles_updated")
        self.assertEqual(log.entity_type, "User")


#tenant isolation tests
class TenantIsolationTests(BaseIAMTestCase):

    def test_tenant_admin_cannot_access_other_tenant_user(self):
        other_tenant = Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b",
        )

        other_user = User.objects.create_user(
            email="other@test.com",
            password="test123",
            tenant=other_tenant,
        )

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("assign-roles", args=[other_user.id])
        )

        self.assertEqual(response.status_code, 403)


#client IP retrieval tests
class ClientIPTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_from_x_forwarded_for(self):
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 5.6.7.8"

        ip = get_client_ip(request)
        self.assertEqual(ip, "1.2.3.4")

    def test_get_client_ip_from_remote_addr(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "9.8.7.6"

        ip = get_client_ip(request)
        self.assertEqual(ip, "9.8.7.6")


#admin authentication view tests
class AdminAuthViewTests(BaseIAMTestCase):

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_login_with_invalid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"email": "wrong@test.com", "password": "wrongpass"},
            follow=True,
        )

        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Invalid credentials", messages)

    def test_login_with_non_staff_user_denied(self):
        response = self.client.post(
            reverse("login"),
            {"email": "user@test.com", "password": "test123"},
            follow=True,
        )

        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("You are not allowed to access admin panel", messages)

    def test_login_with_staff_user_success(self):
        response = self.client.post(
            reverse("login"),
            {"email": "admin@test.com", "password": "admin123"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_admin_logout(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("login"))


# Dashboard view tests
class DashboardViewTests(BaseIAMTestCase):

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_superadmin_dashboard_metrics(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("total_tenants", response.context)
        self.assertIn("total_companies", response.context)
        self.assertIn("total_users", response.context)
        self.assertEqual(response.context["active_menu"], "dashboard")

    def test_tenant_user_dashboard_metrics(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("total_tenants", response.context)
        self.assertEqual(response.context["active_menu"], "dashboard")


# Tenant views and toggle tests
class TenantViewTests(BaseIAMTestCase):

    def test_tenant_list_requires_login(self):
        response = self.client.get(reverse("tenants"))
        self.assertEqual(response.status_code, 302)

    def test_tenant_list_denied_for_non_superadmin(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("tenants"))
        self.assertEqual(response.status_code, 403)

    def test_tenant_list_superadmin_success(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("tenants"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tenant A")


class TenantToggleTests(BaseIAMTestCase):

    def test_toggle_tenant_denied_for_non_superadmin(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("tenant-toggle", args=[self.tenant.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_toggle_tenant_creates_audit_log(self):
        self.client.login(email="admin@test.com", password="admin123")
        self.client.get(reverse("tenant-toggle", args=[self.tenant.id]))

        self.tenant.refresh_from_db()
        self.assertFalse(self.tenant.is_active)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.entity_type, "Tenant")
        self.assertEqual(log.action, "tenant.deactivated")

#user list and toggle tests

class UserListViewTests(BaseIAMTestCase):

    def setUp(self):
        super().setUp()

        # Add required permission for user.view
        permission = Permission.objects.create(
            code="user.view",
            description="View users",
        )
        self.role.permissions.add(permission)

    def test_user_list_requires_login(self):
        response = self.client.get(reverse("users"))
        self.assertEqual(response.status_code, 302)

    def test_user_list_permission_denied(self):
        # Remove permission
        self.role.permissions.clear()

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(reverse("users"))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_user_list(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(reverse("users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "user@test.com")

    def test_superadmin_with_tenant_filter(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(
            reverse("users"),
            {"tenant": str(self.tenant.id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_tenant"],
            str(self.tenant.id)
        )

    def test_superadmin_with_tenant_and_company_filter(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(
            reverse("users"),
            {
                "tenant": str(self.tenant.id),
                "company": str(self.company.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_company"],
            str(self.company.id)
        )

    def test_tenant_user_with_company_filter(self):
        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("users"),
            {"company": str(self.company.id)},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_page_fallback(self):
        self.client.login(email="admin@test.com", password="admin123")
        response = self.client.get(
            reverse("users") + "?page=invalid"
        )
        self.assertEqual(response.status_code, 200)




class ToggleUserTests(BaseIAMTestCase):

    def setUp(self):
        super().setUp()

        # Create manage permission
        self.manage_permission = Permission.objects.create(
            code="user.manage",
            description="Manage users",
        )

        # Attach permission directly to role (M2M)
        self.role.permissions.add(self.manage_permission)

    def test_toggle_user_permission_denied(self):
        # Remove permission from role
        self.role.permissions.remove(self.manage_permission)

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("user-toggle", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_superadmin_toggle_user(self):
        self.client.login(email="admin@test.com", password="admin123")
        self.client.get(reverse("user-toggle", args=[self.user.id]))

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.action, "user.deactivated")
        self.assertEqual(log.entity_type, "User")

    def test_tenant_admin_toggle_own_user(self):
        self.client.login(email="user@test.com", password="test123")
        self.client.get(reverse("user-toggle", args=[self.user.id]))

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_tenant_admin_cannot_toggle_other_tenant_user(self):
        other_tenant = Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b"
        )

        other_user = User.objects.create_user(
            email="other@test.com",
            password="test123",
            tenant=other_tenant,
        )

        self.client.login(email="user@test.com", password="test123")
        response = self.client.get(
            reverse("user-toggle", args=[other_user.id])
        )

        # Must not leak existence of other-tenant users
        self.assertEqual(response.status_code, 404)


# Assign roles view tests

class AssignRolesViewTests(BaseIAMTestCase):

    def setUp(self):
        super().setUp()

        # Create role.manage permission
        self.manage_permission = Permission.objects.create(
            code="role.manage",
            description="Manage roles",
        )

        # Attach permission directly to role (M2M)
        self.role.permissions.add(self.manage_permission)

    def test_assign_roles_get(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.get(
            reverse("assign-roles", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 200)

    def test_assign_roles_permission_denied(self):
        # Remove permission from role
        self.role.permissions.remove(self.manage_permission)

        self.client.login(email="user@test.com", password="test123")

        response = self.client.get(
            reverse("assign-roles", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_assign_roles_post_success(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.post(
            reverse("assign-roles", args=[self.user.id]),
            {"roles": [str(self.role.id)]},
        )

        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.action, "roles_updated")
        self.assertEqual(log.entity_type, "User")

    def test_assign_roles_empty_list(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.post(
            reverse("assign-roles", args=[self.user.id]),
            {"roles": []},
        )

        self.assertEqual(response.status_code, 302)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.metadata["new_roles"], [])


# Role list view tests
class RoleListViewTests(BaseIAMTestCase):

    def setUp(self):
        super().setUp()

        # Create role.view permission
        self.view_permission = Permission.objects.create(
            code="role.view",
            description="View roles",
        )

        # Attach permission directly to role (M2M)
        self.role.permissions.add(self.view_permission)

    def test_role_list_permission_denied(self):
        # Remove permission from role
        self.role.permissions.remove(self.view_permission)

        self.client.login(email="user@test.com", password="test123")

        response = self.client.get(reverse("roles"))
        self.assertEqual(response.status_code, 403)

    def test_role_list_success(self):
        self.client.login(email="user@test.com", password="test123")

        response = self.client.get(reverse("roles"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin")

    def test_role_list_superadmin(self):
        self.client.login(email="admin@test.com", password="admin123")

        response = self.client.get(reverse("roles"))
        self.assertEqual(response.status_code, 200)
