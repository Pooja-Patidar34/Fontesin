from django.urls import path
from .view.auth import admin_login, admin_logout
from .view.dashboard import dashboard
from accounts.view.company import company_list, toggle_company,company_detail_ajax
from .view.user import user_list, toggle_user, assign_roles,role_list,role_detail_ajax,permission_list,save_role,user_detail_ajax,user_edit,add_user
from .view.audit import audit_logs,audit_log_detail_ajax
from .view.tenant import tenant_list,toggle_tenant,tenant_detail_ajax,tenant_delete


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
    path("tenants/<uuid:tenant_id>/toggle/",toggle_tenant,name="tenant-toggle",),
    path("tenants/<uuid:tenant_id>/delete/",tenant_delete, name="tenant-delete"),
    path("audit/logs/<uuid:log_id>/detail/",audit_log_detail_ajax,name="audit_log_detail_ajax",),
    path("tenants/<uuid:tenant_id>/detail/",tenant_detail_ajax,name="tenant-detail",),
    path("companies/<uuid:company_id>/detail/",company_detail_ajax,name="company-detail",),
    path("roles/<uuid:role_id>/detail/",role_detail_ajax,name="role-detail",),
    path("permissions/", permission_list, name="permissions"),
    path("certificates/permissions/", permission_list, name="permissions"),
    path("role-save/", save_role, name="role-save"),
    path("users/<uuid:user_id>/view/", user_detail_ajax, name="user-detail"),
    path("users/<uuid:user_id>/edit/", user_edit, name="user-edit"),
    path("users/add/", add_user, name="add-user"),

]

