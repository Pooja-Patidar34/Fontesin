# Internationalization (i18n) Developer Guide

This guide explains how multilingual support is implemented in the FontEsin Django backend and how to maintain and extend it as the application grows.

**Table of contents**

| Section | Topic |
|---------|-------|
| [1. Overview](#1-overview) | Architecture, supported languages, locale resolution |
| [2. Project Structure](#2-project-structure) | `locale/`, `.po` / `.mo` files, related project files |
| [3. How Translation Works](#3-how-translation-works) | Python, templates, forms, API, notifications |
| [4. Adding New Translatable Content](#4-adding-new-translatable-content) | Step-by-step workflow for new strings |
| [Translation Workflow](#translation-workflow) | Visual summary of the end-to-end process |
| [5. Commands](#5-commands) | `makemessages`, `compilemessages`, validation |
| [6. Adding a New Language](#6-adding-a-new-language) | Extending beyond the four current locales |
| [7. Best Practices](#7-best-practices) | Conventions and patterns to follow |
| [Common Mistakes](#common-mistakes) | Frequent pitfalls and how to avoid them |
| [8. Future Development Workflow](#8-future-development-workflow) | Definition of done per change type |
| [9. Troubleshooting](#9-troubleshooting) | Diagnosing missing or stale translations |
| [10. Maintenance Checklist](#10-maintenance-checklist) | Pre-merge checklist |
| [Code Review Checklist](#code-review-checklist) | What reviewers should verify on every PR |
| [Deployment Notes](#deployment-notes) | Production build and release requirements |
| [Performance Notes](#performance-notes) | Runtime behavior and catalog loading |
| [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq) | Quick answers to common questions |
| [11. Current Implementation Status](#11-current-implementation-status) | What is already in place |
| [Quick reference](#quick-reference) | Copy-paste snippets |

---

## 1. Overview

FontEsin uses **Django's built-in Internationalization (i18n) framework** together with GNU gettext. User-facing strings are marked as translatable in Python, templates, and JavaScript; translations are stored in `.po` files under `locale/` and compiled to binary `.mo` files at deploy time.

**English (`en`)** is the default language and the fallback when a translation is missing or an unsupported locale is requested.

### Currently supported languages

| Code | Language |
|------|----------|
| `en` | English |
| `de` | German |
| `fr` | French |
| `es` | Spanish |

These are declared in `FontEsin/settings.py` (`LANGUAGES`) and mirrored in `accounts.constants.SupportedLocale`. Both must stay in sync when adding or removing a language. See also [Adding a New Language](#6-adding-a-new-language) and [FAQ — How do I add a new language?](#how-do-i-add-a-new-language).

### Key configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `LANGUAGE_CODE` | `"en"` | Default source language |
| `USE_I18N` | `True` | Enables translation machinery |
| `LOCALE_PATHS` | `[BASE_DIR / "locale"]` | Project-level translation files |

### Locale resolution

Requests pass through two middleware layers:

1. **`django.middleware.locale.LocaleMiddleware`** — standard Django locale detection.
2. **`FontEsin.middleware.locale.UserLocaleMiddleware`** — project-specific resolution:
   - Authenticated users: `?lang=` query param → `user.preferred_language` → English fallback.
   - Anonymous users: `?lang=` → session → `django_language` cookie → English fallback.

Language changes are submitted via the header language switcher to `/i18n/setlang/`, which uses a custom `set_language` view that also persists the choice on the user profile when logged in.

---

## 2. Project Structure

```
locale/
├── en/
│   └── LC_MESSAGES/
│       ├── django.po      # Python + template strings
│       ├── django.mo      # Compiled django catalog
│       ├── djangojs.po    # JavaScript strings
│       └── djangojs.mo    # Compiled JS catalog
├── de/
│   └── LC_MESSAGES/
│       └── …
├── es/
│   └── LC_MESSAGES/
│       └── …
└── fr/
    └── LC_MESSAGES/
        └── …
```

### `.po` files (Portable Object)

Human-editable translation catalogs. Each entry pairs:

- **`msgid`** — the source string (English).
- **`msgstr`** — the translated string for that locale.
- **`msgctxt`** (optional) — disambiguates identical English words in different contexts (e.g. `"Status"` on a company row vs. a user profile).

For English (`en`), `msgstr` typically equals `msgid`. Other locales must provide real translations.

### `.mo` files (Machine Object)

Binary files produced by `compilemessages`. Django loads these at runtime. **Never edit `.mo` files by hand** — always edit `.po` files and recompile. See [Performance Notes](#performance-notes) for how Django uses `.mo` files in production.

### Two gettext domains

| Domain | Catalog file | Covers |
|--------|--------------|--------|
| `django` (default) | `django.po` / `django.mo` | Python code, Django templates, forms |
| `djangojs` | `djangojs.po` / `djangojs.mo` | Client-side JavaScript via `gettext()` |

JavaScript strings are anchored in `FontEsin/static/js/djangojs-catalog.js` so `makemessages -d djangojs` can extract them. The runtime catalog is served at `/jsi18n/` via Django's `JavaScriptCatalog`.

### Related project files

| Path | Role |
|------|------|
| `FontEsin/settings.py` | `LANGUAGES`, `LOCALE_PATHS`, `USE_I18N` |
| `accounts/constants.py` | `SupportedLocale` — canonical list of locale codes |
| `FontEsin/middleware/locale.py` | Per-request locale activation |
| `FontEsin/i18n/views.py` | Custom `set_language` with profile persistence |
| `FontEsin/i18n/drf.py` | `APILocaleMixin` for REST API responses |
| `FontEsin/i18n/__init__.py` | `user_language()`, `activate_user_language()` |
| `FontEsin/templatetags/i18n_extras.py` | `{% language_switcher %}` inclusion tag |
| `billing/plan_i18n.py` | `pgettext()` helpers for plan marketing copy |
| `templates/partials/_language_switcher.html` | Header language dropdown |
| `.github/workflows/i18n.yml` | CI validation of catalogs |
| `scripts/compile_i18n.sh` | Deploy helper to compile messages |

---

## 3. How Translation Works

### Python — `gettext` and `gettext_lazy`

Use **`gettext_lazy` (`_`)** for strings evaluated at import time (model fields, form labels, `Meta` classes, settings):

```python
from django.utils.translation import gettext_lazy as _

class MyForm(forms.Form):
    name = forms.CharField(label=_("Full name"))
```

Use **`gettext`** for strings evaluated at request time (views, notifications, runtime errors):

```python
from django.utils.translation import gettext as _

def my_view(request):
    messages.success(request, _("Profile updated successfully."))
```

Use **`pgettext`** when the same English word appears in different contexts (billing plan copy uses this pattern):

```python
from django.utils.translation import pgettext

label = pgettext("billing.plan.pro", "PRO")
```

Use **`translation.override`** when generating content for a specific user in their language (notifications, emails):

```python
from django.utils import translation
from FontEsin.i18n import user_language

with translation.override(user_language(recipient)):
    title = _("You earned a commission of %(amount)s") % {"amount": amount}
```

See [FAQ — When should I use `gettext_lazy`?](#when-should-i-use-gettext_lazy) and [Common Mistakes](#common-mistakes) for guidance on choosing the right function.

### Django templates — `{% trans %}` and `{% blocktrans %}`

Load the i18n library at the top of every translatable template:

```django
{% load i18n %}
```

**Simple strings** — use `{% trans %}` with an optional `context` for disambiguation:

```django
{% trans "Save" context "common" %}
{% trans "Company" context "companies" %}
```

**Strings with variables** — use `{% blocktrans %}`:

```django
{% blocktrans trimmed with count=page_obj.paginator.count context "companies" %}
Total: {{ count }}
{% endblocktrans %}
```

The base layout sets `<html lang="{{ LANGUAGE_CODE }}">` and includes the JavaScript catalog:

```django
{% load static i18n i18n_extras %}
<script src="{% url 'javascript-catalog' %}"></script>
```

Render the language switcher with:

```django
{% language_switcher %}
```

See [FAQ — When should I use `blocktrans`?](#when-should-i-use-blocktrans) for more examples.

### Forms

- Wrap **field labels**, **help text**, and **placeholders** with `_()`.
- Raise **`ValidationError`** with translated messages in `clean_*` methods.

Example from `accounts/forms/tenant_form.py`:

```python
from django.utils.translation import gettext_lazy as _

def clean_name(self):
    name = (self.cleaned_data.get("name") or "").strip()
    if len(name) < 2:
        raise forms.ValidationError(_("Tenant name must be at least 2 characters."))
    return name
```

Model choice labels in `accounts/constants.py` use `_()` on the display half of each tuple while keeping the stored value as a stable English identifier:

```python
CHOICES = [
    (MANUFACTURING, _("Manufacturing")),  # "manufacturing" stored in DB; label translated at display
]
```

### Validation messages

Server-side validation messages must use `_()` or `gettext()`. Client-side validation in JavaScript must use `gettext()` and have matching entries in `djangojs.po`:

```javascript
var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
var LABEL_ACTIVE = g("Active");
```

### Admin

Django's stock admin URLs are currently disabled in this project. The custom admin panel is built from templates under `templates/` and follows the same `{% trans %}` / `{% blocktrans %}` patterns as the rest of the UI. If stock Django admin is re-enabled, its built-in strings are translated through Django's own locale packages; any custom `ModelAdmin` labels should still use `_()`.

### REST API

API views that return user-facing `message` or `error` fields should inherit **`APILocaleMixin`** so unauthenticated clients sending `Accept-Language` receive translated responses:

```python
from FontEsin.i18n.drf import APILocaleMixin

class CompanyListAPIView(APILocaleMixin, APIView):
    ...
```

Wrap API error strings with `gettext` at the point they are returned.

### Notifications

Notifications are stored in the database and read back long after they were written, possibly after the recipient has switched language. Translating them once at write time froze them in the old language, so they are stored as **ingredients rather than finished sentences**: the msgid, its context, and its interpolation parameters, re-rendered through `gettext` on every read.

Compose them with `Msg` / `MsgSeq` from `accounts/utils/i18n_messages.py` and hand those to `notify()`:

```python
from accounts.utils.i18n_messages import Msg, MsgSeq
from accounts.utils.notifications import notify

body = MsgSeq(Msg("%(name)s has requested a %(level)s and is awaiting your review.",
                  name=applicant_label, level=level_label))
if territory:
    body.line(Msg("Territory: %(territory)s.", territory=territory))

notify(recipient=reviewer,
       title=Msg("New %(level)s request", level=level_label),
       body=body)
```

- **`Msg(msgid, ctx=None, **params)`** — one translatable sentence. Parameters may be plain strings (names, amounts, company names — never translated), other `Msg` objects, `MsgSeq` sequences, or `gettext_lazy` proxies from `accounts/constants.py`, whose msgid is recovered so choice labels (franchise level, country) translate too.
- **`MsgSeq`** — an ordered run: `.add(x)` appends directly, `.line(x)` on a new line, `.blank_line(x)` after a blank line.
- **Never `str()` a lazy label before passing it in** — that freezes it at the acting user's request locale.

`notify()` also writes the rendered text into the plain `title` / `body` columns, in the recipient's preferred language, as the fallback for rows that predate this mechanism. Templates must read **`note.display_title`** and **`note.display_body`**, never `note.title` / `note.body`.

Emails are still translated at send time with `translation.override(user_language(recipient))` — they are delivered once and never re-read from the database. See [FAQ — How do I translate emails and notifications?](#how-do-i-translate-emails-and-notifications).

#### Extraction

`xgettext` does not know `Msg()` is a translation call and Django's `makemessages` has no flag to add a keyword, so `scripts/i18n_refresh.py` runs a **second extraction pass** (`xgettext --keyword=Msg:1`) over the project's Python files and merges the result into the POT. A bare `manage.py makemessages` therefore misses every notification string — always refresh via the script.

### Billing plan copy

Plan names, taglines, and feature lists use `pgettext` with contexts like `billing.plan.pro`. Helpers live in `billing/plan_i18n.py`. When changing plan marketing text, update the canonical English in that module and re-run message extraction.

---

## 4. Adding New Translatable Content

Follow this workflow whenever you introduce user-facing text. A visual summary is in [Translation Workflow](#translation-workflow).

### Step 1 — Wrap strings with translation functions

| Location | Mechanism |
|----------|-----------|
| Python (module-level) | `gettext_lazy as _` |
| Python (request-time) | `gettext as _` |
| Templates | `{% trans %}` / `{% blocktrans %}` |
| JavaScript | `gettext('…')` in `djangojs-catalog.js` or inline with catalog loaded |

Add `context "…"` in templates (or `pgettext` in Python) when the same English word means different things in different screens.

### Step 2 — Extract new strings

From the project root (requires GNU gettext tools installed):

```bash
# Python + templates (django domain)
python manage.py makemessages -a

# JavaScript strings (djangojs domain)
python manage.py makemessages -a -d djangojs
```

This updates `locale/<lang>/LC_MESSAGES/django.po` and `djangojs.po` with new `msgid` entries and file references.

#### On Windows, `makemessages` silently updates nothing

Windows extraction writes a POT whose wrapped `#:` reference comments lose their
`#:` prefix on continuation lines. `msguniq` then aborts with `syntax error` and
**no `.po` file is touched** — the command fails after the strings were already
extracted, so it is easy to believe the catalogs were refreshed when they were
not. This is what left the whole Franchise section (and other newer screens)
marked translatable in the templates but English in the UI.

Use the wrapper instead of a bare `makemessages` on Windows:

```bash
python scripts/i18n_refresh.py          # extract, repair the POT, merge into de/es/fr/en
python scripts/i18n_refresh.py --stats  # just report untranslated / fuzzy counts
```

New entries are merged with `--no-fuzzy-matching` on purpose: msgmerge's guesses
for this codebase were wrong more often than right (it paired *Master Franchise*
with *Save Franchise*), and a confidently wrong translation is worse than an
empty one.

`i18n_refresh.py` covers the `django` domain only. The `djangojs` catalogs are
maintained by hand because most of their entries have no extractable source, so
regenerating them with `--no-obsolete` would delete them.

The script also runs a second `xgettext --keyword=Msg:1` pass so notification
strings written as `Msg("…")` are extracted — `makemessages` alone never sees
them. See [Notifications](#notifications).

#### Escaped quotes break extraction

`{% trans "… \"Memo\" …" %}` renders correctly but `templatize()` truncates the
msgid at the escaped quote, so the string can never match a catalog entry and
stays English forever. Use typographic quotes (`“ ”`) inside translatable
literals instead.

### Step 3 — Translate new entries

Open each non-English `.po` file (`de`, `es`, `fr`) and fill in `msgstr` for every new `msgid`. Leave `msgstr ""` only for strings you intentionally defer.

For a large batch, put the reviewed strings in `scripts/i18n_translations.json`
(`{ctx, id, plural, de, es, fr}` per entry, written exactly as they appear inside
the `.po` quotes) and let the filler apply them — it emits a supplement catalog
and folds it in with `msgcat`/`msgmerge`, so quoting, wrapping and plural layout
stay gettext's problem rather than yours. It also replaces `fuzzy` entries, which
gettext ignores at runtime and which therefore show as English:

```bash
python scripts/i18n_fill.py           # fill de/es/fr from the map, then en from msgid
python scripts/i18n_fill.py --check   # list untranslated entries with no mapping
```

Example:

```po
#: templates/dashboard/example.html
msgctxt "common"
msgid "Export"
msgstr "Exportieren"
```

For `msgctxt` entries, translate under the `msgctxt` block:

```po
msgctxt "common"
msgid "Export"
msgstr "Exportieren"
```

Keep all four locale files synchronized — every `msgid` present in `en` should have a corresponding entry in `de`, `es`, and `fr`.

### Step 4 — Compile catalogs

```bash
python manage.py compilemessages
```

Or use the deploy script:

```bash
bash scripts/compile_i18n.sh
```

See [Deployment Notes](#deployment-notes) for production requirements.

### Step 5 — Verify in the UI

1. Start the dev server.
2. Switch language via the header globe icon (or `?lang=de`, `?lang=es`, `?lang=fr`).
3. Confirm new strings appear translated on the page.
4. For JavaScript strings, hard-refresh the browser (see [Troubleshooting](#9-troubleshooting)).

---

## Translation Workflow

Use this flow every time you add or change user-facing text. It mirrors [Section 4](#4-adding-new-translatable-content) in diagram form.

```
Developer adds new UI text
        ↓
Wrap with gettext() / {% trans %} / gettext() in JS
        ↓
Run makemessages (-a for django, -a -d djangojs for JavaScript)
        ↓
Translate .po files (de, es, fr — keep in sync with en)
        ↓
Run compilemessages
        ↓
Test translations in every supported language
        ↓
Commit .po changes (and .mo if your team commits compiled catalogs)
```

**Checklist at each step**

| Step | Command / action | Reference |
|------|------------------|-----------|
| Wrap strings | `_()`, `{% trans %}`, `gettext()` | [Section 3](#3-how-translation-works), [Best Practices](#7-best-practices) |
| Extract | `makemessages -a` and `-d djangojs` | [Commands](#5-commands) |
| Translate | Edit `locale/*/LC_MESSAGES/*.po` | [Step 3 above](#step-3--translate-new-entries) |
| Compile | `compilemessages` or `scripts/compile_i18n.sh` | [Deployment Notes](#deployment-notes) |
| Test | Header switcher + `?lang=` + hard refresh for JS | [Troubleshooting](#9-troubleshooting) |
| Review | [Code Review Checklist](#code-review-checklist) | [Maintenance Checklist](#10-maintenance-checklist) |

---

## 5. Commands

### Extract messages

```bash
# Update django.po for all configured locales
python manage.py makemessages -a

# Update djangojs.po for JavaScript strings
python manage.py makemessages -a -d djangojs

# Extract for a single locale
python manage.py makemessages -l de

# Remove obsolete entries while extracting
python manage.py makemessages -a --no-obsolete
python manage.py makemessages -a -d djangojs --no-obsolete
```

### Compile messages

```bash
python manage.py compilemessages
```

### Validate `.po` syntax (CI does this automatically)

```bash
msgfmt --check -o /dev/null locale/de/LC_MESSAGES/django.po
msgfmt --check -o /dev/null locale/de/LC_MESSAGES/djangojs.po
```

### Prerequisites

GNU gettext must be installed on your machine:

- **Ubuntu/Debian:** `sudo apt-get install gettext`
- **macOS:** `brew install gettext`
- **Windows:** Install gettext via MSYS2, WSL, or the official GNU gettext Windows builds

---

## 6. Adding a New Language

Example: adding Italian (`it`).

### 1. Update `LANGUAGES` in `FontEsin/settings.py`

```python
LANGUAGES = [
    ("en", _("English")),
    ("de", _("German")),
    ("fr", _("French")),
    ("es", _("Spanish")),
    ("it", _("Italian")),  # new
]
```

### 2. Update `SupportedLocale` in `accounts/constants.py`

Add the code to `SupportedLocale`, `CHOICES`, and `ALL`:

```python
class SupportedLocale:
    ...
    IT = "it"
    CHOICES = [..., (IT, _("Italian"))]
    ALL = frozenset({EN, DE, CS, FR, IT})
```

### 3. Update `LANGUAGE_DISPLAY_NAMES` in `FontEsin/templatetags/i18n_extras.py`

```python
LANGUAGE_DISPLAY_NAMES = {
    ...
    SupportedLocale.IT: "Italiano",
}
```

### 4. Create translation files

```bash
python manage.py makemessages -l it
python manage.py makemessages -l it -d djangojs
```

This creates `locale/it/LC_MESSAGES/django.po` and `djangojs.po`.

### 5. Translate

Copy structure from `locale/en/LC_MESSAGES/django.po` and translate every `msgstr`. For `en`, `msgstr` equals `msgid`; for `it`, provide Italian text.

### 6. Compile

```bash
python manage.py compilemessages
```

### 7. Test

- Select the new language in the header switcher.
- Browse major flows: auth, dashboard, profile, billing, notifications.
- Hit API endpoints with `Accept-Language: it` and confirm error messages translate.

### 8. Update CI

Add the new locale to the validation loop in `.github/workflows/i18n.yml`:

```yaml
for loc in en de es fr it; do
```

---

## 7. Best Practices

1. **Never hardcode user-facing strings.** If a human reads it in the UI, email, or API response, wrap it. See [Common Mistakes — Hardcoded English strings](#hardcoded-english-strings).

2. **Always use translation functions** — `_()`, `gettext()`, `{% trans %}`, or `gettext()` in JS.

3. **Use `blocktrans` / format strings for sentences with variables.** Do not split sentences around interpolated values; translators need full sentence context.

   ```django
   {# Good #}
   {% blocktrans with name=user.name %}Hello, {{ name }}{% endblocktrans %}

   {# Bad — word order may differ in other languages #}
   {% trans "Hello," %} {{ user.name }}
   ```

4. **Use `context` / `pgettext` for ambiguous words.** The project uses contexts like `"common"`, `"companies"`, `"dashboard"`, and `"billing"`. See [Common Mistakes — Missing translation context](#missing-translation-context-pgettext).

5. **Keep all locale files synchronized.** When you add a `msgid` to `en`, add and translate it in `de`, `es`, and `fr` before merging.

6. **Do not translate internal identifiers.** Database values, enum keys, API field names, URL slugs, and log messages stay in English. Only translate **display text** (labels shown to users). See [Common Mistakes — Translating database values](#translating-database-values-instead-of-display-labels).

7. **Use `gettext_lazy` at module scope, `gettext` at runtime.** Mixing them incorrectly can cause strings to be captured in the wrong language.

8. **Anchor JavaScript strings in `djangojs-catalog.js`** so extraction is reliable. Include `/jsi18n/` on any page that calls `gettext()` in inline scripts.

9. **Translate per recipient for async/off-request content.** Use `translation.override(user_language(user))` for notifications and emails so each user sees their preferred language.

10. **Commit both `.po` and `.mo` files** if that is the team convention, or at minimum commit `.po` and ensure CI/deployment runs `compilemessages`. This project's CI compiles on every push. See [Deployment Notes](#deployment-notes).

---

## Common Mistakes

Avoid these issues during development and code review. Most are also covered in [Troubleshooting](#9-troubleshooting).

### Hardcoded English strings

**Symptom:** Text stays in English regardless of the selected language.

**Cause:** A string was added directly in a template, view, form, or JavaScript file without wrapping it.

**Fix:** Wrap every user-visible string with the appropriate function (`_()`, `{% trans %}`, `gettext()`). Search for the raw English text if you suspect a miss:

```bash
rg "Your exact English string" templates/ accounts/ billing/
```

Common locations: HTML `placeholder`, `title`, and `aria-label` attributes; JavaScript `alert()` and dynamic DOM updates; form widget `attrs`.

### Forgetting `compilemessages`

**Symptom:** `.po` edits have no effect in the browser or API.

**Cause:** Django reads compiled `.mo` files at runtime, not `.po` source files.

**Fix:** Run `python manage.py compilemessages` after every `.po` change, then refresh. In production, ensure the deploy pipeline runs compilation before the app serves traffic. See [Deployment Notes](#deployment-notes).

### Forgetting JavaScript translations

**Symptom:** Server-rendered text translates correctly, but client-side validation, toasts, or dynamic labels stay in English.

**Cause:** Strings in inline or external JavaScript were not wrapped with `gettext()`, not added to `djangojs-catalog.js`, or missing from `djangojs.po`.

**Fix:**

1. Wrap the string with `gettext('…')`.
2. Add a matching anchor call in `FontEsin/static/js/djangojs-catalog.js`.
3. Run `python manage.py makemessages -a -d djangojs`.
4. Translate entries in `locale/*/LC_MESSAGES/djangojs.po`.
5. Run `compilemessages` and hard-refresh the browser.

See [FAQ — How do I translate JavaScript?](#how-do-i-translate-javascript).

### Using `gettext` instead of `gettext_lazy` in models/forms

**Symptom:** Labels or model field verbose names appear in the wrong language, or change unexpectedly when the server locale shifts.

**Cause:** `gettext()` evaluates immediately at import time, before the request locale is known. Module-level code (models, forms, `Meta` classes, constants) must defer evaluation.

**Fix:** Use `gettext_lazy as _` for anything defined at import time; reserve `gettext` for views, signals at request time, and notification composition inside `translation.override()`.

### Translating database values instead of display labels

**Symptom:** Queries break, filters return no results, or API clients receive unexpected values after a locale change.

**Cause:** A stored enum value, status code, or foreign-key label was translated before saving to the database.

**Fix:** Keep canonical English (or locale-neutral) values in the database. Apply `_()` only to the **display** half of choice tuples and to strings rendered in templates or API `message` fields — never to values used in business logic or persistence.

### Missing translation context (`pgettext`)

**Symptom:** The wrong translation appears, or gettext merges distinct strings into one ambiguous entry.

**Cause:** The same English word (e.g. `"Status"`, `"Company"`, `"PRO"`) is used in different screens without a `context` attribute or `pgettext` call.

**Fix:** Add `context "…"` in templates or use `pgettext("context.key", "English")` in Python so translators can provide distinct `msgstr` values per meaning.

---

## 8. Future Development Workflow

Whenever you add features, treat i18n as part of the definition of done.

| Change type | Required actions |
|-------------|------------------|
| **New page / template** | `{% load i18n %}`; wrap all visible text with `{% trans %}` or `{% blocktrans %}`; run `makemessages -a`; translate; compile; verify per locale. |
| **New button / label** | Same as templates. Prefer existing contexts (`"common"` for shared actions like Save, Cancel, View). |
| **New validation message** | Wrap with `_()` in Python `clean_*` or serializer validation; for client-side JS validation, add `gettext('…')` and update `djangojs.po`. |
| **New email** | Wrap subject and body with `_()`; send inside `translation.override(user_language(recipient))`. |
| **New notification** | Compose `title` / `body` as `Msg` / `MsgSeq` (see [Notifications](#notifications)) so the text re-translates on read; render with `note.display_title` / `note.display_body`; extract via `scripts/i18n_refresh.py`. |
| **New API error message** | Use `gettext()`; ensure the view uses `APILocaleMixin` if clients rely on `Accept-Language`. |
| **New model choice label** | `_()` on the label tuple only; keep the stored value as a stable ASCII key. |
| **New billing plan text** | Update `billing/plan_i18n.py` and run extraction for the `billing.plan.*` contexts. |

### Typical PR workflow

1. Implement feature with all strings wrapped.
2. `python manage.py makemessages -a && python manage.py makemessages -a -d djangojs`
3. Translate new entries in `de`, `es`, `fr`.
4. `python manage.py compilemessages`
5. Manually verify at least one non-English locale.
6. Open PR — CI runs `compilemessages` and `msgfmt --check`.

Follow the [Translation Workflow](#translation-workflow) diagram and the [Code Review Checklist](#code-review-checklist) before requesting review.

---

## 9. Troubleshooting

### Translation not updating after editing `.po` files

You must run `compilemessages` after every `.po` edit. Django reads `.mo` files, not `.po` files, at runtime.

```bash
python manage.py compilemessages
```

Restart the dev server if it was already running.

### Missing translations (English text shown in other locales)

- Check that `msgstr` is not empty in the target locale's `.po` file.
- Confirm you edited the correct domain (`django.po` vs `djangojs.po`).
- For contextual strings, ensure `msgctxt` matches exactly between `msgid` and `msgstr` blocks.
- Run `makemessages -a` to confirm the string was extracted.

### Forgot `compilemessages`

Symptom: `.po` changes have no effect. Fix: compile and refresh. See [Common Mistakes — Forgetting `compilemessages`](#forgetting-compilemessages).

### Browser caching

JavaScript translations are served from `/jsi18n/`. After recompiling, hard-refresh (Ctrl+Shift+R / Cmd+Shift+R) or clear cache. The project also ships `NoCachePagesMiddleware` for HTML pages, but the JS catalog may still be cached aggressively in some browsers.

### Hardcoded strings still visible

Search the codebase for the raw English text. Common misses:

- HTML `placeholder`, `title`, and `aria-label` attributes
- JavaScript `alert()` / dynamic DOM text without `gettext()`
- Form widget attrs set without `_()`
- f-strings or concatenation that bypass `_()`

```bash
# Example search
rg "Your exact English string" templates/ accounts/ billing/
```

See [Common Mistakes — Hardcoded English strings](#hardcoded-english-strings).

### Wrong language active

Check resolution order in `UserLocaleMiddleware`:

1. `?lang=` query parameter
2. Authenticated: `user.preferred_language`
3. Session `_language` key
4. `django_language` cookie
5. English fallback

### `makemessages` command not found / fails

Install GNU gettext (see [Commands](#5-commands)). On Windows, run commands inside WSL or an environment where `msguniq` and `xgettext` are on `PATH`.

### API returns English errors

Ensure the view inherits `APILocaleMixin` and that the client sends `Accept-Language` or the user has a language cookie set.

---

## 10. Maintenance Checklist

Before merging code that touches user-facing text:

- [ ] All new UI strings use `_()`, `{% trans %}`, `{% blocktrans %}`, or `gettext()` — no raw English in templates, views, forms, or JS shown to users.
- [ ] Context (`context "…"` / `pgettext`) added where the same English word appears in multiple places.
- [ ] `python manage.py makemessages -a` run (and `-d djangojs` if JS strings changed).
- [ ] New `msgid` entries translated in `locale/de/`, `locale/es/`, and `locale/fr/`.
- [ ] `python manage.py compilemessages` run successfully.
- [ ] `.mo` files updated (if committed) or CI compile step will run on merge.
- [ ] Verified at least one non-English locale in the browser.
- [ ] JavaScript strings added to `djangojs-catalog.js` when used in client-side code.
- [ ] `SupportedLocale` and `LANGUAGES` still aligned (if locales changed).
- [ ] API views returning translated errors use `APILocaleMixin`.
- [ ] Emails use `translation.override(user_language(…))`; in-app notifications use `Msg` / `MsgSeq` and are rendered with `display_title` / `display_body`.
- [ ] No translation applied to DB keys, enum values, or internal API identifiers.

For PR reviewers, see the expanded [Code Review Checklist](#code-review-checklist).

---

## Code Review Checklist

Use this list when reviewing pull requests that touch user-facing text. It complements the author-facing [Maintenance Checklist](#10-maintenance-checklist).

- [ ] **All new strings are wrapped** — Python (`_()` / `gettext()`), templates (`{% trans %}` / `{% blocktrans %}`), and JavaScript (`gettext()`).
- [ ] **Translation files updated** — `makemessages -a` (and `-d djangojs` when JS changed); new `msgid` entries present in `en`, `de`, `es`, and `fr`.
- [ ] **`compilemessages` executed** — `.mo` files regenerated locally or CI compile step will run on merge.
- [ ] **UI tested in every supported language** — at minimum German, Spanish, and French for new screens; use the header switcher or `?lang=de`, `?lang=es`, `?lang=fr`.
- [ ] **No hardcoded English strings remain** — check templates, inline JS, form attrs, and API `message` / `error` fields.
- [ ] **JavaScript translations verified** — strings anchored in `djangojs-catalog.js`; `djangojs.po` updated; hard refresh after compile.
- [ ] **API responses localized where applicable** — views returning user-facing errors inherit `APILocaleMixin`; strings use `gettext()` at return time.
- [ ] **Context used for ambiguous words** — `pgettext` / `context "…"` where the same English source appears in different meanings.
- [ ] **DB values unchanged** — only display labels translated; stored identifiers remain stable English keys.
- [ ] **`SupportedLocale` / `LANGUAGES` / `locale/` aligned** — if a locale was added or removed, all three were updated together.

---

## Deployment Notes

Translations must be compiled and shipped with every production release.

### `compilemessages` must run before deployment

Django loads binary `.mo` catalogs at runtime. Editing `.po` files alone does not affect a running server. Ensure your deploy pipeline runs:

```bash
python manage.py compilemessages
```

or `bash scripts/compile_i18n.sh` before the application process starts serving requests. CI already validates catalogs via `.github/workflows/i18n.yml`.

### Locale files must be included in deployments

Ship the entire `locale/` directory (at minimum all `LC_MESSAGES/*.mo` files). If your build step runs `compilemessages` on the server or in CI artifacts, include the resulting `.mo` files in the release image or bundle. Do not exclude `locale/` in `.dockerignore` or deployment sync rules.

### Translation cache considerations

- Django caches loaded translation catalogs in memory per process after first use.
- The JavaScript catalog at `/jsi18n/` may be cached by browsers or reverse proxies; versioned static assets and hard refreshes help during development.
- After deploying new `.mo` files, existing worker processes may hold stale in-memory catalogs until recycled.

### Restarting the application if required

After deploying updated `.mo` files, **restart application workers** (Gunicorn, uWSGI, Daphne, Celery workers that render emails/notifications, etc.) so every process reloads the catalogs. A simple code deploy without a process restart can leave old translations in memory until workers are replaced.

See also [Performance Notes](#performance-notes) and [Troubleshooting](#9-troubleshooting).

---

## Performance Notes

Internationalization adds minimal runtime overhead when configured correctly.

### Django loads `.mo` files in production

At startup (or on first translation lookup), Django reads compiled `.mo` binaries from `locale/<lang>/LC_MESSAGES/`. These files are compact and optimized for fast lookup. Never serve or parse `.po` files in production.

### `.po` files are only for editing

Human translators and `makemessages` work with `.po` source catalogs. They are not read during normal request handling. Always run `compilemessages` before testing or deploying.

### Translation lookup is lightweight

Once a catalog is loaded, `gettext()` resolves strings via an in-memory map. The cost per lookup is negligible compared to database and template rendering work. No external translation API is called at request time.

### Only newly added strings require translation

Existing `msgid` entries persist across releases. When you add features, only new or changed strings need extraction, translation in non-English `.po` files, and recompilation. Unchanged entries are reused automatically.

---

## Frequently Asked Questions (FAQ)

### How do I add a new language?

Follow [Section 6 — Adding a New Language](#6-adding-a-new-language). In summary: update `LANGUAGES`, `SupportedLocale`, and `LANGUAGE_DISPLAY_NAMES`; run `makemessages` for the new code; translate all entries; compile; test; update `.github/workflows/i18n.yml`.

### Why is my translation not appearing?

The most common causes:

1. **`compilemessages` not run** — see [Troubleshooting](#9-troubleshooting).
2. **Empty `msgstr`** in the target locale's `.po` file.
3. **Wrong domain** — string is in `djangojs.po` but you edited `django.po` (or vice versa).
4. **String never extracted** — run `makemessages` and confirm the `msgid` exists.
5. **Hardcoded English** — the source was never wrapped. See [Common Mistakes](#common-mistakes).
6. **Browser cache** — hard-refresh after recompiling JavaScript catalogs.

### When should I use `gettext_lazy`?

Use **`gettext_lazy` (`_`)** anywhere the string is defined at **import time**: model fields, form classes, `Meta` options, module-level constants, and `settings.py`. Use **`gettext`** at **request time**: views, `clean_*` methods that run during a request, API responses, and content inside `translation.override()`. See [Section 3](#3-how-translation-works).

### When should I use `blocktrans`?

Use `{% blocktrans %}` when the translated string contains **variables or pluralization**, so translators see the full sentence structure:

```django
{% blocktrans with name=user.name %}Hello, {{ name }}{% endblocktrans %}
```

Use plain `{% trans %}` for static phrases with no interpolation. Add `context "…"` when the English source is ambiguous.

### How do I translate JavaScript?

1. Ensure the page loads `/jsi18n/` (see `templates/base/base.html`).
2. Wrap strings with `gettext('…')` or `interpolate(gettext('…'), { … })`.
3. Add anchor calls in `FontEsin/static/js/djangojs-catalog.js` for reliable extraction.
4. Run `python manage.py makemessages -a -d djangojs`, translate `djangojs.po`, compile, and hard-refresh.

See [Common Mistakes — Forgetting JavaScript translations](#forgetting-javascript-translations).

### How do I translate emails and notifications?

Compose subject and body inside a per-recipient language context:

```python
from django.utils import translation
from FontEsin.i18n import user_language

with translation.override(user_language(recipient)):
    subject = _("Your invoice is ready")
    body = _("Hello %(name)s, your invoice for %(month)s is attached.") % {
        "name": recipient.first_name,
        "month": month_label,
    }
```

That is the right pattern for **emails**, which are delivered once and never re-read. **In-app notifications** go further: they live in the database and are re-read after the user may have switched language, so they store their msgid and parameters and re-translate on every read. See [Notifications](#notifications) for the `Msg` / `MsgSeq` API.

Either way, translate for the **recipient**, never in the acting user's request locale.

---

## 11. Current Implementation Status

- **Four languages are fully configured:** English, German, French, and Spanish (`en`, `de`, `fr`, `es`).
- **Multilingual infrastructure is complete:** middleware, language switcher, user preference persistence, JavaScript catalog, REST API locale mixin, notification localization, and billing plan i18n are in place.
- **Translation catalogs are populated:** `locale/` contains `django.po` and `djangojs.po` (and compiled `.mo` files) for all four locales.
- **CI guards quality:** `.github/workflows/i18n.yml` runs `compilemessages` and validates `.po` syntax on every push/PR.
- **Future content additions** only require wrapping new strings, extracting, translating, and compiling — **no architectural changes are needed** when new features are added.

When you ship a new screen, button, validation rule, email, notification, or API error message, follow [Sections 4](#4-adding-new-translatable-content) and [8](#8-future-development-workflow). The system is designed so i18n is incremental work on each feature, not a separate migration project.

---

## Quick reference

```python
# Python — lazy (models, forms, constants)
from django.utils.translation import gettext_lazy as _

# Python — runtime (views, notifications)
from django.utils.translation import gettext as _

# Python — contextual
from django.utils.translation import pgettext

# Per-user language
from django.utils import translation
from FontEsin.i18n import user_language

with translation.override(user_language(user)):
    send_notification(_("Your request was approved."))
```

```django
{% load i18n %}
{% trans "Dashboard" context "common" %}
{% blocktrans with total=count context "dashboard" %}Total: {{ total }}{% endblocktrans %}
```

```bash
python manage.py makemessages -a
python manage.py makemessages -a -d djangojs
python manage.py compilemessages
```
