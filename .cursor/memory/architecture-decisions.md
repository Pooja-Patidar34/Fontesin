# Architecture Decisions

Approved i18n architecture for FONTESIN. Do not revisit without explicit ticket.

---

## Decisions

### Django gettext

Runtime translation via Django standard gettext. Use `gettext` / `_()` in views, functions, and notify-time code. Templates use `{% trans %}` and `{% blocktrans %}`.

### gettext_lazy

`gettext_lazy as _` for module-level strings: form labels, model choice tuples, `settings.LANGUAGES` labels. Evaluated at render/validation time.

### LocaleMiddleware

Django `LocaleMiddleware` at **position 3** (immediately after `SessionMiddleware`). Handles cookie, session, and `Accept-Language`.

### UserLocaleMiddleware

Custom `FontEsin/middleware/locale.py` **after** `AuthenticationMiddleware`. Re-activates locale from cookie → `user.preferred_language` → existing activation. `normalize_locale()` maps unknown codes to `en`.

### JavaScriptCatalog

`path("jsi18n/", JavaScriptCatalog.as_view(packages=["FontEsin"]))` in `FontEsin/urls.py`. Loaded in `templates/base/base.html`. Shared JS (`main.js`, `no_emoji.js`) uses `gettext()` with English fallback.

### .po / .mo catalogs

`locale/{en,de,es,fr}/LC_MESSAGES/django.po` + `djangojs.po`. Compile to `.mo` at deploy. Do not hand-edit `.mo` files.

### English fallback

Empty `msgstr` → Django displays `msgid` (English source). Acceptable for v1.

### Language persistence strategy

Priority: `?lang=` query → language cookie (`set_language`) → `User.preferred_language` → `Accept-Language` → `en`.

### msgctxt namespacing

Logical keys: `{% trans "save" context "common" %}`, `msgctxt "auth.login"` / `msgid "title"`, `pgettext("billing.plan.{code}", …)`.

### Notifications

Translate at **write-time** with `translation.override(recipient_lang)` in `accounts/utils/notifications.py`.

### Email

Template-based bodies with `translation.override()` in `accounts/utils/mailer.py`. No inline f-string email bodies.

### DRF API

`APILocaleMixin` (`FontEsin/i18n/drf.py`) re-applies `Accept-Language` when no cookie override. Wrap `"message"` strings only — **no envelope changes**.

### CommercialPlan copy

Stable gettext keys by plan code (`billing.plan.{code}.feature.{n}`) via `billing/plan_i18n.py` + `plan_i18n_tags` — not raw DB copy in templates.

### Translation extraction workflow

Per phase: wrap source → `makemessages -l de -l es -l fr` (Linux/WSL/CI) or phase sync script (`scripts/sync_phaseN_po.py`) on Windows → `compilemessages` in CI.

### CI strategy

`.github/workflows/i18n.yml`: `django check`, `compilemessages`, `msgfmt --check` on all 4 locales. **Block merge on failure.**

---

## Do Not Change

Frozen after Phase 1–6. Fix bugs only; do not refactor.

| Area | Paths |
|------|-------|
| Settings i18n block | `FontEsin/settings.py` |
| Locale middleware | `FontEsin/middleware/locale.py` |
| i18n helpers | `FontEsin/i18n/__init__.py`, `FontEsin/i18n/drf.py` |
| i18n URLs | `FontEsin/urls.py` (`i18n/`, `jsi18n/`) |
| Language switcher | `FontEsin/templatetags/i18n_extras.py`, `templates/partials/_language_switcher.html`, `templates/partials/_auth_lang_switcher.html` |
| Supported locales | `accounts/constants.py` (`SupportedLocale`, `LanguageChoices`) |
| CI pipeline | `.github/workflows/i18n.yml`, `scripts/compile_i18n.sh` |
| Base shell | `templates/base/base.html`, `templates/base/toasts.html`, `templates/403.html`, `templates/404.html`, `templates/500.html` |
| Shared JS catalog | `static/adminlte/js/main.js` (toast section), `static/adminlte/js/no_emoji.js` |
| Middleware order | `LocaleMiddleware` pos 3; `UserLocaleMiddleware` after auth |
| API envelope shape | No normalization of DRF response structure |
| Out of scope v1 | `cs`/`ar`/`ja`/`pt` UI, `templates/regions/*`, NACE/NAICS labels, legacy DB notifications, management command stdout |
