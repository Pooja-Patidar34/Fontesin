from django.contrib import admin

from .models import Listing, ListingReaction, ListingAuditLog


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "listing_type", "category_type", "status", "owner_company", "created_at")
    list_filter = ("listing_type", "category_type", "status", "module_id", "visibility_scope")
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at", "published_at", "suspended_at")


@admin.register(ListingReaction)
class ListingReactionAdmin(admin.ModelAdmin):
    list_display = ("listing", "from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ListingAuditLog)
class ListingAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "listing", "changed_by", "created_at")
    list_filter = ("action",)
    readonly_fields = ("id", "created_at")
