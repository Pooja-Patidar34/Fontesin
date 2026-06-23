# Do Not Revisit

Areas complete or frozen. **Do not scan, re-wrap, or refactor** unless fixing a confirmed bug.

---

## Completed Modules (i18n)

| Module | Status |
|--------|--------|
| M0 Infrastructure | ✅ |
| M1 Base Layout & Shared UI | ✅ |
| M2 Authentication & Onboarding | ✅ |
| M3 Companies | ✅ |
| M4 Users & Roles | ✅ |
| M5 Billing | ✅ |
| M6 Notifications (Python) | ✅ |
| M7 Workflows | ✅ |
| M10 REST API (message strings) | ✅ |
| M11 Constants & Enums | ✅ |
| M13 Middleware | ✅ |
| M12 Email (OTP only) | ✅ partial |
| M8 Profile & Dashboard remainder | ✅ |
| M9 Website & PWA | ✅ |

**Not converted:** `templates/regions/*` (out of scope v1)

---

## Frozen Architecture

See [architecture-decisions.md](architecture-decisions.md) → **Do Not Change**.

Includes: middleware order, locale settings, CI workflow, `APILocaleMixin` contract, API envelope shape, 4-locale policy.

---

## Stable Infrastructure (Phase 1)

- `FontEsin/settings.py` (i18n block)
- `FontEsin/middleware/locale.py`
- `FontEsin/templatetags/i18n_extras.py`
- `templates/partials/_language_switcher.html`
- `templates/partials/_auth_lang_switcher.html`
- `.github/workflows/i18n.yml`
- `scripts/compile_i18n.sh`

---

## Stable Shared Shell (Phase 2)

- `templates/base/base.html`, `templates/base/toasts.html`
- `templates/403.html`, `templates/404.html`, `templates/500.html`
- `static/adminlte/js/main.js` (toast i18n)
- `static/adminlte/js/no_emoji.js`
- `FontEsin/urls.py` (`i18n/`, `jsi18n/`)

---

## Stable Auth & Email (Phase 3)

- All `templates/auth/*.html` (10 files)
- `accounts/view/auth.py`
- `accounts/utils/mailer.py`
- `templates/email/otp_password_reset.html`, `.txt`

---

## Stable Backend Cross-Cutting (Phase 4)

- `FontEsin/i18n/__init__.py`, `FontEsin/i18n/drf.py`
- `accounts/forms/company_form.py`, `accounts/forms/tenant_form.py`
- `accounts/utils/notifications.py`
- `accounts/constants.py`
- `accounts_api/view/companies.py`, `accounts_api/view/profile.py`
- `accounts_api/serializers/company_serializers.py`
- `FontEsin/middleware/no_emoji.py`, `billing/utils.py`
- View Python messages: `application_review.py`, `certification.py`, `company.py`, `coordinator_request.py`, `dashboard.py`, `join_request.py`, `notification.py`, `partnership.py`, `profile.py`, `saved_filter.py`, `tenant.py`, `user.py`, `website.py`

---

## Stable Companies (Phase 5)

- `templates/dashboard/companies.html` + `_company_*` partials
- `templates/dashboard/my_companies.html`, `consultant_companies.html`
- `accounts/view/company_import.py`, `company.py` (validation)
- `scripts/sync_phase5_po.py`, `wrap_phase5_companies_templates.py`

---

## Stable Users, Billing & Workflows (Phase 6)

- Users: `users.html`, `_users_panel.html`, `assign_roles.html`, `roles.html`, `permissions.html`, `business_users.html`, `consultant_users.html`
- Billing: `plans.html`, `subscriptions.html`, `payments.html`, `_payments_panel.html`, `commissions.html`, `_commissions_panel.html`, `_commission_invoice_modal.html`, `invoices.html`, `plan_history.html`
- Workflows: `join_requests.html`, `partnerships.html`, `coordinator_requests.html`, `applications.html`
- `templates/profile/_plan_card.html`
- `billing/plan_i18n.py`, `billing/templatetags/plan_i18n_tags.py`, `billing/views.py` (Phase 6 work)
- `scripts/sync_phase6_po.py`

---

## Stable Profile & Dashboard Remainder (Phase 7)

- `templates/profile/profile.html`, `templates/profile/_join_company_form.html`
- `templates/dashboard/index.html`, `search.html`, `messages.html`, `contact_messages.html`
- `templates/dashboard/certifications.html`, `saved_filters.html`
- `templates/dashboard/audit_logs.html`, `_audit_logs_panel.html`
- `templates/dashboard/consultant_statistics.html`
- `templates/dashboard/tenants.html`, `_tenants_panel.html`, `tenant_confirm_delete.html`
- `templates/dashboard/regions_map.html`
- `scripts/sync_phase7_po.py`

---

## Stable Website & PWA (Phase 8)

- All `templates/website/*.html` (9 files)
- `static/adminlte/manifest.json`, `static/adminlte/js/sw.js`
- `accounts/view/website.py` (`comparison_rows` labels)
- `scripts/sync_phase8_po.py`, `scripts/wrap_phase8_website.py`
- Final-pass gaps closed: `index.html` region/plan cards, `contact.html` form/address, `about.html` team alts, `invoice.html` supplier address

---

## Stable Phase 9 Tooling & Catalogs

- `locale/{en,de,es,fr}/LC_MESSAGES/{django,djangojs}.po` — filled (~100%)
- `locale/{en,de,es,fr}/LC_MESSAGES/{django,djangojs}.mo` — compiled
- `scripts/phase9_fill_po.py`, `phase9_validate_po.py`, `phase9_compile_po.py`, `phase9_po_stats.py`, `phase9_qa.py`, `phase9_unfuzzy_po.py`
- `scripts/.phase9_mt_cache.json` — MT cache (do not delete; speeds re-fill)

---

## Do Not Re-Analyze

| Area | Reason |
|------|--------|
| Planning docs in `.cursor/multilingual-*.md` | Reference only; use `.cursor/memory/` for active work |
| `templates/regions/*` | Out of scope v1 |
| Low-traffic views: `error.py`, `webhook.py`, `veriff.py`, `regions.py`, `audit.py`, `consultant.py` | Intentionally skipped Phase 4 |
| NACE/NAICS code labels | Out of scope |
| Legacy DB notification text | Out of scope |
| Management command output | Out of scope |
