from django import forms
from accounts.models import Company, Tenant


class CompanyForm(forms.ModelForm):

    class Meta:
        model = Company
        fields = ["tenant", "name", "registration_id", "is_active"]
        widgets = {
            "tenant": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "registration_id": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if not user:
            return

        if user.is_superuser:
            self.fields["tenant"].queryset = Tenant.objects.all()

        else:
            # Restrict tenant admin to their own tenant only
            self.fields["tenant"].queryset = Tenant.objects.filter(
                id=user.tenant_id
            )
            self.fields["tenant"].initial = user.tenant

            # Hide tenant field completely from tenant admin
            self.fields["tenant"].widget = forms.HiddenInput()
