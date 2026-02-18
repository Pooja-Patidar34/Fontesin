from rest_framework import serializers
from accounts.models import Company, Tenant


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name"]
        

class CompanyCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "tenant",
            "name",
            "registration_id",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        name = attrs.get("name") or getattr(self.instance, "name", None)

        if user and not user.is_superuser:
            if tenant != user.tenant:
                raise serializers.ValidationError(
                    {"tenant": "You cannot manage companies outside your tenant"}
                )

        if tenant and name:
            qs = Company.objects.filter(
                tenant=tenant,
                name__iexact=name
            )
            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "Company with this name already exists in tenant"}
                )

        return attrs


