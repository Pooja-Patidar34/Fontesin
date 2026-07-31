from django.urls import path
from .view.auth import admin_login, admin_logout,register_view,identity_verification_view,apply_view,apply_submit,apply_review_view
from .view.profile import profile_view, company_search_ajax, plans_view
from .view.auth import admin_login, admin_logout, register_view, identity_verification_view, forgot_password, verify_otp, reset_password, check_email_exists
from .view.dashboard import dashboard, consultant_stats, consultant_statistics_page
from accounts.view.company import company_list, toggle_company,company_detail_ajax,company_delete,company_filter_autocomplete, my_companies, select_company
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
from .view.regions import region_us, region_de, region_cz, region_ae, region_jp, regions_map_view, region_coming_soon, region_detail
from .view.consultant import consultant_companies, consultant_users, coordinator_users, coordinator_companies, business_users
from .view.veriff import CreateVeriffSessionAPIView, VeriffStatusAPIView
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
from .view.join_request import join_requests_list, join_request_action, join_request_cancel, company_leave, company_join
from .view.certification import certification_list, certification_action
from .view.application_review import (
    application_pending,
    applications_list,
    application_action,
)
from .view.coordinator_request import (
    coordinator_request_submit,
    coordinator_requests_list,
    coordinator_request_action,
)
from .view.franchise import (
    franchise_request_view,
    franchise_request_submit,
    franchise_applications_list,
    franchise_application_action,
    franchise_activate,
    franchise_child_requests,
    franchise_child_action,
    franchise_tree,
    franchise_suspend,
    franchise_remove,
    franchise_removal_request,
    franchise_removal_cancel,
    franchise_removal_action,
    franchise_consultants,
    assign_consultant,
    consultant_assignment_remove,
    franchise_add_subfranchise,
    franchise_subfranchise_submit,
    franchise_certified_companies,
    franchise_sales,
    franchise_reports,
)
from .view.notification import (
    messages_list,
    message_mark_read,
    messages_mark_all_read,
    message_delete,
    message_open,
)
from .view.contact_message import (
    contact_messages_list,
    contact_message_mark_read,
    contact_messages_mark_all_read,
    contact_message_delete,
)


urlpatterns = [
    path("login/", admin_login, name="login"),
    path("logout/", admin_logout, name="logout"),
    path("dashboard/",dashboard, name="dashboard"),
    path("dashboard/consultant-stats/", consultant_stats, name="consultant-stats"),
    path("consultants/<uuid:user_id>/statistics/", consultant_statistics_page, name="consultant-statistics"),
    path("companies/", company_list, name="companies"),
    path("my-companies/", my_companies, name="my-companies"),
    path("select-company/", select_company, name="select-company"),
    path("companies/filter-autocomplete/", company_filter_autocomplete, name="companies-filter-autocomplete"),
    path("companies/<uuid:company_id>/toggle/", toggle_company, name="company-toggle"),
    path("users/", user_list, name="users"),
    path("users/<uuid:user_id>/toggle/",toggle_user,name="user-toggle",),
    path("users/<uuid:user_id>/delete/",user_delete,name="user-delete",),
    path("users/<uuid:user_id>/roles/",assign_roles,name="assign-roles",),
    path("audit-logs/", audit_logs, name="audit-logs"),
    path("roles/", role_list, name="roles"),
    path("franchises/", tenant_list, name="tenants"),
    path("franchises/<uuid:tenant_id>/toggle/",toggle_tenant,name="tenant-toggle",),
    path("franchises/<uuid:tenant_id>/delete/",tenant_delete, name="tenant-delete"),
    path("audit/logs/<uuid:log_id>/detail/",audit_log_detail_ajax,name="audit_log_detail_ajax",),
    path("franchises/<uuid:tenant_id>/detail/",tenant_detail_ajax,name="tenant-detail",),
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

    # Join requests (business users join existing companies from their profile;
    # the company owner approves / declines here)
    path("join-requests/", join_requests_list, name="join-requests"),
    path("join-requests/<uuid:request_id>/action/", join_request_action, name="join-request-action"),
    path("join-requests/<uuid:request_id>/cancel/", join_request_cancel, name="join-request-cancel"),
    path("companies/<uuid:company_id>/leave/", company_leave, name="company-leave"),
    path("companies/<uuid:company_id>/join/", company_join, name="company-join"),

    # Certifications (consultants only)
    path("certifications/", certification_list, name="certifications"),
    path("certifications/<uuid:company_id>/action/", certification_action, name="certification-action"),

    # Coordinator role requests (BU submit / Super Admin review)
    path("coordinator-requests/", coordinator_requests_list, name="coordinator-requests"),
    path("coordinator-requests/submit/", coordinator_request_submit, name="coordinator-request-submit"),
    path("coordinator-requests/<uuid:request_id>/action/", coordinator_request_action, name="coordinator-request-action"),

    # Franchise requests (user submit / Super Admin review → approve → activate)
    path("franchise-request/", franchise_request_view, name="franchise-request"),
    path("franchise-request/submit/", franchise_request_submit, name="franchise-request-submit"),
    path("franchise-applications/", franchise_applications_list, name="franchise-applications"),
    path("franchise-applications/<uuid:application_id>/action/", franchise_application_action, name="franchise-application-action"),
    path("franchises/<uuid:tenant_id>/activate/", franchise_activate, name="franchise-activate"),
    # Direct-parent (Master/National/Regional) review of sub-franchise requests
    path("franchise-sub-requests/", franchise_child_requests, name="franchise-child-requests"),
    path("franchise-sub-requests/<uuid:application_id>/action/", franchise_child_action, name="franchise-child-action"),
    # Franchise tree (scoped by visibility) + suspension + consultant management
    path("franchise-tree/", franchise_tree, name="franchise-tree"),
    path("franchises/<uuid:tenant_id>/suspend/", franchise_suspend, name="franchise-suspend"),
    # Removal (§9.2 wind-down): ends the franchise for its holder and every
    # sub-franchise beneath it. Distinct from tenant-delete, which is the plain
    # partition delete for a non-franchise tenant.
    path("franchises/<uuid:tenant_id>/remove/", franchise_remove, name="franchise-remove"),
    # Holder-initiated exit: request → the granting authority (direct parent
    # holder, or the Platform Admin for a Master) approves before anything is
    # wound down.
    path("franchises/<uuid:tenant_id>/removal-request/", franchise_removal_request, name="franchise-removal-request"),
    path("franchise-removals/<uuid:removal_id>/cancel/", franchise_removal_cancel, name="franchise-removal-cancel"),
    path("franchise-removals/<uuid:removal_id>/action/", franchise_removal_action, name="franchise-removal-action"),
    path("franchise-consultants/", franchise_consultants, name="franchise-consultants"),
    path("franchise-consultants/assign/", assign_consultant, name="assign-consultant"),
    path("franchise-consultants/<uuid:assignment_id>/remove/", consultant_assignment_remove, name="consultant-assignment-remove"),
    # Holder proposes a child franchise under one of their nodes (spec §6.3)
    path("franchise-add-sub/", franchise_add_subfranchise, name="franchise-add-subfranchise"),
    path("franchise-add-sub/submit/", franchise_subfranchise_submit, name="franchise-subfranchise-submit"),
    # Subtree business data (spec §6.3): certified companies, plan sales, reports
    path("franchise-certified-companies/", franchise_certified_companies, name="franchise-certified-companies"),
    path("franchise-sales/", franchise_sales, name="franchise-sales"),
    path("franchise-reports/", franchise_reports, name="franchise-reports"),

    # Messages / notifications (every account type)
    path("messages/", messages_list, name="messages"),
    path("messages/mark-all-read/", messages_mark_all_read, name="messages-mark-all-read"),
    path("messages/<uuid:notification_id>/read/", message_mark_read, name="message-mark-read"),
    path("messages/<uuid:notification_id>/open/", message_open, name="message-open"),
    path("messages/<uuid:notification_id>/delete/", message_delete, name="message-delete"),

    # Contact messages (website contact form → Super Admin inbox)
    path("contact-messages/", contact_messages_list, name="contact-messages"),
    path("contact-messages/mark-all-read/", contact_messages_mark_all_read, name="contact-messages-mark-all-read"),
    path("contact-messages/<uuid:message_id>/read/", contact_message_mark_read, name="contact-message-mark-read"),
    path("contact-messages/<uuid:message_id>/delete/", contact_message_delete, name="contact-message-delete"),

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
    # Canonical home is the bare root URL: fontesin.com/ serves index.html
    # directly (no redirect). The 'home' name maps here, so every
    # {% url 'home' %} / reverse('home') link keeps users on fontesin.com
    # instead of bouncing to /home/.
    path('', home, name='home'),
    # Legacy /home/ path kept under 'home_root' so old bookmarks/links still
    # resolve to the same page.
    path('home/', home, name='home_root'),
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
    path('users/business/', business_users, name='business-users'),
    path('coordinators/companies/', coordinator_companies, name='coordinator-companies'),

    #region specific pages
    path('region/us/', region_us, name='region_us'),
    path('region/de/', region_de, name='region_de'),
    path('region/cz/', region_cz, name='region_cz'),
    path('region/ae/', region_ae, name='region_ae'),
    path('region/jp/', region_jp, name='region_jp'),
    path('region/<str:code>/coming-soon/', region_coming_soon, name='region_coming_soon'),
    # Generic data-driven profile for every other curated country. Declared
    # AFTER the bespoke region pages above so /region/us/ etc. still resolve to
    # their dedicated views; this catches /region/se/, /region/gb/, …
    path('region/<str:code>/', region_detail, name='region_detail'),

    #webhook
    path("veriff/webhook/", veriff_webhook),


    #veriff
    path("veriff/session/", CreateVeriffSessionAPIView.as_view(),name="veriff-session",),
    path("veriff/status/", VeriffStatusAPIView.as_view(), name="veriff-status"),
    path("verify/", identity_verification_view, name="identity-verification"),
    path("apply/", apply_view, name="apply"),
    path("apply/submit/", apply_submit, name="apply-submit"),
    path("apply-review/", apply_review_view, name="apply-review"),
    # Coordinator / franchise application approval
    path("application-pending/", application_pending, name="application-pending"),
    path("applications/", applications_list, name="applications"),
    path("applications/<uuid:user_id>/action/", application_action, name="application-action"),
]

