from django import forms
from accounts.models import Company, Tenant


class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = [
            # ---- Tenant / Identity ----
            "tenant",
            "name",
            "registration_id",
            "classification",

            # ---- Address ----
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",

            # ---- Contact ----
            "phone",
            "phone_secondary",
            "fax",
            "website",

            # ---- Status ----
            "is_active",
        ]

        widgets = {
            # Identity
            "tenant": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "registration_id": forms.TextInput(attrs={"class": "form-control"}),
            "classification": forms.Select(attrs={"class": "form-control"}),

            # Address
            "address_line1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),

            "latitude": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),
            "longitude": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),

            # Contact
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "phone_secondary": forms.TextInput(attrs={"class": "form-control"}),
            "fax": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),

            # Status
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if not user:
            return

        if user.is_superuser:
            # Superuser can select any tenant
            self.fields["tenant"].queryset = Tenant.objects.all()

        else:
            # Tenant admin restricted to own tenant
            self.fields["tenant"].queryset = Tenant.objects.filter(
                id=user.tenant_id
            )
            self.fields["tenant"].initial = user.tenant
            self.fields["tenant"].widget = forms.HiddenInput()