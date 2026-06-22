# Multilingual Implementation: Challenges & 7–8 Day AI-Assisted Timeline

**Project:** FONTESIN Django Backend  
**Target locales:** `en` (default/fallback), `de`, `es`, `fr`  
**Approach:** Django gettext + AI-assisted string wrapping and machine translation

---

## Executive Summary

Full manual i18n is estimated at **15–20 developer-days** (~3,000+ hardcoded strings, zero existing infrastructure).

With **AI-assisted implementation**, **7–8 days** delivers **broad coverage (~85–90%)** — shippable v1 with MT translations and English fallback, not fully human-reviewed.

| Metric | Manual (1 dev) | AI-assisted (1 dev) |
|--------|----------------|---------------------|
| Engineering wrap | 12–14 days | 6–7 days |
| Translation fill | 3–7 days | 0.5–1 day (MT) |
| QA & rollout | 2–3 days | 1–2 days |
| **Total** | **15–20 days** | **7–8 days** |

---

## 1. Codebase Challenges

### 1.1 No existing i18n foundation

| Gap | Impact |
|-----|--------|
| No `LocaleMiddleware` | Language never switches at request level |
| No `locale/` / `.po` files | No translation catalog |
| No `{% trans %}` / `gettext` | Every string must be wrapped |
| No language switcher | Users cannot change language |
| `User.preferred_language` not wired | Profile field ignored (8 langs vs 4 required) |

### 1.2 Massive, fragmented string surface

| Surface | Volume | Difficulty |
|---------|--------|------------|
| Django templates (73 files) | 1,500–3,000+ | High |
| Django flash messages | ~131 | Medium |
| AJAX `JsonResponse` | ~200+ | Medium |
| Form `ValidationError` | ~43 | Medium |
| In-app notifications | ~60+ f-strings | High |
| Client `showToast()` / `appConfirm()` | ~80+ | High |
| DRF API messages | ~25+ | Medium |
| Choice labels | ~150+ | Medium |
| Email OTP | ~15 | Medium |
| Billing XLSX labels | ~30 | Low |
| DB plan marketing copy | ~80+ | **High** |
| Website / marketing | ~500+ | Medium |

### 1.3 Inconsistent API response shapes

- `{"status", "message", "data"}` — DRF
- `{"ok", "message"}` — AJAX
- `{"success", "message"}` — profile updates
- `{"error"}` — import, middleware

### 1.4 Inline JavaScript hotspots

| File | Issue |
|------|-------|
| `templates/dashboard/users.html` | `ENUMS` JS object (~line 1016) |
| `templates/auth/register.html` | ~15 client-side validation toasts |
| `templates/base/base.html` | `appConfirm()` defaults |
| 13+ dashboard partials | Inline `appConfirm({...})` |
| `static/adminlte/js/main.js` | `TOAST_TITLES` |

### 1.5 Dynamic / database content

| Content | Problem |
|---------|---------|
| `CommercialPlan` features/taglines | In DB, not gettext-able without schema change |
| Existing `Notification` rows | Stored in English |
| NACE/NAICS codes | Thousands of English titles — defer |
| User-generated content | Must NOT be translated |

### 1.6 Translation quality vs speed

| Locale | Priority | MT risk |
|--------|----------|---------|
| `de` | Strategic (DACH) | Formal tone — needs spot-check |
| `es` | Pilot | Generally good MT |
| `fr` | Pilot | Gender agreement — needs review |
| `en` | Source of truth | N/A |

---

## 2. How AI Assistance Changes the Equation

### What AI accelerates (2–3× faster)

| Task | Manual | AI-assisted |
|------|--------|-------------|
| Audit / inventory | 1 day | 2–3 hours |
| Wrap 73 templates | 5–6 days | 1.5–2 days |
| Wrap Python views/forms | 2–3 days | 1 day |
| Generate `de`/`es`/`fr` `.po` | 2–3 days | 2–4 hours |
| Infrastructure boilerplate | 0.5 day | 1–2 hours |

### What AI does NOT eliminate

| Task | Est. time |
|------|-----------|
| Visual regression testing | 1 day |
| Complex `blocktrans` review | 0.5 day |
| DB plan content strategy | 0.5 day |
| `ENUMS` / inline JS refactor | 0.5 day |
| German spot-check | 0.5–1 day (can be post-launch) |
| Deploy `compilemessages` | 2 hours |

---

## 3. Coverage Expectations at Day 8

| Area | Coverage | Fallback |
|------|----------|----------|
| Infrastructure & switcher | 100% | N/A |
| Auth flows | 100% | EN for MT errors |
| Dashboard (all modules) | ~90% | EN for missed strings |
| API messages | ~95% | EN |
| Notifications (new) | 100% | EN for legacy rows |
| Email OTP | 100% | EN if locale unknown |
| Website / marketing | ~85% | EN |
| Country dropdown labels | ~90% | EN |
| Industry codes (NACE) | 0% (deferred) | English |
| Translation quality `de` | MT + spot-check | EN fallback |
| Translation quality `es`/`fr` | MT pilot | EN fallback |

---

## 4. Deferred Post Day 8

- Professional human `de` review (Week 2–3)
- Industry code (NACE/NAICS) localization
- Regional landing pages (`templates/regions/*`)
- API response envelope normalization
- Legacy `Notification` rows in English
- Management command console output

---

## 5. Summary

| Question | Answer |
|----------|--------|
| Is 5 days enough? | No — MVP only (~30%) |
| Is 7–8 days enough with AI? | **Yes, for shippable v1 (~85–90%)** |
| Is 7–8 days enough without AI? | No — need 12–14 engineering days |
| Translation quality at Day 8? | MT + EN fallback; schedule human `de` review Week 2 |
| Biggest risks? | Inline JS, DB plan copy, missed strings, deploy without `compilemessages` |

**Recommended path:** Execute 7–8 day AI-assisted plan, ship with EN fallback, then 3–5 day human `de` QA sprint in Week 2.
