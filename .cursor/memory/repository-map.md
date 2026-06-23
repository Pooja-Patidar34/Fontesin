# Repository Map

Module index — paths only. Use to scope sessions; do not full-repo scan.

**Infrastructure:** `FontEsin/settings.py`, `FontEsin/urls.py`, `FontEsin/middleware/locale.py`, `FontEsin/middleware/no_emoji.py`, `FontEsin/i18n/`, `FontEsin/templatetags/i18n_extras.py`, `locale/`, `.github/workflows/i18n.yml`

**Shared:** `templates/base/base.html`, `templates/base/toasts.html`, `templates/403.html`, `templates/404.html`, `templates/500.html`, `templates/partials/_language_switcher.html`, `templates/partials/_auth_lang_switcher.html`, `static/adminlte/js/main.js`, `static/adminlte/js/no_emoji.js`, `FontEsin/static/js/djangojs-catalog.js`

---

## Authentication

**Templates**
- `templates/auth/application_pending.html`
- `templates/auth/apply.html`
- `templates/auth/apply_review.html`
- `templates/auth/forgot_password.html`
- `templates/auth/login.html`
- `templates/auth/pending_approval.html`
- `templates/auth/register.html`
- `templates/auth/reset_password.html`
- `templates/auth/verify.html`
- `templates/auth/verify_otp.html`

**Views**
- `accounts/view/auth.py`
- `accounts/view/application_review.py`
- `accounts/view/veriff.py`

**Forms**
- (inline in views / registration flow)

**APIs**
- (auth via session views, not DRF)

**JS**
- (inline in auth templates; shared `main.js` for toasts)

**Email**
- `templates/email/otp_password_reset.html`
- `templates/email/otp_password_reset.txt`

---

## Companies

**Templates**
- `templates/dashboard/companies.html`
- `templates/dashboard/_company_create_modal.html`
- `templates/dashboard/_company_import_modal.html`
- `templates/dashboard/_company_row.html`
- `templates/dashboard/_companies_rows.html`
- `templates/dashboard/_companies_pagination.html`
- `templates/dashboard/my_companies.html`
- `templates/dashboard/consultant_companies.html`

**Views**
- `accounts/view/company.py`
- `accounts/view/company_import.py`

**Forms**
- `accounts/forms/company_form.py`

**APIs**
- `accounts_api/view/companies.py`
- `accounts_api/serializers/company_serializers.py`

**JS**
- `window.COMPANY_I18N` in `templates/dashboard/companies.html`, `_company_create_modal.html`, `_company_import_modal.html`

**Email**
- (none)

---

## Users

**Templates**
- `templates/dashboard/users.html`
- `templates/dashboard/_users_panel.html`
- `templates/dashboard/assign_roles.html`
- `templates/dashboard/roles.html`
- `templates/dashboard/permissions.html`
- `templates/dashboard/business_users.html`
- `templates/dashboard/consultant_users.html`

**Views**
- `accounts/view/user.py`
- `accounts/view/tenant.py`

**Forms**
- `accounts/forms/tenant_form.py`

**APIs**
- (user actions via dashboard views)

**JS**
- `window.USER_I18N` in `users.html`, `roles.html`, `permissions.html`, `business_users.html`, `consultant_users.html`

**Email**
- (none)

---

## Billing

**Templates**
- `templates/dashboard/plans.html`
- `templates/dashboard/subscriptions.html`
- `templates/dashboard/payments.html`
- `templates/dashboard/_payments_panel.html`
- `templates/dashboard/commissions.html`
- `templates/dashboard/_commissions_panel.html`
- `templates/dashboard/_commission_invoice_modal.html`
- `templates/dashboard/invoices.html`
- `templates/dashboard/plan_history.html`
- `templates/profile/_plan_card.html` (included by billing)

**Views**
- `billing/views.py`

**Forms**
- (none dedicated)

**APIs**
- (plan-gate errors in `billing/utils.py`)

**JS**
- `window.BILLING_I18N` in `subscriptions.html`, `payments.html`, `commissions.html`

**Email**
- (none in billing module)

**i18n helpers**
- `billing/plan_i18n.py`
- `billing/templatetags/plan_i18n_tags.py`
- `billing/utils.py`

---

## Notifications

**Templates**
- `templates/dashboard/messages.html` *(Phase 7 — not yet wrapped)*

**Views**
- `accounts/view/notification.py`

**Forms**
- (none)

**APIs**
- (none)

**JS**
- (inline in messages template — Phase 7)

**Email**
- (none)

**Utils**
- `accounts/utils/notifications.py`

---

## Profile

**Templates**
- `templates/profile/profile.html` *(Phase 7)*
- `templates/profile/_join_company_form.html` *(Phase 7)*
- `templates/profile/_plan_card.html` *(Phase 6 — done)*

**Views**
- `accounts/view/profile.py`
- `accounts/view/saved_filter.py`
- `accounts/view/certification.py`

**Forms**
- `accounts/forms/certificate_form.py`

**APIs**
- `accounts_api/view/profile.py`
- `accounts_api/serializers/profile_serializers.py`

**JS**
- (Phase 7 — profile templates)

**Email**
- (none)

---

## Website

**Templates**
- `templates/website/index.html` *(Phase 8 — done)*
- `templates/website/about.html` *(Phase 8 — done)*
- `templates/website/contact.html` *(Phase 8 — done)*
- `templates/website/career.html` *(Phase 8 — done)*
- `templates/website/worldmap.html` *(Phase 8 — done)*
- `templates/website/_world_map.html` *(Phase 8 — done)*
- `templates/website/upgrade_required.html` *(Phase 8 — done)*
- `templates/website/membership.html` *(Phase 8 — done)*
- `templates/website/invoice.html` *(Phase 8 — done)*

**Views**
- `accounts/view/website.py`
- `accounts/view/regions.py` *(out of scope v1)*

**Forms**
- (none)

**APIs**
- (none)

**JS**
- `static/adminlte/manifest.json` *(Phase 8 — done)*
- `static/adminlte/js/sw.js` *(Phase 8 — done)*
- `WEBSITE_I18N`, `WEBSITE_MAP_I18N`, `PWA_I18N` bridges in website templates

**Email**
- (none)

---

## Dashboard (remainder — Phase 7)

**Templates**
- `templates/dashboard/index.html`
- `templates/dashboard/search.html`
- `templates/dashboard/messages.html`
- `templates/dashboard/contact_messages.html`
- `templates/dashboard/certifications.html`
- `templates/dashboard/saved_filters.html`
- `templates/dashboard/audit_logs.html`
- `templates/dashboard/_audit_logs_panel.html`
- `templates/dashboard/consultant_statistics.html`
- `templates/dashboard/tenants.html`
- `templates/dashboard/_tenants_panel.html`
- `templates/dashboard/tenant_confirm_delete.html`
- `templates/dashboard/regions_map.html`

**Workflow templates** *(Phase 6 — done)*
- `templates/dashboard/join_requests.html`
- `templates/dashboard/partnerships.html`
- `templates/dashboard/coordinator_requests.html`
- `templates/dashboard/applications.html`

**Views**
- `accounts/view/dashboard.py`
- `accounts/view/search.py`
- `accounts/view/contact_message.py`
- `accounts/view/audit.py`
- `accounts/view/consultant.py`
- `accounts/view/join_request.py`
- `accounts/view/partnership.py`
- `accounts/view/coordinator_request.py`

**Forms**
- (module-specific — see Companies, Users, Profile)

**APIs**
- (dashboard uses server-rendered views)

**JS**
- `window.WORKFLOW_I18N` in `join_requests.html`, `partnerships.html` *(Phase 6)*

**Email**
- (none)

---

## API

**Views**
- `accounts_api/view/companies.py`
- `accounts_api/view/profile.py`
- `accounts_api/view/industry_codes.py`
- `accounts_api/views.py`
- `accounts_api/urls.py`

**Serializers**
- `accounts_api/serializers/company_serializers.py`
- `accounts_api/serializers/profile_serializers.py`

**i18n**
- `FontEsin/i18n/drf.py` (`APILocaleMixin`)

**Skipped (low-traffic / admin)**
- `accounts/view/error.py`, `search.py`, `webhook.py`, `veriff.py`, `regions.py`, `contact_message.py`, `consultant.py`, `audit.py`

---

## Scripts (i18n maintenance)

- `scripts/compile_i18n.sh`
- `scripts/sync_phase3_po.py`, `scripts/sync_phase4_po.py`, `scripts/sync_phase5_po.py`, `scripts/sync_phase6_po.py`, `scripts/sync_phase7_po.py`, `scripts/sync_phase8_po.py`
- `scripts/wrap_phase4_i18n.py`, `scripts/wrap_phase5_companies_templates.py`
- `scripts/gen_phase3_translations.py`, `scripts/fill_de_auth_mt.py`, `scripts/unfuzzy_auth_po.py`
