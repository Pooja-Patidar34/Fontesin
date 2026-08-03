from django.contrib import admin

from accounts.models import (
    ConsultantAssignment,
    FranchiseApplication,
    NaceCode,
    NaicsCode,
    Tenant,
)


class IndustryCodeAdmin(admin.ModelAdmin):
    """Read-only admin for industry classification lookups.

    These tables are seeded from upstream CSVs (Eurostat for NACE, US Census
    for NAICS) via ``python manage.py seed_industry_codes`` — editing rows
    in the admin would just drift from the canonical source on the next
    re-seed.
    """

    list_display = ("code", "title", "level", "parent", "is_active")
    list_filter = ("level", "is_active")
    search_fields = ("code", "title")
    ordering = ("code",)
    autocomplete_fields = ("parent",)
    list_select_related = ("parent",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NaceCode)
class NaceCodeAdmin(IndustryCodeAdmin):
    pass


@admin.register(NaicsCode)
class NaicsCodeAdmin(IndustryCodeAdmin):
    pass


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Franchise nodes (and legacy partitions). Surfaces the tree, territory,
    and lifecycle so the Super Admin can inspect the hierarchy (spec §7.4)."""

    list_display = (
        "name",
        "franchise_level",
        "franchise_status",
        "parent",
        "territory_country",
        "territory_region",
        "is_exclusive",
        "is_active",
    )
    list_filter = ("franchise_level", "franchise_status", "is_active", "is_deleted")
    list_select_related = ("parent",)
    search_fields = ("name", "slug", "territory_country", "territory_region", "territory_city")
    raw_id_fields = ("parent", "owner_user", "owner_company", "approved_by", "created_by")
    readonly_fields = ("slug", "created_at", "updated_at")
    ordering = ("name",)


@admin.register(FranchiseApplication)
class FranchiseApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "applicant_user",
        "requested_level",
        "requested_country",
        "requested_region",
        "application_status",
        "parent_franchise",
        "created_at",
    )
    list_filter = ("application_status", "requested_level")
    list_select_related = ("applicant_user", "parent_franchise")
    search_fields = (
        "applicant_user__email",
        "requested_country",
        "requested_region",
        "requested_city",
    )
    raw_id_fields = (
        "applicant_user",
        "parent_franchise",
        "approved_by",
        "rejected_by",
        "created_franchise",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(ConsultantAssignment)
class ConsultantAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "consultant_user",
        "franchise_node",
        "consultant_type",
        "status",
        "territory_country",
        "territory_region",
        "assigned_at",
    )
    list_filter = ("consultant_type", "status")
    list_select_related = ("consultant_user", "franchise_node")
    search_fields = ("consultant_user__email", "franchise_node__name")
    raw_id_fields = ("consultant_user", "franchise_node", "assigned_by")
    readonly_fields = ("created_at", "updated_at")
