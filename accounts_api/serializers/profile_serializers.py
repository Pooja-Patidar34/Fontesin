from rest_framework import serializers
from accounts.models import User
from accounts_api.serializers.company_serializers import CompanySerializer


class UserProfileSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)
    role = serializers.CharField(source="role.name", read_only=True)

    companies = CompanySerializer(
        many=True,
        read_only=True,
        source="companies_through_user",
    )

    class Meta:
        model = User
        fields = [
            "id",

            # Identity
            "email",
            "first_name",
            "last_name",

            # Tenant & Role
            "tenant_id",
            "role",

            # Contact
            "phone",
            "national_prefix",

            # Personal
            "birth_date",
            "gender",
            "ethnicity",
            "preferred_language",

            # Address
            "address_line1",
            "address_line2",
            "city",
            "state_region",
            "postal_code",
            "country",

            # Profile
            "bio",
            "notes",
            "photo_url",

            # Companies (flattened)
            "companies",

            # Metadata
            "created_at",
        ]

        read_only_fields = fields