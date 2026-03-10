from rest_framework import serializers
from accounts.models import Company, Tenant

from rest_framework import serializers
from accounts.models import Company


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "classification",
            "city",
            "country",
        ]
        
class CompanyCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id",
            "tenant",
            "name",
            "registration_id",
            "classification",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",
            "phone",
            "phone_secondary",
            "fax",
            "website",
        ]
        read_only_fields = ["id"]

    def validate_tenant(self, value):
        request = self.context.get("request")
        if request and not request.user.is_superuser:
            if value != request.user.tenant:
                raise serializers.ValidationError(
                    "You cannot assign a company outside your tenant"
                )
        return value
