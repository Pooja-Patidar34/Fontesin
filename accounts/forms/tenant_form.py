import re

from django import forms
from accounts.models import Tenant

# 2-100 chars, letters (incl. accented) / digits / spaces / & ' . , - ( ) only; must contain at least one letter.
TENANT_NAME_RE = re.compile(r"^(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}$")


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ["name", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter tenant name",
                "minlength": "2",
                "maxlength": "100",
                "pattern": r"(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}",
                "title": "2-100 characters. Letters, digits, spaces, and & ' . , - ( ) only. Must contain at least one letter.",
                # Strip disallowed characters as the user types or pastes \u2014
                # mirrors the server-side TENANT_NAME_RE allowlist. Browser
                # still enforces maxlength=100 natively.
                "oninput": (
                    "this.value=this.value"
                    ".replace(/[^A-Za-z\u00C0-\u024F0-9&'.,\\-()\\s]/g,'')"
                    ".replace(/\\s+/g,' ').replace(/^ /,'')"
                ),
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Tenant name must be at least 2 characters.")
        if len(name) > 100:
            raise forms.ValidationError("Tenant name must be 100 characters or fewer.")
        if not TENANT_NAME_RE.match(name):
            raise forms.ValidationError(
                "Tenant name may only contain letters, digits, spaces, and the symbols & ' . , - ( ), and must contain at least one letter."
            )
        # Reject duplicate franchise names (case-insensitive). The model only
        # auto-uniquifies `slug`, not `name`, so without this two franchises
        # could share the same display name. Tenant.objects excludes
        # soft-deleted rows, so a deleted franchise's name can be reused.
        duplicates = Tenant.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                "A franchise with this name already exists. Please choose a different name."
            )
        return name
