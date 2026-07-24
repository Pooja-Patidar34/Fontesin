from django.urls import path

from listings import web

app_name = "listings_web"

urlpatterns = [
    # Browse / search + detail
    path("", web.browse_listings, name="browse"),
    path("<uuid:listing_id>/", web.listing_detail, name="detail"),
    path("<uuid:listing_id>/react/", web.react_listing, name="react"),

    # Business User - create / edit / my listings
    path("add/", web.add_listing, name="add"),
    path("my-listings/", web.my_listings, name="my-listings"),
    path("my-offers/", web.my_offers, name="my-offers"),
    path("my-demands/", web.my_demands, name="my-demands"),
    path("my-reactions/", web.my_reactions, name="my-reactions"),
    path("reactions/set-status/", web.reaction_set_status, name="reaction-set-status"),
    path("<uuid:listing_id>/edit/", web.edit_listing, name="edit"),
    path("<uuid:listing_id>/activate/", web.set_status, {"target": "activate"}, name="activate"),
    path("<uuid:listing_id>/deactivate/", web.set_status, {"target": "deactivate"}, name="deactivate"),

    # Audit history (owner or admin)
    path("<uuid:listing_id>/history/", web.audit_history, name="history"),

    # Admin
    path("manage/", web.admin_listings, name="admin"),
    path("<uuid:listing_id>/suspend/", web.admin_suspend, name="suspend"),
    path("<uuid:listing_id>/reactivate/", web.admin_reactivate, name="reactivate"),
]
