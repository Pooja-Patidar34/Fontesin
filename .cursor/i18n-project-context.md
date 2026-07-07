# Project Overview

FONTESIN is a Django 6 monolith (server-rendered HTML, vanilla JS, DRF API) undergoing a **gettext-based i18n rollout**.

| Item | Value |
|------|-------|
| **Execution plan** | [`.cursor/multilingual-phased-implementation-plan.md`](multilingual-phased-implementation-plan.md) (9 phases) |
| **Architecture reference** | [`.cursor/multilingual-architecture.md`](multilingual-architecture.md) |
| **Target locales** | `en` (default + fallback), `de`, `es`, `fr` |
| **Approach** | Wrap strings in source → extract `.po` per phase → MT-fill in Phase 9 → EN fallback for gaps |
| **Started** | 2026-06-23 |
| **Last updated** | 2026-06-23 (Phase 6 complete) |

**This file is the single source of truth for i18n project state.** Load it first in every Cursor session. Do not re-derive state from scratch.

---

# Current Status

| Metric | State |
|--------|-------|
| **Overall progress** | Phases **1–6 complete**; **Phase 7 next** |
| **Templates converted** | ~48 / ~91 (`{% trans %}` / `{% blocktrans %}`); **Users, Billing & Workflows complete** |
| **Python views wrapped** | 15 / 23 in `accounts/view/` (+ `company_import.py`); forms, API, billing utils/views, notifications done |
| **Catalog size** | ~730+ unique `django.po` msgctxt/msgid pairs (+ ~41 `djangojs.po` msgids from phases 1–4) |
| **Translation fill** | `en` source complete; `de`/`es`/`fr` mostly empty → **EN fallback at runtime** |
| **`django check`** | Passes (2026-06-23, post–Phase 6) |
| **`compilemessages`** | CI-ready (`.github/workflows/i18n.yml`); **fails locally on Windows** (no GNU gettext) |

---

# Completed Phases

## Phase 1 — Foundation, CI & Locale Resolution ✅

**Objective:** Runtime i18n infrastructure and deployment safety before string wrapping.

**Deliverables:**
- `LANGUAGES`, `LOCALE_PATHS`, `LANGUAGE_CODE = "en"`, i18n context processor
- `LocaleMiddleware` after `SessionMiddleware` (position 3)
- `UserLocaleMiddleware` for cookie / `preferred_language` / fallback
- `path("i18n/", include("django.conf.urls.i18n"))`
- Language switcher UI + templatetag
- `SupportedLocale` narrowed to 4 locales; `LanguageChoices` alias
- Skeleton `locale/{en,de,es,fr}/LC_MESSAGES/django.po`
- CI gate: `.github/workflows/i18n.yml`

**Files/modules affected:**
- `FontEsin/settings.py`
- `FontEsin/middleware/locale.py`
- `FontEsin/urls.py` (i18n URLs only; `jsi18n/` added in Phase 2)
- `FontEsin/templatetags/i18n_extras.py`
- `templates/partials/_language_switcher.html`
- `templates/partials/_auth_lang_switcher.html`
- `accounts/constants.py` (`SupportedLocale`, `LanguageChoices`)
- `locale/en/LC_MESSAGES/django.po` (skeleton)
- `.github/workflows/i18n.yml`
- `scripts/compile_i18n.sh`

**Validation performed:**
- `python manage.py check` — no issues
- Middleware order verified in `settings.py`
- CI workflow defines `compilemessages` + `msgfmt --check` on 4 locales

---

## Phase 2 — Shared Shell, JS Bridge & Error Pages ✅

**Objective:** Convert shared chrome and establish the JavaScript translation bridge.

**Deliverables:**
- `templates/base/base.html` — nav, sidebar, confirm modal, `html lang="{{ LANGUAGE_CODE }}"`
- Error pages: `templates/403.html`, `templates/404.html`, `templates/500.html`
- `templates/base/toasts.html` — server-rendered messages (no client wrap needed)
- `JavaScriptCatalog` at `jsi18n/` wired in `base.html`
- `static/adminlte/js/main.js` — `TOAST_TITLES` via `gettext()` with fallback
- `static/adminlte/js/no_emoji.js` — client toast strings via `gettext()`
- `djangojs.po` catalogs for JS strings
- First `makemessages` extraction for shell namespace

**Files/modules affected:**
- `templates/base/base.html`
- `templates/base/toasts.html`
- `templates/403.html`, `templates/404.html`, `templates/500.html`
- `FontEsin/urls.py` (`jsi18n/` route)
- `static/adminlte/js/main.js`
- `static/adminlte/js/no_emoji.js`
- `FontEsin/static/js/djangojs-catalog.js` (generated catalog)
- `locale/*/LC_MESSAGES/djangojs.po`

**Validation performed:**
- `JavaScriptCatalog` URL registered and referenced in `base.html`
- `gettext` guard pattern in `main.js` (`typeof gettext === 'function'`)
- Error templates use `{% trans %}` / `{% blocktrans %}`

---

## Phase 3 — Authentication, Onboarding & Email ✅

**Objective:** End-to-end localization of login → onboarding → password-reset email.

**Deliverables:**
- All auth templates wrapped with `{% trans %}` / `{% blocktrans %}`
- `accounts/view/auth.py` — flash/JSON messages wrapped with `gettext`
- `accounts/utils/mailer.py` — template-based OTP email with `translation.override(recipient_lang)`
- Email templates: `templates/email/otp_password_reset.html`, `templates/email/otp_password_reset.txt`
- Auth namespace extracted into all 4 `.po` files
- Helper scripts: `scripts/gen_phase3_translations.py`, `scripts/sync_phase3_po.py`, `scripts/fill_de_auth_mt.py`, `scripts/unfuzzy_auth_po.py`, `scripts/phase3_auth_translations.json`

**Files/modules affected:**
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
- `accounts/view/auth.py`
- `accounts/utils/mailer.py`
- `templates/email/otp_password_reset.html`
- `templates/email/otp_password_reset.txt`

**Validation performed:**
- Auth templates grep: all 10 auth pages contain `{% trans %}` or `{% blocktrans %}`
- Mailer uses `translation.override()` + `render_to_string()` (no f-string email bodies)
- Partial German MT fill attempted via `scripts/fill_de_auth_mt.py` (not full catalog)

---

## Phase 4 — Backend Cross-Cutting: API, Notifications, Forms & Constants ✅

**Objective:** Localize Python-side messages spanning multiple dashboard modules before template work.

**Deliverables:**
- `messages.*` and `JsonResponse` `"message":` strings wrapped across 14 view modules
- `accounts/forms/company_form.py`, `accounts/forms/tenant_form.py` — `gettext_lazy` validation errors
- `accounts/utils/notifications.py` — `translation.override(recipient_lang)` at notify-time
- `FontEsin/i18n/__init__.py` — `user_language()`, `activate_user_language()`
- `FontEsin/i18n/drf.py` — `APILocaleMixin` for `Accept-Language`
- `accounts_api/view/companies.py`, `accounts_api/view/profile.py` — API messages + mixin
- `accounts_api/serializers/company_serializers.py`
- `accounts/constants.py` — all choice labels via `gettext_lazy`
- `FontEsin/middleware/no_emoji.py` — user-facing rejection message
- `billing/utils.py`, `billing/views.py` — plan-gate / view messages (Python only; billing **templates** deferred to Phase 6)
- Phase 4 `.po` sync scripts: `scripts/wrap_phase4_i18n.py`, `scripts/sync_phase4_po.py`, `scripts/fix_phase4_dynamic.py`, `scripts/fix_phase4_quotes.py`, `scripts/cleanup_phase3_po.py`
- **Explicitly not done:** API response envelope normalization (deferred per risk matrix)

**Files/modules affected:**

*Views (14):*
- `accounts/view/application_review.py`
- `accounts/view/auth.py` (also Phase 3)
- `accounts/view/certification.py`
- `accounts/view/company.py`
- `accounts/view/coordinator_request.py`
- `accounts/view/dashboard.py`
- `accounts/view/join_request.py`
- `accounts/view/notification.py`
- `accounts/view/partnership.py`
- `accounts/view/profile.py`
- `accounts/view/saved_filter.py`
- `accounts/view/tenant.py`
- `accounts/view/user.py`
- `accounts/view/website.py` (view messages only; website **templates** deferred to Phase 8)

*Forms, API, infra:*
- `accounts/forms/company_form.py`
- `accounts/forms/tenant_form.py`
- `accounts/utils/notifications.py`
- `accounts/constants.py`
- `accounts_api/view/companies.py`
- `accounts_api/view/profile.py`
- `accounts_api/serializers/company_serializers.py`
- `FontEsin/i18n/__init__.py`
- `FontEsin/i18n/drf.py`
- `FontEsin/middleware/no_emoji.py`
- `billing/utils.py`
- `billing/views.py`

**Validation performed:**
- `python manage.py check` — passes
- `APILocaleMixin` applied to company + profile API views
- Phase 4 entries present in `locale/de/LC_MESSAGES/django.po` (tagged `#: phase4`, mostly `#, fuzzy` with empty `msgstr` — MT deferred to Phase 9)
- Views intentionally **not** wrapped (admin/webhook/low-traffic): `error.py`, `search.py`, `webhook.py`, `veriff.py`, `regions.py`, `contact_message.py`, `consultant.py`, `audit.py`

---

## Phase 5 — Companies Module ✅

**Objective:** Localize the Companies dashboard surface: CRUD UI, import flow, list/pagination, My Companies, consultant view.

**Deliverables:**
- All company templates wrapped with `{% trans %}` / `{% blocktrans %}` (`context "companies"` / `"companies.import"` / `"common"`)
- `window.COMPANY_I18N` JS bridge in `companies.html`, `_company_create_modal.html`, `_company_import_modal.html` — server-rendered strings + runtime `gettext()` pass
- `accounts/view/company_import.py` — import API error messages wrapped with `gettext`
- `accounts/view/company.py` — AJAX validation fallback message wrapped (missed in Phase 4)
- Phase 5 `.po` sync: `scripts/sync_phase5_po.py`, `scripts/wrap_phase5_companies_templates.py`
- **Not modified:** locale infrastructure, middleware, language switcher, auth/users/billing/website modules

**Files/modules affected:**
- `templates/dashboard/companies.html`
- `templates/dashboard/_company_create_modal.html`
- `templates/dashboard/_company_import_modal.html`
- `templates/dashboard/_company_row.html`
- `templates/dashboard/_companies_rows.html`
- `templates/dashboard/_companies_pagination.html`
- `templates/dashboard/my_companies.html`
- `templates/dashboard/consultant_companies.html`
- `accounts/view/company_import.py`
- `accounts/view/company.py` (validation message fix only)
- `scripts/sync_phase5_po.py`
- `scripts/wrap_phase5_companies_templates.py`
- `locale/{en,de,es,fr}/LC_MESSAGES/django.po` (+172 Phase 5 entries via sync script)

**Validation performed:**
- `python manage.py check` — passes
- All 6 company templates compile (`get_template`) without `TemplateSyntaxError`
- Company template grep: all 8 `templates/dashboard/*compan*` files contain `{% trans %}` or `{% blocktrans %}`
- `makemessages` — fails on Windows (no GNU gettext); entries merged via `scripts/sync_phase5_po.py`
- `compilemessages` — deferred to CI / Linux (Windows limitation unchanged)

---

## Phase 6 — Users, Billing & Workflows ✅

**Objective:** Localize users/roles UI, billing/subscription pages, join/partnership/coordinator workflows; implement `CommercialPlan` gettext keys.

**Deliverables:**
- All user management templates wrapped (`users`, roles, permissions, assign_roles, business/consultant users panels)
- `window.USER_I18N` JS bridge in `users.html`, `roles.html`, `permissions.html`, `business_users.html`, `consultant_users.html` — ENUMS labels + validation/toast strings
- `billing/plan_i18n.py` — stable `pgettext("billing.plan.{code}", …)` keys for free/basic/pro/global plan copy
- `billing/templatetags/plan_i18n_tags.py` — template filters for localized plan fields
- Billing dashboard templates wrapped; `display_*` fields on plans in `subscription_list`
- XLSX commission invoice export headers localized in `billing/views.py`
- `window.BILLING_I18N` in subscriptions, payments, commissions templates
- Workflow templates wrapped (join_requests, partnerships, coordinator_requests, applications)
- `window.WORKFLOW_I18N` in join_requests + partnerships for AJAX toasts/confirms
- `templates/profile/_plan_card.html` wrapped (required by `plans.html` include only)
- Phase 6 `.po` sync: `scripts/sync_phase6_po.py` (+453 entries per locale)

**Files/modules affected:**
- `templates/dashboard/users.html`, `_users_panel.html`, `assign_roles.html`, `roles.html`, `permissions.html`, `business_users.html`, `consultant_users.html`
- `templates/dashboard/plans.html`, `subscriptions.html`, `payments.html`, `_payments_panel.html`, `commissions.html`, `_commissions_panel.html`, `_commission_invoice_modal.html`, `invoices.html`, `plan_history.html`
- `templates/dashboard/join_requests.html`, `partnerships.html`, `coordinator_requests.html`, `applications.html`
- `templates/profile/_plan_card.html` (billing dependency only)
- `billing/plan_i18n.py`, `billing/templatetags/plan_i18n_tags.py`, `billing/views.py` (XLSX headers + `attach_plan_display_fields`)
- `scripts/sync_phase6_po.py`
- `locale/{en,de,es,fr}/LC_MESSAGES/django.po`

**Validation performed:**
- `python manage.py check` — passes
- All 21 Phase 6 templates compile (`get_template`) without `TemplateSyntaxError`
- Phase 6 template grep: all target files contain `{% trans %}` or `{% blocktrans %}`
- `scripts/sync_phase6_po.py` — +453 entries per locale (`users`, `billing`, `workflows`, `billing.plan.*` namespaces)
- `accounts/view/user.py` — already wrapped Phase 4; no changes required
- Workflow views — already wrapped Phase 4; no changes required

---

# Architecture Decisions

| Topic | Decision |
|-------|----------|
| **gettext** | Runtime translation via Django standard gettext; `gettext` in views/functions, templates via `{% trans %}` |
| **gettext_lazy** | `_()` / `gettext_lazy` for module-level strings: form labels, model choice tuples, settings `LANGUAGES` labels |
| **LocaleMiddleware** | Django `LocaleMiddleware` at position 3 (immediately after `SessionMiddleware`) |
| **UserLocaleMiddleware** | Custom middleware **after** `AuthenticationMiddleware`; re-activates locale from cookie → `user.preferred_language` → existing activation |
| **normalize_locale()** | Unknown / legacy codes (`cs`, `ar`, `ja`, `pt`, etc.) → `en` |
| **JavaScriptCatalog** | `path("jsi18n/", JavaScriptCatalog.as_view(packages=["FontEsin"]))`; loaded in `base.html`; JS uses `gettext()` with English fallback if catalog missing |
| **.po / .mo catalogs** | `locale/{en,de,es,fr}/LC_MESSAGES/django.po` + `djangojs.po`; compile to `.mo` at deploy; CI validates syntax |
| **English fallback** | Empty `msgstr` → Django displays `msgid` (English source); acceptable for v1 |
| **Supported locales** | `en`, `de`, `es`, `fr` only; `SupportedLocale.ALL` frozenset; `LanguageChoices` is backward-compatible alias |
| **Language persistence** | Priority: `?lang=` query → language cookie (`set_language` form) → `User.preferred_language` → `Accept-Language` → `en` |
| **msgctxt namespacing** | Logical keys namespaced: `{% trans "save" context "common" %}`, `msgctxt "auth.login"` / `msgid "title"` |
| **Notifications** | Translate at **write-time** with `translation.override(recipient_lang)` in `accounts/utils/notifications.py` |
| **Email** | Template-based with `translation.override()` in `mailer.py`; no inline f-string bodies |
| **DRF API** | `APILocaleMixin` re-applies `Accept-Language` when no cookie override; wrap `"message"` strings only — **no envelope changes** |
| **CommercialPlan copy** | Stable gettext keys by plan code (`billing.plan.{code}.feature.{n}`) — **required before Phase 6 billing template merge** |
| **Out of scope v1** | `cs`/`ar`/`ja`/`pt` UI, NACE/NAICS codes, API envelope normalization, `templates/regions/*`, legacy DB notifications, management command output |

---

# Completed Modules

| Module | ID | Status | Notes |
|--------|----|--------|-------|
| Infrastructure & Architecture | M0 | ✅ Complete | Settings, middleware, CI, switcher, locale dirs |
| Base Layout & Shared UI | M1 | ✅ Complete | `base.html`, toasts, error pages, JS catalog |
| Authentication & Onboarding | M2 | ✅ Complete | All auth templates + `auth.py` + OTP email |
| Notifications & Messaging | M6 | ✅ Complete | Python notify helpers only; notification **UI templates** in Phase 7 |
| REST API (accounts_api) | M10 | ✅ Complete | Companies + profile views/serializers; message strings only |
| Constants & Enums | M11 | ✅ Complete | `accounts/constants.py` choice labels |
| Middleware & Misc | M13 | ✅ Complete | `locale.py`, `no_emoji.py` user message |
| Email (OTP) | M12 | ✅ Partial | OTP password-reset only; other emails not audited |
| Companies (dashboard UI) | M3 | ✅ Complete | List, CRUD modal, import, My Companies, consultant view; `COMPANY_I18N` JS bridge |
| Users & Roles (dashboard UI) | M4 | ✅ Complete | users.html, roles/permissions, business/consultant users; `USER_I18N` JS bridge |
| Billing (dashboard UI) | M5 | ✅ Complete | plans, subscriptions, payments, commissions, invoices; `CommercialPlan` gettext keys; `BILLING_I18N` |
| Workflows (dashboard UI) | M7 | ✅ Complete | join_requests, partnerships, coordinator_requests, applications; `WORKFLOW_I18N` |

**Not yet converted (templates):** M8 Profile, M9 Website

---

# Do Not Revisit

Do **not** scan, re-wrap, or refactor these unless fixing a confirmed bug. Patterns here are the reference implementation.

## Infrastructure (Phase 1)
- `FontEsin/settings.py` (i18n block only)
- `FontEsin/middleware/locale.py`
- `FontEsin/templatetags/i18n_extras.py`
- `templates/partials/_language_switcher.html`
- `templates/partials/_auth_lang_switcher.html`
- `.github/workflows/i18n.yml`
- `scripts/compile_i18n.sh`

## Shared shell (Phase 2)
- `templates/base/base.html`
- `templates/base/toasts.html`
- `templates/403.html`, `templates/404.html`, `templates/500.html`
- `static/adminlte/js/main.js` (toast i18n section)
- `static/adminlte/js/no_emoji.js`
- `FontEsin/urls.py` (`i18n/`, `jsi18n/` routes)

## Auth & email (Phase 3)
- All `templates/auth/*.html` (10 files)
- `accounts/view/auth.py`
- `accounts/utils/mailer.py`
- `templates/email/otp_password_reset.html`
- `templates/email/otp_password_reset.txt`

## Backend cross-cutting (Phase 4)
- `FontEsin/i18n/__init__.py`, `FontEsin/i18n/drf.py`
- `accounts/forms/company_form.py`, `accounts/forms/tenant_form.py`
- `accounts/utils/notifications.py`
- `accounts/constants.py`
- `accounts_api/view/companies.py`, `accounts_api/view/profile.py`
- `accounts_api/serializers/company_serializers.py`
- `FontEsin/middleware/no_emoji.py`
- `billing/utils.py`
- These view files (Python messages only): `application_review.py`, `certification.py`, `company.py`, `coordinator_request.py`, `dashboard.py`, `join_request.py`, `notification.py`, `partnership.py`, `profile.py`, `saved_filter.py`, `tenant.py`, `user.py`, `website.py`

## Companies module (Phase 5)
- `templates/dashboard/companies.html`
- `templates/dashboard/_company_create_modal.html`
- `templates/dashboard/_company_import_modal.html`
- `templates/dashboard/_company_row.html`
- `templates/dashboard/_companies_rows.html`
- `templates/dashboard/_companies_pagination.html`
- `templates/dashboard/my_companies.html`
- `templates/dashboard/consultant_companies.html`
- `accounts/view/company_import.py`
- `scripts/sync_phase5_po.py`
- `scripts/wrap_phase5_companies_templates.py`

## Users, billing & workflows (Phase 6)
- `templates/dashboard/users.html`, `_users_panel.html`, `assign_roles.html`, `roles.html`, `permissions.html`, `business_users.html`, `consultant_users.html`
- `templates/dashboard/plans.html`, `subscriptions.html`, `payments.html`, `_payments_panel.html`, `commissions.html`, `_commissions_panel.html`, `_commission_invoice_modal.html`, `invoices.html`, `plan_history.html`
- `templates/dashboard/join_requests.html`, `partnerships.html`, `coordinator_requests.html`, `applications.html`
- `templates/profile/_plan_card.html` (billing include only)
- `billing/plan_i18n.py`, `billing/templatetags/plan_i18n_tags.py`, `billing/views.py` (Phase 6 template/XLSX work only)
- `scripts/sync_phase6_po.py`

## Planning docs (read-only reference)
- `.cursor/multilingual-phased-implementation-plan.md`
- `.cursor/multilingual-architecture.md`
- `.cursor/multilingual-task-list.md`
- `.cursor/multilingual-risk-analysis.md`

---

# Current Phase

## Phase 7 — Profile & Dashboard Remainder 🔄 NEXT

**Objectives:**
- Localize `templates/profile/*` (except `_plan_card.html` — done in Phase 6 for billing)
- Remaining dashboard templates: index, search, messages, contact_messages, certifications, saved_filters, audit_logs, consultant_statistics, tenants
- Grep `appConfirm(` gate for missed inline strings

**Target files:** See [`.cursor/multilingual-phased-implementation-plan.md`](multilingual-phased-implementation-plan.md) Phase 7 manifest.

**Exit criteria:**
- [ ] Profile pages render in `de` without layout breaks
- [ ] Dashboard remainder templates wrapped
- [ ] `python manage.py check` + `compilemessages` (CI)
- [ ] Update **this file**

**Effort estimate:** 1–1.5 days

---

# Future Phases

| Phase | Name | Scope | Depends on |
|-------|------|-------|------------|
| **8** | Website, PWA & Final Extraction | `templates/website/*` (9 files; **exclude** `templates/regions/*`), `manifest.json`, `sw.js`, `makemessages -a` | Phase 7 (deferrable if behind schedule) |
| **9** | MT, QA & Rollout | MT-fill `de`/`es`/`fr` `.po`, `compilemessages`, 4-locale smoke matrix, human `de` review backlog, staging deploy | Phases 1–8 |

### Phase 7 detail
- M8 Profile: `templates/profile/*` (except `_plan_card.html`), `profile.py` (view already wrapped)
- Dashboard remainder: index, search, messages, contact_messages, certifications, saved_filters, audit_logs, consultant_statistics, tenants

### Phase 8 detail
- Public marketing pages last; regions stay English
- Final grep sweep: `showToast(`, `appConfirm(`, `alert(`, `"message": "`

### Phase 9 detail
- MT by namespace (auth, billing, companies, …) — not whole-file at once
- Tier A human review: auth, billing, emails, notifications (`de` formal tone)
- Target: >80% non-empty `msgstr`; zero broken pages in smoke matrix

---

# Validation History

| Date | Check | Result | Notes |
|------|-------|--------|-------|
| 2026-06-23 | `python manage.py check` | ✅ Pass | No issues |
| 2026-06-23 | `python manage.py compilemessages` (Windows) | ❌ Fail | GNU gettext / `msgfmt` not installed locally |
| 2026-06-23 | CI workflow `.github/workflows/i18n.yml` | ✅ Configured | Runs on push/PR to main/master/develop |
| 2026-06-23 | Auth template grep | ✅ Pass | All 10 `templates/auth/*` use `{% trans %}` / `{% blocktrans %}` |
| 2026-06-23 | `python manage.py check` (post–Phase 5) | ✅ Pass | No issues |
| 2026-06-23 | Company template compile (`get_template`) | ✅ Pass | All 6 company templates load |
| 2026-06-23 | Company template grep | ✅ Pass | All 8 `*compan*` dashboard templates use `{% trans %}` / `{% blocktrans %}` |
| 2026-06-23 | `scripts/sync_phase5_po.py` | ✅ Pass | +172 entries per locale (`companies` / `companies.import` namespaces) |
| 2026-06-23 | `python manage.py check` (post–Phase 6) | ✅ Pass | No issues |
| 2026-06-23 | Phase 6 template compile (`get_template`) | ✅ Pass | All 21 target templates load |
| 2026-06-23 | Phase 6 template grep | ✅ Pass | All users/billing/workflow templates use `{% trans %}` / `{% blocktrans %}` |
| 2026-06-23 | `scripts/sync_phase6_po.py` | ✅ Pass | +453 entries per locale (`users`, `billing`, `workflows`, `billing.plan.*`) |
| 2026-06-23 | Dashboard template grep (non-company) | ⏳ Partial | Users/billing/workflows done; dashboard remainder — Phase 7 |
| 2026-06-23 | Website template grep | ⏳ Pending | Zero `{% trans %}` in `templates/website/**` — Phase 8 |
| 2026-06-23 | Automated i18n tests | ⏳ None | No `accounts/tests` coverage for locale yet |
| 2026-06-23 | Manual 4-locale smoke | ⏳ Not run | Deferred to Phase 9 |
| 2026-06-23 | API `Accept-Language` curl test | ⏳ Not run | `APILocaleMixin` implemented; manual verify recommended |
| 2026-06-23 | Email OTP in `de` | ⏳ Not run | Mailer refactor complete; manual verify recommended |

### Catalog statistics (2026-06-23)

| Catalog | Approx. msgids | Translation fill |
|---------|----------------|------------------|
| `locale/en/LC_MESSAGES/django.po` | ~550+ | Source locale (complete) |
| `locale/de/LC_MESSAGES/django.po` | ~550+ | Mostly empty / `#, fuzzy`; sparse manual fills (e.g. auth) |
| `locale/es/LC_MESSAGES/django.po` | ~550+ | Mostly empty |
| `locale/fr/LC_MESSAGES/django.po` | ~550+ | Mostly empty |
| `locale/*/LC_MESSAGES/djangojs.po` | ~41 each | Mostly empty |

---

# Known Issues

| Issue | Severity | Status | Action |
|-------|----------|--------|--------|
| GNU gettext not on Windows dev machine | Medium | Open | Use CI, WSL, or `choco install gettext` for local `compilemessages` |
| `de`/`es`/`fr` catalogs mostly untranslated | Expected | Deferred Phase 9 | EN fallback active; MT-fill before staging |
| Phase 4 `.po` entries all `#, fuzzy` with empty `msgstr` | Low | Deferred Phase 9 | Run `scripts/sync_phase4_po.py` + MT fill |
| `company_import.py` not wrapped | Medium | **Resolved Phase 5** | Wrapped in Phase 5 |
| Dashboard/website templates still English UI | High | Phase 7–8 | Users/billing/workflows done; profile/website remain |
| `billing/views.py` Python wrapped but billing templates not | Medium | **Resolved Phase 6** | Templates + `CommercialPlan` gettext keys done |
| `CommercialPlan` DB copy vs gettext keys | High | **Resolved Phase 6** | `billing/plan_i18n.py` + `display_*` fields |
| No automated locale regression tests | Low | Deferred | Optional post-Phase 9 |
| Pre-existing `.mo` files in repo | Low | Monitor | Regenerate via `compilemessages` on deploy; do not hand-edit `.mo` |
| German formal tone (Sie) not verified | Medium | Phase 9 | Human review Tier A strings |

### Explicitly deferred (do not implement without new ticket)
- API response envelope normalization
- `cs` / `ar` / `ja` / `pt` UI locales
- `templates/regions/*` localization
- NACE/NAICS industry code labels
- Legacy DB-stored notification text migration
- Management command stdout/stderr localization

---

# Developer Instructions

## For every future Cursor session

1. **Read this file first** — [`.cursor/i18n-project-context.md`](i18n-project-context.md)
2. **Do not redesign architecture** — follow decisions in Architecture Decisions above
3. **Do not recreate implementation plans** — use [`.cursor/multilingual-phased-implementation-plan.md`](multilingual-phased-implementation-plan.md) for phase manifests only
4. **Do not re-analyze completed phases** — trust Completed Phases + Do Not Revisit lists
5. **Do not scan unrelated modules** — load only the current phase target files (~5–15 files)
6. **Continue from Current Phase** — do not skip ahead or revisit completed work
7. **Use completed files as exemplars** — e.g. `templates/auth/login.html` for templates, `accounts/view/auth.py` for views

## Wrapping conventions (quick reference)

```django
{% load i18n %}
{% trans "Save" context "common" %}
{% blocktrans trimmed with name=user.name %}Hello, {{ name }}!{% endblocktrans %}
```

```python
from django.utils.translation import gettext as _           # runtime
from django.utils.translation import gettext_lazy as _     # module-level
```

```javascript
(typeof gettext === 'function') ? gettext('Error') : 'Error'
```

## Per-phase workflow

1. Read **Current Phase** section in this file
2. Convert only listed target files
3. Run phase grep gate (not full-repo scan)
4. `python manage.py makemessages -l de -l es -l fr` (Linux/macOS/WSL with gettext)
5. `python manage.py check`
6. Visual smoke in `en` + `de`
7. **Update this file** (Maintenance Protocol)

## Maintenance Protocol — update after every completed phase

When a phase is completed, update these sections in **this file**:

1. **Current Status** — progress %, catalog stats, validation results
2. **Completed Phases** — add new section with objective, deliverables, files, validation
3. **Completed Modules** — mark module ✅
4. **Do Not Revisit** — append newly finished files
5. **Current Phase** — advance to next phase number with new objectives/targets/exit criteria
6. **Future Phases** — remove completed entry from table (or mark done)
7. **Validation History** — add dated rows for checks run
8. **Known Issues** — resolve or add items discovered during the phase
9. **Last updated** date at top of file

**Checkpoint command block (run where gettext is available):**

```bash
python manage.py check
python manage.py makemessages -l de -l es -l fr --ignore=venv
python manage.py compilemessages
msgfmt --statistics locale/de/LC_MESSAGES/django.po
msgfmt --check -o /dev/null locale/de/LC_MESSAGES/django.po
```

---

*End of i18n project context. Next action: **Phase 7 — Profile & Dashboard Remainder**.*
