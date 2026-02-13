from django import forms
from accounts.models import Tenant


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ["name", "is_active"] 
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter tenant name"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }
