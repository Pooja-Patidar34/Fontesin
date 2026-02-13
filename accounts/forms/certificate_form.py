from django import forms
from accounts.models import Permission, Role

class RoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Role
        fields = ["name", "permissions"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and not user.is_superuser:
            self.fields["permissions"].queryset = Permission.objects.all()


class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ["code", "description"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
        }
