"""
Listings Engine - Business User + Admin API (cookbook Section 12 / Step 3).

Response envelope matches the rest of the project:
    {"status": bool, "data"/"errors"/"message": ...}
"""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from FontEsin.i18n.drf import APILocaleMixin
from accounts.utils.i18n_messages import Msg
from accounts.utils.notifications import notify

from listings.models import Listing, ListingReaction
from listings.serializers import (
    ListingReadSerializer,
    ListingWriteSerializer,
    ListingReactionSerializer,
    ListingAuditLogSerializer,
)
from listings import services
from listings import module_registry


def _audit_snapshot(listing):
    """JSON-serializable snapshot of a listing for the audit log.

    DRF returns UUID/Decimal/datetime objects in `.data`; round-tripping through
    DjangoJSONEncoder coerces them to primitives the JSONField can store.
    """
    data = ListingReadSerializer(listing).data
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def _notify_listing_owner(listing, sender, title, body="", link_url=""):
    """Drop an in-app notification on the listing owner (cookbook `notifyUser`).

    `notify()` swallows its own errors, so a notification failure can never
    break the originating reaction/suspend action.
    """
    return notify(
        recipient=listing.owner_user,
        sender=sender,
        title=title,
        body=body,
        link_url=link_url,
        related_company=listing.owner_company,
    )


class ListingCollectionAPIView(APILocaleMixin, APIView):
    """POST -> create listing (12.1); GET -> search active listings (12.3)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            qs = Listing.objects.filter(
                status=Listing.ACTIVE,
                visibility_scope__in=services.get_user_visible_scopes(user),
            )
            if not services.is_admin(user):
                qs = qs.filter(tenant=user.tenant)

            params = request.query_params
            filter_map = {
                "listing_type": "listing_type",
                "category_type": "category_type",
                "module_id": "module_id",
                "company_id": "owner_company_id",
                "region": "region",
            }
            for param, field in filter_map.items():
                value = params.get(param)
                if value:
                    qs = qs.filter(**{field: value})

            # NACE and country go through the same helpers the browse page uses,
            # so both surfaces agree: a section matches its whole subtree, and a
            # country matches whether it arrives as an ISO code or English name.
            if params.get("nace_isic_code"):
                qs = qs.filter(services.nace_filter(params["nace_isic_code"])[0])
            if params.get("country"):
                qs = qs.filter(services.country_filter(params["country"]))

            keyword = params.get("keyword")
            if keyword:
                qs = qs.filter(
                    Q(title__icontains=keyword)
                    | Q(description__icontains=keyword)
                    | Q(keywords__icontains=keyword)
                )

            qs = qs.select_related("owner_company", "owner_user", "nace_code")
            serializer = ListingReadSerializer(qs, many=True)
            return Response({"status": True, "data": serializer.data})

        except DatabaseError:
            return Response(
                {"status": False, "message": _("Database error while searching listings")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"status": False, "message": _("Unable to search listings")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        user = request.user

        if not (services.is_business_user(user) or services.is_admin(user)):
            return Response(
                {"status": False, "message": _("Only Business Users can create listings.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ListingWriteSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = serializer.validated_data["owner_company"]
        if not services.company_belongs_to_user(company, user):
            return Response(
                {"status": False, "message": _("You can only create listings for a company you own.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        module_id = serializer.validated_data.get("module_id")
        if not module_registry.user_can_access_id(user, module_id):
            # Professional modules are paid-only; a Free-plan Business User is
            # told to upgrade rather than given the generic role refusal.
            module = module_registry.get_module_by_id(module_id)
            if module and module_registry.module_locked_for_user(user, module):
                message = _("Professional modules are available on paid plans only. "
                            "Upgrade your plan to unlock this module.")
            else:
                message = _("You do not have access to this module.")
            return Response(
                {"status": False, "message": message},
                status=status.HTTP_403_FORBIDDEN,
            )

        scope = serializer.validated_data["visibility_scope"]
        if not services.can_publish_to_scope(user, scope):
            return Response(
                {"status": False, "message": _("You are not allowed to publish to this visibility scope.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            published_at = timezone.now() if serializer.validated_data.get("status") == Listing.ACTIVE else None
            listing = serializer.save(
                owner_user=user,
                tenant=user.tenant,
                published_at=published_at,
            )
            services.create_audit_log(listing, "listing_created", None, _audit_snapshot(listing), user)
            return Response(
                {"status": True, "data": ListingReadSerializer(listing).data},
                status=status.HTTP_201_CREATED,
            )
        except DatabaseError:
            return Response(
                {"status": False, "message": _("Database error while creating listing")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            return Response(
                {"status": False, "message": _("Unable to create listing")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MyOffersAPIView(APILocaleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        listings = (
            Listing.objects.filter(owner_user=request.user, listing_type=Listing.OFFER)
            .select_related("owner_company", "nace_code")
        )
        return Response({"status": True, "data": ListingReadSerializer(listings, many=True).data})


class MyDemandsAPIView(APILocaleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        listings = (
            Listing.objects.filter(owner_user=request.user, listing_type=Listing.DEMAND)
            .select_related("owner_company", "nace_code")
        )
        return Response({"status": True, "data": ListingReadSerializer(listings, many=True).data})


class ListingDetailAPIView(APILocaleMixin, APIView):
    """GET -> detail (12.x); PUT -> update own listing (12.2)."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, listing_id):
        return (
            Listing.objects.select_related("owner_company", "owner_user", "nace_code")
            .get(id=listing_id)
        )

    def get(self, request, listing_id):
        try:
            listing = self._get_object(listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner = services.is_listing_owner(listing, user)
        if not (is_owner or services.is_admin(user)):
            # Non-owners may only see active, visible listings.
            if listing.status != Listing.ACTIVE or not services.can_view_scope(user, listing.visibility_scope):
                return Response({"status": False, "message": _("Permission denied")}, status=status.HTTP_403_FORBIDDEN)

        return Response({"status": True, "data": ListingReadSerializer(listing).data})

    def put(self, request, listing_id):
        try:
            listing = self._get_object(listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if not services.is_listing_owner(listing, user) and not services.is_admin(user):
            return Response(
                {"status": False, "message": _("You cannot edit another user's listing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if listing.status == Listing.SUSPENDED and not services.is_admin(user):
            return Response(
                {"status": False, "message": _("Suspended listing cannot be edited by Business User.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        old_snapshot = _audit_snapshot(listing)
        serializer = ListingWriteSerializer(
            listing, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        scope = serializer.validated_data.get("visibility_scope", listing.visibility_scope)
        if not services.can_publish_to_scope(user, scope):
            return Response(
                {"status": False, "message": _("You are not allowed to publish to this visibility scope.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            updated = serializer.save()
            services.create_audit_log(updated, "listing_updated", old_snapshot, _audit_snapshot(updated), user)
            return Response({"status": True, "data": ListingReadSerializer(updated).data})
        except DatabaseError:
            return Response(
                {"status": False, "message": _("Database error while updating listing")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListingStatusAPIView(APILocaleMixin, APIView):
    """Owner activate/deactivate (cookbook Step 3.15/3.16)."""

    permission_classes = [IsAuthenticated]
    target_status = None  # set by subclass
    action_label = None

    def post(self, request, listing_id):
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if not services.is_listing_owner(listing, user) and not services.is_admin(user):
            return Response(
                {"status": False, "message": _("You cannot modify another user's listing.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if listing.status == Listing.SUSPENDED and not services.is_admin(user):
            return Response(
                {"status": False, "message": _("Suspended listing cannot be changed by Business User.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        old_snapshot = _audit_snapshot(listing)
        listing.status = self.target_status
        if self.target_status == Listing.ACTIVE and listing.published_at is None:
            listing.published_at = timezone.now()
        listing.save(update_fields=["status", "published_at", "updated_at"])
        services.create_audit_log(listing, self.action_label, old_snapshot, _audit_snapshot(listing), user)
        return Response({"status": True, "data": ListingReadSerializer(listing).data})


class ListingActivateAPIView(ListingStatusAPIView):
    target_status = Listing.ACTIVE
    action_label = "listing_activated"


class ListingDeactivateAPIView(ListingStatusAPIView):
    target_status = Listing.INACTIVE
    action_label = "listing_deactivated"


class ListingReactionAPIView(APILocaleMixin, APIView):
    """POST -> create an interest reaction (cookbook 12.4)."""

    permission_classes = [IsAuthenticated]
    DEFAULT_MESSAGE = _(
        "I am interested in this listing and would like to start communication through FONTESIN."
    )

    def post(self, request, listing_id):
        user = request.user
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        if listing.status != Listing.ACTIVE:
            return Response(
                {"status": False, "message": _("Reaction is allowed only for active listings.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if services.is_listing_owner(listing, user):
            return Response(
                {"status": False, "message": _("You cannot react to your own listing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not services.can_view_scope(user, listing.visibility_scope):
            return Response({"status": False, "message": _("Permission denied")}, status=status.HTTP_403_FORBIDDEN)

        # A reaction is company-to-company (from_company is NOT NULL). Resolve
        # the company the user is acting as — primary_company alone is blank on
        # plenty of accounts and used to reach the insert as a null, where the
        # IntegrityError below reported it as "already reacted".
        from_company = services.acting_company(user, request)
        if from_company is None:
            return Response(
                {"status": False,
                 "message": _("Add a company to your account before reacting to a listing.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = (request.data.get("message") or "").strip() or self.DEFAULT_MESSAGE
        try:
            reaction = ListingReaction.objects.create(
                listing=listing,
                from_user=user,
                from_company=from_company,
                to_user=listing.owner_user,
                to_company=listing.owner_company,
                message=message,
                status=ListingReaction.NEW,
            )
        except IntegrityError:
            return Response(
                {"status": False, "message": _("You have already reacted to this listing.")},
                status=status.HTTP_409_CONFLICT,
            )

        _notify_listing_owner(
            listing,
            sender=user,
            title=Msg("New reaction to your listing"),
            body=Msg("%(title)s received a new reaction.", title=listing.title),
            link_url=reverse("listings_web:listing-reactions", args=[listing.id]),
        )
        return Response(
            {"status": True, "data": ListingReactionSerializer(reaction).data},
            status=status.HTTP_201_CREATED,
        )


class MyReactionsAPIView(APILocaleMixin, APIView):
    """Reactions received on the current user's listings (cookbook Step 6.30)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        reactions = ListingReaction.objects.filter(to_user=request.user).select_related("listing")
        return Response({"status": True, "data": ListingReactionSerializer(reactions, many=True).data})


class ListingSuspendAPIView(APILocaleMixin, APIView):
    """Admin suspend with reason (cookbook 12.5)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        user = request.user
        if not services.is_admin(user):
            return Response({"status": False, "message": _("Permission denied")}, status=status.HTTP_403_FORBIDDEN)

        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            return Response(
                {"status": False, "message": _("Suspension reason is required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        old_snapshot = _audit_snapshot(listing)
        listing.status = Listing.SUSPENDED
        listing.suspension_reason = reason
        listing.suspended_at = timezone.now()
        listing.save(update_fields=["status", "suspension_reason", "suspended_at", "updated_at"])
        services.create_audit_log(listing, "listing_suspended", old_snapshot, _audit_snapshot(listing), user)
        _notify_listing_owner(
            listing,
            sender=user,
            title=Msg("Your listing was suspended"),
            body=Msg("%(title)s was suspended. Reason: %(reason)s",
                     title=listing.title, reason=reason),
        )
        return Response({"status": True, "data": ListingReadSerializer(listing).data})


class ListingReactivateAPIView(APILocaleMixin, APIView):
    """Admin reactivate a suspended listing (cookbook Step 7.34)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        user = request.user
        if not services.is_admin(user):
            return Response({"status": False, "message": _("Permission denied")}, status=status.HTTP_403_FORBIDDEN)

        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        old_snapshot = _audit_snapshot(listing)
        listing.status = Listing.ACTIVE
        listing.suspension_reason = ""
        listing.suspended_at = None
        if listing.published_at is None:
            listing.published_at = timezone.now()
        listing.save(update_fields=["status", "suspension_reason", "suspended_at", "published_at", "updated_at"])
        services.create_audit_log(listing, "listing_reactivated", old_snapshot, _audit_snapshot(listing), user)
        return Response({"status": True, "data": ListingReadSerializer(listing).data})


class ListingAuditLogAPIView(APILocaleMixin, APIView):
    """Audit history for a listing (cookbook Step 7.35). Owner or admin."""

    permission_classes = [IsAuthenticated]

    def get(self, request, listing_id):
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return Response({"status": False, "message": _("Listing not found")}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if not services.is_listing_owner(listing, user) and not services.is_admin(user):
            return Response({"status": False, "message": _("Permission denied")}, status=status.HTTP_403_FORBIDDEN)

        logs = listing.audit_logs.all()
        return Response({"status": True, "data": ListingAuditLogSerializer(logs, many=True).data})
