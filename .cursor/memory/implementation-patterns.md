# Implementation Patterns

Approved patterns for i18n work. **Reuse these — do not invent alternatives.**

Exemplar files: `templates/auth/login.html`, `accounts/view/auth.py`, `templates/dashboard/companies.html`.

---

## Python gettext

```python
from django.utils.translation import gettext as _

messages.success(request, _("Company saved."))
return JsonResponse({"message": _("Action failed.")})
```

Runtime strings only. Use at call time inside views, utils, and notify helpers.

---

## gettext_lazy (module-level)

```python
from django.utils.translation import gettext_lazy as _

class CompanyForm(forms.ModelForm):
    class Meta:
        labels = {"name": _("Company name")}

    def clean_name(self):
        raise ValidationError(_("Name is required."))
```

Also for `accounts/constants.py` choice tuples and `settings.LANGUAGES` labels.

---

## Template gettext

```django
{% load i18n %}
{% trans "Save" context "common" %}
<title>{% trans "Log In" context "auth.login" %} – FONTESIN</title>
```

Always `{% load i18n %}` at top. Use `context` for `msgctxt` namespacing.

---

## blocktrans examples

**Simple with variable:**
```django
{% blocktrans with role=role_label context "auth.application_pending" %}{{ role }} application{% endblocktrans %}
```

**With HTML (no trim if tags inside):**
```django
{% blocktrans context "auth.login" %}By logging in, you agree to our <a href="#">Terms</a>.{% endblocktrans %}
```

**Interpolation + plan data:**
```django
{% blocktrans with plan_name=subscription.plan.name currency=subscription.plan.currency price=subscription.plan.price context "auth.pending_approval" %}{{ plan_name }} Plan - {{ currency }} {{ price }}{% endblocktrans %}
```

Use `{% blocktrans trimmed %}` when no inner HTML tags. Match variable names exactly to Python context.

---

## JavaScript localization pattern

**Shared catalog (Phase 2):**
```javascript
function g(fallback) {
  return (typeof gettext === 'function') ? gettext(fallback) : fallback;
}
const TOAST_TITLES = { success: g('Success'), error: g('Error'), /* ... */ };
```

**Module I18N bridge (Phase 5+):**
```django
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.COMPANY_I18N = {
    saved: '{% filter escapejs %}{% trans "Company saved." context "companies" %}{% endfilter %}',
  };
  Object.keys(window.COMPANY_I18N).forEach(function (k) {
    window.COMPANY_I18N[k] = g(window.COMPANY_I18N[k]);
  });
})();
</script>
```

Bridges: `COMPANY_I18N`, `USER_I18N`, `BILLING_I18N`, `WORKFLOW_I18N`. Use `Object.assign` when merging into existing `USER_I18N`.

---

## Notification localization pattern

```python
from django.utils import translation
from django.utils.translation import gettext as _
from FontEsin.i18n import user_language

def _localized_notify(recipient, *, title="", body="", ...):
    with translation.override(user_language(recipient)):
        return notify(recipient=recipient, title=title, body=body, ...)
```

Callers pass English msgids; override translates at write-time for recipient locale.

---

## Email localization pattern

```python
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _

with translation.override(user_language):
    subject = _("FONTESIN – Your password reset code")
    html_body = render_to_string("email/otp_password_reset.html", context)
    text_body = render_to_string("email/otp_password_reset.txt", context)
```

Email templates use `{% trans %}` / `{% blocktrans %}`. No f-string bodies.

---

## API localization pattern

```python
from FontEsin.i18n.drf import APILocaleMixin

class CompanyViewSet(APILocaleMixin, viewsets.ViewSet):
    def create(self, request):
        return Response({"message": _("Company created.")})
```

Mixin on DRF views only. Wrap `"message"` / `"error"` string values — do not change response shape.

---

## Billing plan pattern

```python
# billing/plan_i18n.py
from django.utils.translation import pgettext
pgettext("billing.plan.basic", "Up to 50 companies")
```

```django
{% load plan_i18n_tags %}
{{ plan|plan_feature:1 }}
```

Attach `display_*` fields in view before template render.

---

## Phase workflow (every conversion)

1. Wrap only target files from `current-phase.md`
2. Run phase grep gate (not full-repo scan)
3. Sync `.po` via `makemessages` or `scripts/sync_phaseN_po.py`
4. `python manage.py check`
5. Update `completed-work.md`, `current-phase.md`, `do-not-revisit.md`
