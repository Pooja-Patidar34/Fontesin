# Multilingual Task List — FONTESIN

Checkbox task list for 7–8 day AI-assisted implementation.  
**Locales:** `en`, `de`, `es`, `fr` | **Fallback:** always English

---

## Day 1 — Infrastructure (M0)

- [ ] Add `LANGUAGES`, `LOCALE_PATHS`, `LANGUAGE_CODE = "en"` to `FontEsin/settings.py`
- [ ] Add `LocaleMiddleware` after `SessionMiddleware`
- [ ] Create `FontEsin/middleware/locale.py` (user preference + session)
- [ ] Create `locale/en/LC_MESSAGES/django.po` skeleton
- [ ] Add `path("i18n/", include("django.conf.urls.i18n"))` to `FontEsin/urls.py`
- [ ] Create `templates/partials/_language_switcher.html`
- [ ] Create `FontEsin/templatetags/i18n_extras.py`
- [ ] Narrow `LanguageChoices` to 4 locales in `accounts/constants.py`
- [ ] Add `compilemessages` to CI/deploy pipeline
- [ ] Save planning docs to `.cursor/` and `docs/`

---

## Day 2 — Base + Auth (M1, M2)

### M1 — Base Layout
- [ ] `{% load i18n %}` + convert `templates/base/base.html` (nav, sidebar, confirm modal)
- [ ] Convert `templates/base/toasts.html`
- [ ] Convert `templates/403.html`
- [ ] Wire `JavaScriptCatalog` in urls + base template
- [ ] Convert `TOAST_TITLES` in `static/adminlte/js/main.js`
- [ ] Convert `static/adminlte/js/no_emoji.js` toast messages
- [ ] Dynamic `html lang="{{ LANGUAGE_CODE }}"` in base templates

### M2 — Authentication
- [ ] Convert `templates/auth/login.html`
- [ ] Convert `templates/auth/register.html` (+ ~15 client toasts)
- [ ] Convert `templates/auth/verify.html`
- [ ] Convert `templates/auth/verify_otp.html`
- [ ] Convert `templates/auth/forgot_password.html`
- [ ] Convert `templates/auth/reset_password.html`
- [ ] Convert `templates/auth/apply.html`
- [ ] Convert `templates/auth/apply_review.html`
- [ ] Convert `templates/auth/pending_approval.html`
- [ ] Convert `templates/auth/application_pending.html`
- [ ] Wrap `accounts/view/auth.py` messages (~37)
- [ ] Refactor `accounts/utils/mailer.py` → email templates
- [ ] Run `makemessages -a` for de, es, fr

---

## Day 3 — Backend (M6, M10, M11, M12, M13)

- [ ] Wrap `messages.*` in `accounts/view/auth.py`
- [ ] Wrap `messages.*` in `accounts/view/website.py`
- [ ] Wrap `messages.*` in `accounts/view/join_request.py`
- [ ] Wrap `messages.*` in `accounts/view/partnership.py`
- [ ] Wrap `messages.*` in `accounts/view/company.py`
- [ ] Wrap `messages.*` in `accounts/view/user.py`
- [ ] Wrap `messages.*` in `accounts/view/profile.py`
- [ ] Wrap `messages.*` in `accounts/view/tenant.py`
- [ ] Wrap `messages.*` in `accounts/view/coordinator_request.py`
- [ ] Wrap `messages.*` in `accounts/view/certification.py`
- [ ] Wrap `messages.*` in `accounts/view/saved_filter.py`
- [ ] Wrap `messages.*` in `accounts/view/application_review.py`
- [ ] Wrap `messages.*` in `accounts/view/notification.py`
- [ ] Wrap `messages.*` in `accounts/view/dashboard.py`
- [ ] Wrap `messages.*` in `billing/views.py`
- [ ] Wrap `messages.*` in `FontEsin/middleware/no_emoji.py`
- [ ] Wrap all `JsonResponse` message strings (grep `"message":`)
- [ ] Wrap `accounts/forms/company_form.py` ValidationErrors (39)
- [ ] Wrap `accounts/forms/tenant_form.py` ValidationErrors (4)
- [ ] Localize `accounts/utils/notifications.py` (notify-time locale)
- [ ] DRF `Accept-Language` middleware/hook
- [ ] Wrap `accounts_api/view/companies.py`
- [ ] Wrap `accounts_api/view/profile.py`
- [ ] Wrap `accounts_api/serializers/company_serializers.py`
- [ ] Wrap `accounts/constants.py` with `gettext_lazy`
- [ ] Wrap `billing/utils.py` plan-gate errors

---

## Day 4 — Companies (M3)

- [ ] Convert `templates/dashboard/companies.html`
- [ ] Convert `templates/dashboard/_company_create_modal.html`
- [ ] Convert `templates/dashboard/_company_import_modal.html`
- [ ] Convert `templates/dashboard/_company_row.html`
- [ ] Convert `templates/dashboard/_companies_rows.html`
- [ ] Convert `templates/dashboard/_companies_pagination.html`
- [ ] Convert `templates/dashboard/my_companies.html`
- [ ] Convert `templates/dashboard/consultant_companies.html`
- [ ] Wrap `accounts/view/company.py`
- [ ] Wrap `accounts/view/company_import.py`
- [ ] Wrap `accounts_api/view/companies.py` (remaining)
- [ ] Localize CSV import error labels

---

## Day 5 — Users, Billing, Workflows (M4, M5, M7)

### M4 — Users
- [ ] Convert `templates/dashboard/users.html` + ENUMS injection
- [ ] Convert `templates/dashboard/_users_panel.html`
- [ ] Convert `templates/dashboard/consultant_users.html`
- [ ] Convert `templates/dashboard/business_users.html`
- [ ] Convert `templates/dashboard/roles.html`
- [ ] Convert `templates/dashboard/assign_roles.html`
- [ ] Convert `templates/dashboard/permissions.html`
- [ ] Wrap `accounts/view/user.py`

### M5 — Billing
- [ ] Convert `templates/dashboard/plans.html`
- [ ] Convert `templates/dashboard/subscriptions.html`
- [ ] Convert `templates/dashboard/payments.html`
- [ ] Convert `templates/dashboard/_payments_panel.html`
- [ ] Convert `templates/dashboard/commissions.html`
- [ ] Convert `templates/dashboard/_commissions_panel.html`
- [ ] Convert `templates/dashboard/_commission_invoice_modal.html`
- [ ] Convert `templates/dashboard/invoices.html`
- [ ] Convert `templates/dashboard/plan_history.html`
- [ ] Convert `templates/website/membership.html`
- [ ] Convert `templates/website/invoice.html`
- [ ] Wrap `billing/views.py` + XLSX export labels
- [ ] Implement CommercialPlan i18n strategy

### M7 — Workflows
- [ ] Convert `templates/dashboard/join_requests.html`
- [ ] Convert `templates/dashboard/partnerships.html`
- [ ] Convert `templates/dashboard/coordinator_requests.html`
- [ ] Convert `templates/dashboard/applications.html`
- [ ] Wrap `accounts/view/join_request.py`
- [ ] Wrap `accounts/view/partnership.py`
- [ ] Wrap `accounts/view/coordinator_request.py`

---

## Day 6 — Remaining (M8, M9, M12)

### M8 — Profile
- [ ] Convert `templates/profile/profile.html`
- [ ] Convert `templates/profile/_join_company_form.html`
- [ ] Convert `templates/profile/_plan_card.html`
- [ ] Wrap `accounts/view/profile.py`
- [ ] Wrap `accounts/view/saved_filter.py`
- [ ] Wrap `accounts/view/certification.py`
- [ ] Wrap `accounts_api/view/profile.py`

### Dashboard remainder
- [ ] Convert `templates/dashboard/index.html`
- [ ] Convert `templates/dashboard/search.html`
- [ ] Convert `templates/dashboard/messages.html`
- [ ] Convert `templates/dashboard/contact_messages.html`
- [ ] Convert `templates/dashboard/certifications.html`
- [ ] Convert `templates/dashboard/saved_filters.html`
- [ ] Convert `templates/dashboard/audit_logs.html`
- [ ] Convert `templates/dashboard/_audit_logs_panel.html`
- [ ] Convert `templates/dashboard/consultant_statistics.html`
- [ ] Convert `templates/dashboard/tenants.html`
- [ ] Convert `templates/dashboard/_tenants_panel.html`
- [ ] Convert `templates/dashboard/tenant_confirm_delete.html`
- [ ] Convert `templates/dashboard/regions_map.html`
- [ ] Convert all `appConfirm()` inline strings in partials

### M9 — Website
- [ ] Convert `templates/website/index.html`
- [ ] Convert `templates/website/about.html`
- [ ] Convert `templates/website/contact.html`
- [ ] Convert `templates/website/career.html`
- [ ] Convert `templates/website/worldmap.html`
- [ ] Convert `templates/website/upgrade_required.html`
- [ ] Wrap `accounts/view/website.py`
- [ ] Convert `static/manifest.json`
- [ ] Convert `static/adminlte/js/sw.js`
- [ ] Run `makemessages -a` — final sweep

---

## Day 7 — MT Fill & QA

- [ ] Machine-translate empty `msgstr` in `de`/`es`/`fr` `.po`
- [ ] `python manage.py compilemessages`
- [ ] Fix `blocktrans` interpolation errors
- [ ] Smoke test: auth flow (all 4 locales)
- [ ] Smoke test: company CRUD
- [ ] Smoke test: user management
- [ ] Smoke test: billing / subscriptions
- [ ] Smoke test: API with `Accept-Language: de`
- [ ] Grep for remaining hardcoded `showToast(`, `appConfirm(`, `"message": "`
- [ ] Generate coverage report (`msgfmt --statistics`)
- [ ] Spot-check ~50 critical `de` strings

---

## Day 8 — Rollout

- [ ] Fix regressions from Day 7
- [ ] Verify `compilemessages` in CI passes
- [ ] Performance check (no per-request file I/O)
- [ ] Update translator workflow documentation
- [ ] Release checklist + rollback plan
- [ ] Deploy to staging
- [ ] Document Week 2 human `de` review backlog

---

## Module Acceptance Criteria Quick Reference

| Module | Done when |
|--------|-----------|
| M0 | Switcher works; locale persists; EN fallback verified |
| M1 | Shared chrome + toasts translated |
| M2 | Full auth + OTP email in user locale |
| M3 | Company CRUD + import + API localized |
| M4 | User modals + ENUMS in all locales |
| M5 | Billing admin + plan cards + XLSX headers |
| M6 | New notifications in recipient locale |
| M7 | Join/partnership errors translated |
| M8 | Profile + saved filters localized |
| M9 | Website pages + dynamic `html lang` |
| M10 | API `Accept-Language` returns localized messages |
| M11 | Dropdown labels respect locale |
| M12 | Email + PWA strings localized |
| M13 | Middleware errors localized |
