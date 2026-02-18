from accounts.models import User, Tenant, Role, UserRole, UserCompany, UserCompanyRole,Company
from rest_framework import serializers
from accounts_api.serializers.company_serializers import CompanySerializer

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class UserProfileSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    companies = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "tenant",
            "role",
            "companies",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields

    def get_role(self, obj):
        try:
            user_role = (
                UserRole.objects
                .select_related("role")
                .get(user=obj)
            )
            return RoleSerializer(user_role.role).data
        except UserRole.DoesNotExist:
            return None

    def get_companies(self, obj):
        user_companies = (
            UserCompany.objects
            .filter(user=obj)
            .select_related("company")
        )

        result = []
        for uc in user_companies:
            result.append(
                CompanySerializer({
                    "id": uc.company.id,
                    "name": uc.company.name,
                    "is_primary": uc.is_primary,
                }).data
            )

        return result

