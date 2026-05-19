from django.contrib import admin

from accounts.models import NaceCode, NaicsCode


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
