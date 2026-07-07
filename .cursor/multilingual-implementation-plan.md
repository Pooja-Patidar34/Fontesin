# Multilingual (i18n) Implementation Plan — FONTESIN

**Target locales:** `en` (default + fallback), `de`, `es`, `fr`  
**Primary timeline:** 7–8 days with AI-assisted implementation  
**Runtime:** Django gettext (`.po`/`.mo`) with `msgctxt` key namespacing

---

## Executive Summary

FONTESIN is a **Django 6 monolith** with server-rendered HTML (73 templates), vanilla JS, and a DRF REST API. There is **no existing i18n implementation** despite `USE_I18N = True`.

| Approach | Duration | Coverage |
|----------|----------|----------|
| Manual, 1 dev | 15–20 days | Full, production-ready |
| Manual, 2 devs | 10–12 days | Full, production-ready |
| **AI-assisted, 1 dev** | **7–8 days** | **~85–90% wrapped; MT translations; EN fallback** |
| 5-day MVP only | 5 days | ~30% (auth + shell + 1 module) |

**Current state:** ~100% hardcoded English. Zero `gettext`, zero `{% trans %}`, no `LocaleMiddleware`, no language switcher. `User.preferred_language` exists but is not wired to locale activation.

---

## 7–8 Day AI-Assisted Roadmap

### Day 1 — Audit, Architecture & Infrastructure

- Configure `LANGUAGES`, `LOCALE_PATHS`, `LocaleMiddleware`, custom user-locale middleware
- Language switcher partial + `set_language` URL
- `locale/en/LC_MESSAGES/django.po` skeleton (namespaces: common, auth, dashboard, billing, notifications, api, email, errors)
- Align `LanguageChoices` to 4 supported locales
- Add `compilemessages` to CI/deploy checklist
- Save planning docs to `.cursor/` and `docs/`

**Exit criteria:** Language switch persists in session; `translation.activate('de')` works.

---

### Day 2 — Base Layout, Shared JS & Auth

- Convert `templates/base/base.html` (nav, sidebar, confirm modal)
- Convert `toasts.html`, `403.html`, `main.js`, `no_emoji.js` + `JavaScriptCatalog`
- Convert all 12 `templates/auth/*` files
- Wrap `accounts/view/auth.py` messages (~37)
- Refactor `mailer.py` → email templates with `{% trans %}`
- Seed empty `de`/`es`/`fr` `.po` files via `makemessages`

**Exit criteria:** Full auth flow works in 4 locales.

---

### Day 3 — Backend Python, API & Notifications

- Wrap all `messages.*` calls across 16 view files
- Wrap all `JsonResponse` message strings
- Wrap `company_form.py` + `tenant_form.py` validation (43 errors)
- Localize `accounts/utils/notifications.py` (translate at notify-time)
- DRF `Accept-Language` activation + wrap `accounts_api/` messages
- Wrap `accounts/constants.py` choice labels
- Middleware errors (`no_emoji.py`, `billing/utils.py`)

**Exit criteria:** API returns localized `message` with `Accept-Language: de`.

---

### Day 4 — Companies Module

- `templates/dashboard/companies.html` + modals (`_company_*`)
- `accounts/view/company.py`, `company_import.py`
- `accounts_api/view/companies.py` + serializer
- Inline `showToast` / `appConfirm` in company templates
- CSV import error labels

**Exit criteria:** Company CRUD, import, and API gating messages localized.

---

### Day 5 — Users, Billing & Workflows

- `users.html` + `_users_panel.html` + `ENUMS` JS injection
- `accounts/view/user.py` (68 JsonResponse messages)
- Roles, permissions, assign_roles templates
- Billing templates + `billing/views.py` + XLSX export labels
- `CommercialPlan` i18n strategy (gettext keys by plan code)
- Join requests, partnerships, coordinator views

**Exit criteria:** User management and billing admin usable in 4 locales.

---

### Day 6 — Remaining Dashboard, Profile & Website

- Profile templates + views
- Certifications, saved filters, contact messages, audit logs
- All remaining dashboard templates (~15 files)
- Website pages (`templates/website/*`) — 9 files
- PWA `manifest.json`, `sw.js`
- Run `makemessages -a` — catch missed strings

**Exit criteria:** All templates wrapped; untranslated keys fall back to English.

---

### Day 7 — Machine Translation, Regression & Gap Fill

- MT-fill empty `msgstr` in `de`/`es`/`fr` `.po` files
- `compilemessages` + verify no broken interpolations
- Manual smoke test: auth, companies, users, billing, API
- Fix `blocktrans` variable mismatches
- Coverage report: `msgfmt --statistics` per locale
- Spot-check ~50 critical `de` strings

**Exit criteria:** >80% of keys have non-empty `msgstr`; zero broken pages.

---

### Day 8 — Buffer, Documentation & Rollout

- Fix regressions from Day 7
- Performance check (`.mo` file loading)
- Update translator workflow docs
- Release checklist: CI, deploy, smoke tests
- Schedule Week 2 human `de` review (optional)

**Exit criteria:** Deployed to staging; rollback documented.

---

## PR Boundaries (Suggested)

| PR | Day | Scope |
|----|-----|-------|
| PR-1 | 1 | Infrastructure only (settings, middleware, switcher, locale/) |
| PR-2 | 2 | Base layout + auth templates + email templates |
| PR-3 | 3 | Backend Python + API + notifications + constants |
| PR-4 | 4 | Companies module |
| PR-5 | 5 | Users + billing + join/partnership |
| PR-6 | 6 | Remaining dashboard + website + PWA |
| PR-7 | 7–8 | MT fill, fixes, docs, CI |

---

## Module Index (M0–M13)

| Module | Name | Effort |
|--------|------|--------|
| M0 | Infrastructure & Architecture | 1 day |
| M1 | Base Layout & Shared UI | 0.5 day |
| M2 | Authentication & Onboarding | 1 day |
| M3 | Companies & Import | 1.5 days |
| M4 | Users & Roles | 1 day |
| M5 | Billing & Subscriptions | 1 day |
| M6 | Notifications & Messaging | 0.75 day |
| M7 | Join Requests, Partnerships, Coordinator | 0.75 day |
| M8 | Profile & Settings | 0.5 day |
| M9 | Website & Regional Pages | 1 day |
| M10 | REST API (accounts_api) | 0.5 day |
| M11 | Constants & Enums | 0.5 day |
| M12 | Email & PWA | 0.25 day |
| M13 | Middleware & Misc | 0.25 day |

See `.cursor/multilingual-task-list.md` for checkbox tasks and `.cursor/multilingual-architecture.md` for technical details.

---

## Success Criteria (Day 8)

- [ ] Language switcher on dashboard and website
- [ ] Session + `preferred_language` drive locale selection
- [ ] English fallback for all missing translations
- [ ] Auth, companies, users, billing, notifications, API covered
- [ ] `de`/`es`/`fr` `.po` files populated (MT acceptable)
- [ ] `compilemessages` runs in CI
- [ ] No broken template rendering (smoke test passed)
- [ ] Phase 2 human QA backlog documented for `de`

---

## Related Documents

- [`.cursor/multilingual-phased-implementation-plan.md`](multilingual-phased-implementation-plan.md) — **Risk-driven 9-phase delivery roadmap** (primary execution plan)
- [`.cursor/multilingual-architecture.md`](multilingual-architecture.md) — Technical design
- [`.cursor/multilingual-task-list.md`](multilingual-task-list.md) — Checkbox task list
- [`.cursor/multilingual-risk-analysis.md`](multilingual-risk-analysis.md) — Risks and mitigations
- [`.cursor/multilingual-ai-accelerated-timeline.md`](multilingual-ai-accelerated-timeline.md) — Challenges and feasibility analysis
