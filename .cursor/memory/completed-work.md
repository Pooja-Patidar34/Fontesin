# Completed Work

Phase history — summarized. Full detail in legacy doc: `.cursor/i18n-project-context.md`.

---

## Phase 1 — Foundation, CI & Locale Resolution

**Scope:** Runtime i18n infrastructure before string wrapping.

**Modules touched:** M0 Infrastructure

**Key deliverables:**
- `LANGUAGES`, `LOCALE_PATHS`, i18n context processor
- `LocaleMiddleware` (pos 3) + `UserLocaleMiddleware`
- Language switcher + `i18n/` URLs
- `SupportedLocale` narrowed to 4 locales
- Skeleton `locale/*/LC_MESSAGES/django.po`
- CI: `.github/workflows/i18n.yml`

**Validation:** `django check` pass; middleware order verified; CI defines `compilemessages` + `msgfmt --check`

---

## Phase 2 — Shared Shell, JS Bridge & Error Pages

**Scope:** Shared chrome + JavaScript translation bridge.

**Modules touched:** M1 Base Layout

**Key deliverables:**
- `base.html`, toasts, 403/404/500 error pages
- `JavaScriptCatalog` at `jsi18n/`
- `main.js` TOAST_TITLES, `no_emoji.js` via `gettext()`
- `djangojs.po` catalogs

**Validation:** `gettext` guard in JS; error templates use `{% trans %}`

---

## Phase 3 — Authentication, Onboarding & Email

**Scope:** Login → onboarding → password-reset email end-to-end.

**Modules touched:** M2 Auth, partial M12 Email

**Key deliverables:**
- 10 auth templates wrapped
- `accounts/view/auth.py` messages
- `mailer.py` + OTP email templates with `translation.override()`
- Auth namespace in all 4 `.po` files

**Validation:** All auth templates contain `{% trans %}` / `{% blocktrans %}`; mailer uses template render

---

## Phase 4 — Backend Cross-Cutting

**Scope:** Python messages spanning multiple modules before template work.

**Modules touched:** M6 Notifications, M10 API, M11 Constants, M13 Middleware

**Key deliverables:**
- 14 view modules: `messages.*` and `JsonResponse` wrapped
- Forms: `company_form.py`, `tenant_form.py` (`gettext_lazy`)
- `notifications.py` write-time override
- `APILocaleMixin` + companies/profile API
- `accounts/constants.py` choice labels
- `billing/utils.py`, `no_emoji.py` messages

**Validation:** `django check` pass; API mixin applied; API envelope unchanged

---

## Phase 5 — Companies Module

**Scope:** Company CRUD, import, list/pagination UI.

**Modules touched:** M3 Companies

**Key deliverables:**
- 8 company dashboard templates wrapped
- `window.COMPANY_I18N` JS bridge
- `company_import.py` + validation fix in `company.py`
- +172 `.po` entries via `scripts/sync_phase5_po.py`

**Validation:** All `*compan*` templates wrapped; templates compile; `django check` pass

---

## Phase 6 — Users, Billing & Workflows

**Scope:** RBAC UI, billing/subscriptions, join/partnership workflows.

**Modules touched:** M4 Users, M5 Billing, M7 Workflows

**Key deliverables:**
- 21 templates: users, roles, billing, workflows
- `USER_I18N`, `BILLING_I18N`, `WORKFLOW_I18N` bridges
- `billing/plan_i18n.py` + `plan_i18n_tags`
- XLSX export headers localized
- +453 `.po` entries via `scripts/sync_phase6_po.py`

**Validation:** All Phase 6 templates wrapped and compile; `django check` pass

---

## Phase 7 — Profile & Dashboard Remainder

**Scope:** Profile pages and remaining authenticated dashboard surfaces.

**Templates updated:**
- `templates/profile/profile.html`
- `templates/profile/_join_company_form.html`
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

**JS bridges:** `PROFILE_I18N`, `DASHBOARD_I18N` (index, certifications, consultant statistics, regions map)

**Scripts:** `scripts/sync_phase7_po.py`, `scripts/wrap_phase7_index.py`, `scripts/wrap_phase7_remaining.py`, `scripts/fix_profile_phase7.py`

**Verified (no changes):** `accounts/view/profile.py`, `accounts/view/saved_filter.py`, `accounts/view/certification.py`; `accounts/forms/certificate_form.py` has no user-facing certificate errors (RoleForm only)

**Validation:** All Phase 7 templates wrapped; `appConfirm(` grep clean in scope; `python manage.py check` pass; +322 `.po` entries via `scripts/sync_phase7_po.py`

---

## Phase 8 — Website, PWA & Final Extraction

**Scope:** Public website templates, PWA assets, final string extraction before MT fill.

**Modules touched:** M9 Website, M12 PWA remainder

**Templates updated:**
- `templates/website/index.html`
- `templates/website/about.html`
- `templates/website/contact.html`
- `templates/website/career.html`
- `templates/website/worldmap.html`
- `templates/website/_world_map.html`
- `templates/website/upgrade_required.html`
- `templates/website/membership.html`
- `templates/website/invoice.html`

**PWA / static:**
- `static/adminlte/manifest.json` (created)
- `static/adminlte/js/sw.js` (`PWA_STRINGS` + `postMessage` bridge)

**Views:** `accounts/view/website.py` — `comparison_rows` labels wrapped with `gettext`

**JS bridges:** `WEBSITE_I18N` (contact, career, membership, invoice), `WEBSITE_MAP_I18N` (`_world_map.html`), `PWA_I18N` (all website pages)

**Scripts:** `scripts/wrap_phase8_website.py`, `scripts/sync_phase8_po.py`

**Gap-fix (final pass):** Region/plan cards on `index.html`, contact form placeholders/address/map strings, team `alt` texts on `about.html`, supplier address on `invoice.html`

**Validation:** All 9 website templates compile; Phase 8 grep gate clean; `python manage.py check` pass; 517 unique Phase 8 pairs via `scripts/sync_phase8_po.py` (+29 final-pass entries in all 4 locale catalogs)

---

## Phase 9 — MT, QA & Rollout

**Scope:** MT-fill `de`/`es`/`fr` catalogs, validate, compile, 4-locale smoke QA.

**Scripts added:**
- `scripts/phase9_fill_po.py` — batch MT fill with placeholder preservation + cache
- `scripts/phase9_validate_po.py` — interpolation + empty-msgstr audit
- `scripts/phase9_compile_po.py` — polib `.mo` compile (Windows-safe)
- `scripts/phase9_po_stats.py` — coverage statistics
- `scripts/phase9_qa.py` — django check, catalog load, template compile
- `scripts/phase9_unfuzzy_po.py` — remove fuzzy flags from filled entries

**Catalog coverage (final):**
- `django.po`: 2169 entries × 4 locales — ~100% filled
- `djangojs.po`: 557 entries × 4 locales — 100% filled

**Regression fixes:**
- `es` plural partnership banner (`%(counter)s`)
- `fr` workflow strings — restored `{{ companies_url }}` / `{{ profile_url }}` placeholders

**Validation:** `phase9_validate_po.py` PASS; `phase9_compile_po.py` PASS (8 catalogs); `phase9_qa.py` PASS; `django check` PASS; key strings verified in `de`/`es`/`fr` via `pgettext`
