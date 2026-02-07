from django.urls import path
from .view.auth import admin_login, admin_logout
from .view.dashboard import dashboard
from accounts.view.company import company_list, toggle_company
from .view.user import user_list, toggle_user, assign_roles,role_list
from .view.audit import audit_logs
from .view.tenant import tenant_list

urlpatterns = [
    path("login/", admin_login, name="login"),
    path("logout/", admin_logout, name="logout"),
    path("",dashboard, name="dashboard"),
    path("companies/", company_list, name="companies"),
    path("companies/<uuid:company_id>/toggle/", toggle_company, name="company-toggle"),
    path("users/", user_list, name="users"),
    path("users/<uuid:user_id>/toggle/",toggle_user,name="user-toggle",),
    path("users/<uuid:user_id>/roles/",assign_roles,name="assign-roles",),
    path("audit-logs/", audit_logs, name="audit-logs"),
    path("roles/", role_list, name="roles"),
    path("tenants/", tenant_list, name="tenants"),
]
