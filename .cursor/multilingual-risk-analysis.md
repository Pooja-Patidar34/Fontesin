# Multilingual Risk Analysis — FONTESIN

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| AI wraps wrong strings (splits HTML tags) | Medium | High | `makemessages` + visual QA Day 7 |
| AI misses inline JS strings | High | Medium | Grep `showToast`, `appConfirm`, `alert` on Day 6 |
| `blocktrans` variable mismatches | Medium | High | Test dynamic pages Day 7 |
| MT wrong German formal tone | Medium | Medium | Spot-check auth + billing; Week 2 review |
| DB plan copy not in `.po` | High | Medium | Stable gettext keys by plan code (Day 5) |
| Deploy without `compilemessages` | Medium | Critical | CI gate Day 1 |
| Scope creep (normalize API envelopes) | Medium | Medium | Defer to post-v1 |
| Developer review bottleneck | High | Medium | AI bulk; human reviews diffs |
| Scope creep (73 templates, 3000+ strings) | High | High | Phased modules; website last |
| Existing notifications in English | Low | Low | Accept legacy; new ones localized |
| `LanguageChoices` mismatch (8 vs 4) | Medium | Medium | Narrow to 4 supported locales |
| Inline JS (`ENUMS`, `appConfirm`) | High | High | `JavaScriptCatalog` + `json_script` |
| Inconsistent API envelopes | Medium | Medium | Wrap strings only; defer normalization |
| Translator capacity for `de` | Medium | Medium | MT first; human review Week 2 |
| NACE/NAICS industry codes | Low | Low | Explicitly out of scope v1 |

---

## Technical Risks

### Middleware ordering

**Risk:** `LocaleMiddleware` in wrong position breaks session/CSRF.  
**Mitigation:** Insert immediately after `SessionMiddleware` (position 3). Test login POST after change.

### Broken template rendering

**Risk:** `{% blocktrans %}` with HTML inside breaks layout; AI may nest tags incorrectly.  
**Mitigation:** Use `{% blocktrans trimmed %}`; visual smoke test every converted template.

### Pluralization

**Risk:** German/French plural rules differ from English.  
**Mitigation:** Use `ngettext` for count-based strings; audit with `msgfmt --check`.

### Interpolation in notifications

**Risk:** f-string notification bodies lose translation context.  
**Mitigation:** Refactor to `_("...%(name)s...", name=value)` inside `translation.override(recipient_lang)`.

---

## Product Risks

### Partial localization UX

**Risk:** Users see mixed English/German on same page if migration incomplete.  
**Mitigation:** English fallback is acceptable per requirements; prioritize high-traffic paths first (auth → dashboard core → website).

### `preferred_language` legacy values

**Risk:** Users with `cs`, `ar`, `ja`, `pt` in DB get no matching locale.  
**Mitigation:** Map unknown values to `en` in middleware; migrate choices to 4 locales.

### CommercialPlan marketing copy

**Risk:** Plan cards show English features while UI is German.  
**Mitigation:** Implement gettext keys per plan code before billing PR merges.

---

## AI-Specific Risks (7–8 Day Plan)

| Risk | Mitigation |
|------|------------|
| Bulk edits introduce regressions | Small PRs per module; run Django checks after each |
| Inconsistent `msgctxt` naming | Document convention Day 1; lint in review |
| Over-translating (admin-only strings) | Skip management commands, ADRs, logs |
| Under-translating API errors | Grep `"message":` and `messages.` before Day 7 |

---

## Operational Risks

| Risk | Mitigation |
|------|------------|
| `.mo` not rebuilt on deploy | `compilemessages` in Dockerfile/CI |
| Stale translations after code change | `makemessages` in pre-commit or CI diff check |
| Performance regression | Compiled `.mo` cached by Django; no per-request JSON file reads |

---

## Out of Scope (v1) — Accepted Risks

- Czech, Arabic, Japanese, Portuguese UI
- Industry code (NACE/NAICS) localization
- Management command console output
- Celery/async notifications (not implemented)
- PDF export (not implemented)
- RTL layout
- Third-party translator SaaS
- Regional pages (`templates/regions/*`) — market-specific, may stay English
- Legacy notification rows in database
- API response envelope normalization

---

## Contingency Plans

| Scenario | Action |
|----------|--------|
| Day 7 finds >20% broken pages | Extend Day 8 buffer; defer website to Week 2 |
| `de` MT quality unacceptable | Ship with EN fallback for `de`; prioritize human review |
| Companies module not done Day 4 | Move to Day 5; defer website |
| CI `compilemessages` fails | Block merge; fix `.po` syntax before deploy |

---

## Post-Launch Follow-Up (Week 2+)

1. Human translation review for `de` (strategic market) — 3–5 days
2. `es`/`fr` pilot QA — 2 days
3. Industry codes decision — separate ADR
4. API envelope normalization — separate ticket
