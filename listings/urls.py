from django.urls import path

from listings.api import (
    ListingCollectionAPIView,
    MyOffersAPIView,
    MyDemandsAPIView,
    MyReactionsAPIView,
    ListingDetailAPIView,
    ListingActivateAPIView,
    ListingDeactivateAPIView,
    ListingReactionAPIView,
    ListingSuspendAPIView,
    ListingReactivateAPIView,
    ListingAuditLogAPIView,
)

app_name = "listings"

urlpatterns = [
    # Collection: search (GET) + create (POST)
    path("", ListingCollectionAPIView.as_view(), name="listing-collection"),
    # Business User inbox views (static segments before the uuid route)
    path("my-offers/", MyOffersAPIView.as_view(), name="my-offers"),
    path("my-demands/", MyDemandsAPIView.as_view(), name="my-demands"),
    path("my-reactions/", MyReactionsAPIView.as_view(), name="my-reactions"),

    # Single listing: detail (GET) + update (PUT)
    path("<uuid:listing_id>/", ListingDetailAPIView.as_view(), name="listing-detail"),

    # Status transitions
    path("<uuid:listing_id>/activate/", ListingActivateAPIView.as_view(), name="listing-activate"),
    path("<uuid:listing_id>/deactivate/", ListingDeactivateAPIView.as_view(), name="listing-deactivate"),
    # Reactions
    path("<uuid:listing_id>/interest/", ListingReactionAPIView.as_view(), name="listing-interest"),

    # Admin actions
    path("<uuid:listing_id>/suspend/", ListingSuspendAPIView.as_view(), name="listing-suspend"),
    path("<uuid:listing_id>/reactivate/", ListingReactivateAPIView.as_view(), name="listing-reactivate"),
    path("<uuid:listing_id>/audit/", ListingAuditLogAPIView.as_view(), name="listing-audit"),
]
