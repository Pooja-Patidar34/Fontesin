from django.urls import path
from .view.auth import admin_login, admin_logout,register_view,identity_verification_view,apply_view,apply_submit,apply_review_view
from .view.profile import profile_view, company_search_ajax, plans_view
from .view.auth import admin_login, admin_logout, register_view, identity_verification_view, forgot_password, verify_otp, reset_password, check_email_exists
from .view.dashboard import dashboard, consultant_stats, consultant_statistics_page
from accounts.view.company import company_list, toggle_company,company_detail_ajax,company_delete,company_filter_autocomplete, my_companies
from accounts.view.company_import import (
    company_import_upload,
    company_import_status,
    company_import_errors,
    company_import_sample,
)
from .view.user import user_list, toggle_user, assign_roles,role_list,role_detail_ajax,permission_list,save_role,user_detail_ajax,user_edit,add_user,user_delete
from .view.audit import audit_logs,audit_log_detail_ajax
from .view.tenant import tenant_list,toggle_tenant,tenant_detail_ajax,tenant_delete
from .view.website import home, about, worldmap, career, contact, membership, select_plan, invoice_detail
from .view.regions import region_us, region_de, region_cz, region_ae, region_jp, regions_map_view
from .view.consultant import consultant_companies, consultant_users, coordinator_users, coordinator_companies
from .view.veriff import CreateVeriffSessionAPIView
from .view.webhook import veriff_webhook
from billing.views import invoice_list, plan_history, payment_list, payment_approve, payment_reject, payment_edit, payment_detail_ajax, subscription_list, plan_edit, plan_toggle, commission_list, commission_mark_paid, commission_invoice_detail_ajax, commission_invoice_export
from .view.search import global_search
from .view.error import access_denied
from .view.saved_filter import (
    saved_filter_list,
    saved_filter_save,
    saved_filter_delete,
    saved_filter_apply,
    company_connect,
)
from .view.partnership import partnership_list, partnership_action, partnership_cancel
from .view.certification import certification_list, certification_action
from .view.notification import (
    messages_list,
    message_mark_read,
    messages_mark_all_read,
    message_delete,
)


urlpatterns = [
    path("login/", admin_login, name="login"),
    path("logout/", admin_logout, name="logout"),
    path("dashboard/",dashboard, name="dashboard"),
    path("dashboard/consultant-stats/", consultant_stats, name="consultant-stats"),
    path("consultants/<uuid:user_id>/statistics/", consultant_statistics_page, name="consultant-statistics"),
    path("companies/", company_list, name="companies"),
    path("my-companies/", my_companies, name="my-companies"),
    path("companies/filter-autocomplete/", company_filter_autocomplete, name="companies-filter-autocomplete"),
    path("companies/<uuid:company_id>/toggle/", toggle_company, name="company-toggle"),
    path("users/", user_list, name="users"),
    path("users/<uuid:user_id>/toggle/",toggle_user,name="user-toggle",),
    path("users/<uuid:user_id>/delete/",user_delete,name="user-delete",),
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
    path("companies/<uuid:company_id>/delete/", company_delete, name="company-delete"),
    path("companies/<uuid:company_id>/connect/", company_connect, name="company-connect"),

    # Bulk CSV import (superuser only)
    path("companies/import/upload/", company_import_upload, name="company-import-upload"),
    path("companies/import/sample.csv", company_import_sample, name="company-import-sample"),
    path("companies/import/<uuid:job_id>/status/", company_import_status, name="company-import-status"),
    path("companies/import/<uuid:job_id>/errors/", company_import_errors, name="company-import-errors"),

    # Partnerships (basic-plan business users only)
    path("partnerships/", partnership_list, name="partnerships"),
    path("partnerships/<uuid:connection_id>/action/", partnership_action, name="partnership-action"),
    path("partnerships/<uuid:connection_id>/cancel/", partnership_cancel, name="partnership-cancel"),

    # Certifications (consultants only)
    path("certifications/", certification_list, name="certifications"),
    path("certifications/<uuid:company_id>/action/", certification_action, name="certification-action"),

    # Messages / notifications (every account type)
    path("messages/", messages_list, name="messages"),
    path("messages/mark-all-read/", messages_mark_all_read, name="messages-mark-all-read"),
    path("messages/<uuid:notification_id>/read/", message_mark_read, name="message-mark-read"),
    path("messages/<uuid:notification_id>/delete/", message_delete, name="message-delete"),

    # Saved filters (Favorites) — basic business users only
    path("saved-filters/", saved_filter_list, name="saved-filters"),
    path("saved-filters/save/", saved_filter_save, name="saved-filter-save"),
    path("saved-filters/<uuid:filter_id>/apply/", saved_filter_apply, name="saved-filter-apply"),
    path("saved-filters/<uuid:filter_id>/delete/", saved_filter_delete, name="saved-filter-delete"),
    path("register/", register_view, name="register"),
    path("register/check-email/", check_email_exists, name="check-email"),
    path("profile/", profile_view, name="profile"),
    path("profile/company-search/", company_search_ajax, name="profile-company-search"),
    path("plans/", plans_view, name="plans"),
    path("subscriptions/", subscription_list, name="subscriptions"),
    path("subscriptions/<int:plan_id>/edit/", plan_edit, name="plan-edit"),
    path("subscriptions/<int:plan_id>/toggle/", plan_toggle, name="plan-toggle"),
    path("invoices/", invoice_list, name="invoices"),
    path("plan-history/", plan_history, name="plan-history"),
    path("commissions/", commission_list, name="commissions"),
    path("commissions/<int:commission_id>/mark-paid/", commission_mark_paid, name="commission-mark-paid"),
    path("commissions/<int:commission_id>/invoice/", commission_invoice_detail_ajax, name="commission-invoice-detail"),
    path("commissions/<int:commission_id>/export/", commission_invoice_export, name="commission-invoice-export"),
    path("payments/", payment_list, name="payments"),
    path("payments/<int:subscription_id>/approve/", payment_approve, name="payment-approve"),
    path("payments/<int:subscription_id>/reject/", payment_reject, name="payment-reject"),
    path("payments/<int:subscription_id>/edit/", payment_edit, name="payment-edit"),
    path("payments/<int:subscription_id>/detail/", payment_detail_ajax, name="payment-detail"),
    path("search/", global_search, name="global-search"),
    path("access-denied/", access_denied, name="access-denied"),
    path("forgot-password/", forgot_password, name="forgot-password"),
    path("verify-otp/", verify_otp, name="verify-otp"),
    path("reset-password/", reset_password, name="reset-password"),

    #static pages
    # Root URL serves the same home view, so visiting fontesin.com (without
    # /home/) lands users on the home page directly. The named URL 'home'
    # stays on /home/ so existing reverse('home') calls keep pointing at
    # the canonical path.
    path('', home, name='home_root'),
    path('home/', home, name='home'),  # default landing page
    path('about/', about, name='about'),
    path('worldmap/', worldmap, name='worldmap'),
    path('career/', career, name='career'),
    path('contact/', contact, name='contact'),
    path('membership/', membership, name='membership'),
    path('select-plan/', select_plan, name='select_plan'),
    path('invoice/<int:invoice_id>/', invoice_detail, name='invoice_detail'),

    #coordinator regions & map dashboard
    path('regions-map/', regions_map_view, name='regions-map'),

    #staff directory (coordinator + franchise + superuser)
    path('consultants/companies/', consultant_companies, name='consultant-companies'),
    path('consultants/users/', consultant_users, name='consultant-users'),
    path('coordinators/users/', coordinator_users, name='coordinator-users'),
    path('coordinators/companies/', coordinator_companies, name='coordinator-companies'),

    #region specific pages
    path('region/us/', region_us, name='region_us'),
    path('region/de/', region_de, name='region_de'),
    path('region/cz/', region_cz, name='region_cz'),
    path('region/ae/', region_ae, name='region_ae'),
    path('region/jp/', region_jp, name='region_jp'),

    #webhook
    path("veriff/webhook/", veriff_webhook),


    #veriff
    path("veriff/session/", CreateVeriffSessionAPIView.as_view(),name="veriff-session",),
    path("verify/", identity_verification_view, name="identity-verification"),
    path("apply/", apply_view, name="apply"),
    path("apply/submit/", apply_submit, name="apply-submit"),
    path("apply-review/", apply_review_view, name="apply-review"),
]

