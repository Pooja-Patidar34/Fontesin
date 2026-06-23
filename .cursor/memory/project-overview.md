# Project Overview

**FONTESIN** — Django 6 monolith for a global business platform (company directory, RBAC, billing, partnerships).

| Item | Value |
|------|-------|
| **Memory entry point** | [onboarding.md](onboarding.md) |
| **Active work** | [current-phase.md](current-phase.md) |
| **Last updated** | 2026-06-23 (Phase 9 complete — i18n v1) |

---

## Purpose

Server-rendered dashboard + public website + DRF API for multi-tenant company management, subscriptions, join/partnership workflows, and identity onboarding.

## Tech Stack

- **Backend:** Django 6, PostgreSQL, DRF (`accounts_api`)
- **Frontend:** Django templates, AdminLTE, vanilla JS
- **i18n:** Django gettext (`.po`/`.mo`), `msgctxt` namespacing
- **Email:** MailerSend API
- **CI:** GitHub Actions (`.github/workflows/i18n.yml`)

## Architecture Summary

```
Request → LocaleMiddleware → SessionMiddleware chain → UserLocaleMiddleware
        → Views/Templates (gettext) + JavaScriptCatalog (jsi18n/)
        → locale/{en,de,es,fr}/LC_MESSAGES/{django,djangojs}.po
```

Monolith apps: `FontEsin` (project), `accounts`, `accounts_api`, `billing`.

## Current Implementation Status

| Metric | State |
|--------|-------|
| **i18n phases** | **1–9 complete** |
| **Templates converted** | ~84 / ~91 (regions excluded) |
| **Python views wrapped** | 15/23 in `accounts/view/` (+ `company_import.py`) |
| **Catalog** | 2169 `django.po` + 557 `djangojs.po` msgids per locale |
| **Translation fill** | `en`/`de`/`es`/`fr` ~100% filled |
| **`django check`** | Passes |
| **`compilemessages`** | CI-ready (GNU gettext); local via `scripts/phase9_compile_po.py` |

## Supported Languages

`en` (default + fallback), `de`, `es`, `fr`

Legacy DB codes (`cs`, `ar`, `ja`, `pt`) normalize to `en`.

## Translation Strategy

1. Wrap strings in source per phase (templates, views, forms, JS bridges).
2. Extract via `makemessages` (or phase sync scripts on Windows).
3. Defer bulk MT fill to **Phase 9**; accept EN fallback for gaps in v1.
4. Human review Tier A: auth, billing, emails, notifications (`de` formal tone).

## Important Constraints

- **Do not** change API response envelopes.
- **Do not** localize `templates/regions/*`, NACE/NAICS codes, management command output.
- **Do not** redesign locale middleware or CI after Phase 1.
- One module manifest per AI session (~5–15 files).
- Update memory files after each completed phase (not new planning docs).

## Completed Phases

| Phase | Name |
|-------|------|
| 1 | Foundation, CI & Locale Resolution |
| 2 | Shared Shell, JS Bridge & Error Pages |
| 3 | Authentication, Onboarding & Email |
| 4 | Backend Cross-Cutting: API, Notifications, Forms & Constants |
| 5 | Companies Module |
| 6 | Users, Billing & Workflows |
| 7 | Profile & Dashboard Remainder |
| 8 | Website, PWA & Final Extraction |
| 9 | MT, QA & Rollout |

## Current Phase

**None — i18n v1 complete.** See [completed-work.md](completed-work.md) Phase 9.

## Remaining Phases

None planned for i18n v1. Post-launch: human Tier A review for formal `de` (auth/billing/email).
