"""
Listings Engine - serializers.

`ListingReadSerializer`   -> full read representation (also used for audit snapshots).
`ListingWriteSerializer`  -> create/update, carrying the cookbook Section 6 validation.
`ListingReactionSerializer` / `ListingAuditLogSerializer` -> read representations.
"""

import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from listings.models import Listing, ListingReaction, ListingAuditLog


# Matches emoji / pictographic characters across the common Unicode blocks
# (emoticons, symbols & pictographs, transport, flags, dingbats, variation
# selectors and ZWJ used to build compound emoji).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols, pictographs, emoji, transport, etc.
    "\U00002600-\U000027BF"  # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U00002190-\U000021FF"  # arrows
    "\U00002B00-\U00002BFF"  # misc symbols and arrows
    "\U0000200D"             # zero-width joiner
    "\U000020E3"             # combining enclosing keycap
    "]+",
    flags=re.UNICODE,
)


def _has_emoji(value):
    return bool(_EMOJI_RE.search(value or ""))


class ListingReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            "id",
            "listing_type",
            "category_type",
            "tenant",
            "owner_company",
            "owner_user",
            "nace_code",
            "title",
            "description",
            "keywords",
            "price_without_vat",
            "currency",
            "minimum_quantity_or_scope",
            "unit",
            "video_url",
            "product_image_id",
            "certification_text",
            "certification_image_id",
            "country",
            "region",
            "city",
            "visibility_scope",
            "status",
            "suspension_reason",
            "module_id",
            "module_specific_data",
            "published_at",
            "suspended_at",
            "created_at",
            "updated_at",
        ]


class ListingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            "listing_type",
            "category_type",
            "owner_company",
            "nace_code",
            "title",
            "description",
            "keywords",
            "price_without_vat",
            "currency",
            "minimum_quantity_or_scope",
            "unit",
            "video_url",
            "product_image_id",
            "certification_text",
            "certification_image_id",
            "country",
            "region",
            "city",
            "visibility_scope",
            "status",
            "module_id",
            "module_specific_data",
        ]

    # ---- field-level validation (cookbook Section 6) ----
    def validate_title(self, value):
        if not value or len(value) < 3 or len(value) > 100:
            raise serializers.ValidationError(_("Title must be between 3 and 100 characters."))
        if _has_emoji(value):
            raise serializers.ValidationError(_("Title must not contain emojis."))
        return value

    def validate_description(self, value):
        if not value or len(value) < 20 or len(value) > 200:
            raise serializers.ValidationError(_("Description must be between 20 and 200 characters."))
        if _has_emoji(value):
            raise serializers.ValidationError(_("Description must not contain emojis."))
        return value

    def validate_certification_text(self, value):
        if value and len(value) > 100:
            raise serializers.ValidationError(_("Certification text must not exceed 100 characters."))
        return value

    def validate_keywords(self, value):
        if not isinstance(value, list) or len(value) < 1 or len(value) > 20:
            raise serializers.ValidationError(_("At least 1 and maximum 20 keywords are required."))
        return value

    def validate_price_without_vat(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(_("Price must be positive."))
        return value

    def validate_unit(self, value):
        """The unit is a code from a fixed list, not free text.

        Which list applies depends on the category, so that check lives in
        ``validate()`` where both fields are in hand; here we only reject a value
        that is no unit at all.
        """
        if value and str(value).strip() not in dict(Listing.UNIT_CHOICES):
            raise serializers.ValidationError(_("Select a unit from the list."))
        return value

    def validate_minimum_quantity_or_scope(self, value):
        if value and not str(value).strip().isdigit():
            raise serializers.ValidationError(_("Minimum quantity must contain digits only."))
        return value

    # ---- cross-field validation ----
    def validate(self, attrs):
        # Merge with the existing instance so partial (PATCH/PUT) updates see the
        # full picture, mirroring the cookbook's `{ ...existing, ...payload }`.
        data = {**self._instance_dict(), **attrs}
        errors = {}

        if not data.get("owner_company"):
            errors["owner_company"] = _("Company is required.")
        if not data.get("nace_code"):
            errors["nace_code"] = _("NACE / ISIC classification is required.")
        if not data.get("visibility_scope"):
            errors["visibility_scope"] = _("Visibility scope is required.")

        listing_type = data.get("listing_type")
        category_type = data.get("category_type")

        # price -> currency
        if data.get("price_without_vat") is not None and not data.get("currency"):
            errors["currency"] = _("Currency is required when price is filled.")

        # unit -> category: a Service cannot be priced per pallet, nor a Product
        # per consultation.
        unit = (data.get("unit") or "").strip()
        if unit and unit not in dict(Listing.unit_choices_for(category_type)):
            errors["unit"] = (
                _("Choose a service unit, such as Per Hour or Per Project.")
                if category_type == Listing.SERVICE
                else _("Choose a product unit, such as Per Piece or Per Kilogram.")
            )

        # product image only for Product Offer
        if data.get("product_image_id"):
            if not (listing_type == Listing.OFFER and category_type == Listing.PRODUCT):
                errors["product_image_id"] = _("Product image is allowed only for Product Offer.")

        # Demand must not carry offer-only media in MVP
        if listing_type == Listing.DEMAND:
            if data.get("product_image_id"):
                errors["product_image_id"] = _("Demand must not contain product image.")
            if data.get("video_url"):
                errors["video_url"] = _("Demand must not contain video URL in MVP.")
            if data.get("certification_image_id"):
                errors["certification_image_id"] = _("Demand must not contain certification image in MVP.")

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _instance_dict(self):
        if self.instance is None:
            return {}
        return {
            "listing_type": self.instance.listing_type,
            "category_type": self.instance.category_type,
            "owner_company": self.instance.owner_company,
            "nace_code": self.instance.nace_code,
            "visibility_scope": self.instance.visibility_scope,
            "price_without_vat": self.instance.price_without_vat,
            "currency": self.instance.currency,
            "product_image_id": self.instance.product_image_id,
            "video_url": self.instance.video_url,
            "certification_image_id": self.instance.certification_image_id,
        }


class ListingReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingReaction
        fields = [
            "id",
            "listing",
            "from_user",
            "from_company",
            "to_user",
            "to_company",
            "message",
            "status",
            "created_at", 
            "updated_at",
        ]


class ListingAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingAuditLog
        fields = [
            "id",
            "listing",
            "action",
            "old_value",
            "new_value",
            "changed_by",
            "created_at",
        ]
