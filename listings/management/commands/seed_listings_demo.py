"""
Seed the four canonical demo listings for the MVP Phase 3 investor/demo
scenario (cookbook Section 15, items 40-43 + Day 14):

    Product Offer · Service Offer · Product Demand · Service Demand

Idempotent: re-running updates the same rows (matched by owner + title).
Pass --owner <email> to pick the owning Business User, otherwise the first
business_user that owns a company is used.

    python manage.py seed_listings_demo
    python manage.py seed_listings_demo --owner owner@example.com
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User, Company, NaceCode
from listings.models import Listing


DEMO = [
    dict(
        key="Demo Product Offer",
        listing_type=Listing.OFFER, category_type=Listing.PRODUCT,
        description="Bulk stainless-steel pipes, DIN-certified, ready for export across the EU.",
        keywords=["steel", "pipes", "export"],
        price_without_vat="1250.00", currency="EUR",
        minimum_quantity_or_scope="500", unit="metre",
    ),
    dict(
        key="Demo Service Offer",
        listing_type=Listing.OFFER, category_type=Listing.SERVICE,
        description="On-site industrial welding and inspection service for manufacturing plants.",
        keywords=["welding", "inspection", "on-site"],
        price_without_vat="80.00", currency="EUR",
        minimum_quantity_or_scope="1", unit="day",
    ),
    dict(
        key="Demo Product Demand",
        listing_type=Listing.DEMAND, category_type=Listing.PRODUCT,
        description="Seeking a long-term supplier of food-grade aluminium sheets for packaging.",
        keywords=["aluminium", "packaging", "supplier"],
    ),
    dict(
        key="Demo Service Demand",
        listing_type=Listing.DEMAND, category_type=Listing.SERVICE,
        description="Looking for a certified logistics partner for temperature-controlled EU transport.",
        keywords=["logistics", "cold-chain", "transport"],
    ),
]


class Command(BaseCommand):
    help = "Create/update the four canonical demo listings for the investor demo."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Email of the Business User to own the demo listings.")

    def handle(self, *args, **options):
        owner = self._resolve_owner(options.get("owner"))
        company = Company.objects.filter(owner_user=owner).first()
        if not company:
            raise CommandError(f"User {owner.email} owns no company; cannot seed listings.")
        nace = NaceCode.objects.filter(is_active=True).order_by("code").first()

        created, updated = 0, 0
        for spec in DEMO:
            defaults = dict(
                owner_user=owner, tenant=owner.tenant, owner_company=company,
                nace_code=nace, module_id="products_services",
                title=spec["key"], description=spec["description"],
                keywords=spec["keywords"], listing_type=spec["listing_type"],
                category_type=spec["category_type"], visibility_scope=Listing.PUBLIC,
                status=Listing.ACTIVE, published_at=timezone.now(),
                price_without_vat=spec.get("price_without_vat"),
                currency=spec.get("currency"),
                minimum_quantity_or_scope=spec.get("minimum_quantity_or_scope", ""),
                unit=spec.get("unit", ""),
            )
            obj, was_created = Listing.objects.update_or_create(
                owner_user=owner, title=spec["key"], defaults=defaults,
            )
            created += was_created
            updated += not was_created
            self.stdout.write(f"  {'created' if was_created else 'updated'}: {obj.title}")

        self.stdout.write(self.style.SUCCESS(
            f"Demo listings ready for {owner.email} / {company.name} "
            f"({created} created, {updated} updated)."
        ))

    def _resolve_owner(self, email):
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f"No user with email {email}.")
        for c in Company.objects.exclude(owner_user=None).select_related("owner_user__role"):
            role_code = (getattr(c.owner_user.role, "code", "") or "").lower()
            if role_code == "business_user":
                return c.owner_user
        raise CommandError("No business_user-owned company found; pass --owner <email>.")
