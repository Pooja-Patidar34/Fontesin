from django.db import models
from django.contrib.postgres.indexes import GinIndex
from accounts.models import Company,Tenant,User,NaceCode
from accounts.common.active_manager import ActiveManager
import uuid

class Listing(models.Model):
          OFFER = "offer"
          DEMAND ="demand"

          LISTING_TYPE_CHOICES=(
                  (OFFER, "offer"),
                  (DEMAND, "demand")
          )

          ACTIVE = "active"
          DRAFT = "draft"
          INACTIVE="inactive"
          SUSPENDED="suspended"

          STATUS_CHOICES=(
                  (ACTIVE,"active"),
                  (DRAFT,"draft"),
                  (INACTIVE,"inactive"),
                  (SUSPENDED,"suspended")
          )

          PRODUCT="product"
          SERVICE="service"

          CATEGORY_CHOICES=(
                 (PRODUCT,"product"),
                 (SERVICE,"service")
          )

          PUBLIC="public"
          MEMBERS="members"
          PRIVATE="private"

          VISIBILITY_CHOICES=(
                 (PUBLIC,"public"),
                 (MEMBERS,"members"),
                 (PRIVATE,"private")
          )

          CURRENCY_CHOICES=(
                 ("EUR","EUR"),
                 ("USD","USD"),
                 ("GBP","GBP"),
                 ("CZK","CZK"),
          )
          id=models.UUIDField(primary_key=True,default=uuid.uuid4 ,editable=False)
          listing_type=models.CharField(max_length=20,choices=LISTING_TYPE_CHOICES,db_index=True,)
          tenant=models.ForeignKey(Tenant,on_delete=models.PROTECT,related_name="listings")
          owner_company=models.ForeignKey(Company,on_delete=models.CASCADE,related_name="listings")
          owner_user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="listings")
          title=models.CharField(max_length=120)
          description=models.TextField()
          category_type=models.CharField(max_length=20,choices=CATEGORY_CHOICES,db_index=True)
          country=models.CharField(max_length=100,blank=True,default="",db_index=True)
          region=models.CharField(max_length=100,blank=True,default="",db_index=True)
          city=models.CharField(max_length=100,blank=True,default="",db_index=True)
          status=models.CharField(max_length=20,choices=STATUS_CHOICES,default=DRAFT,db_index=True)
          visibility_scope=models.CharField(max_length=20,choices=VISIBILITY_CHOICES,default=PUBLIC,db_index=True)
          module_id=models.CharField(max_length=50,db_index=True)
          suspension_reason = models.TextField(blank=True)
          module_specific_data = models.JSONField(default=dict,blank=True)
          nace_code = models.ForeignKey(NaceCode,on_delete=models.PROTECT,null=True,blank=True)
          price_without_vat = models.DecimalField(
            max_digits=14,
            decimal_places=2,
            null=True,
            blank=True,
          )

          currency = models.CharField(
            max_length=10,
            choices=CURRENCY_CHOICES,
            null=True,
            blank=True,
          )

          minimum_quantity_or_scope = models.CharField(
            max_length=255,
            null=True,
            blank=True,
          )

          unit = models.CharField(
            max_length=50,
            null=True,
            blank=True,
          )

          video_url = models.URLField(
            null=True,
            blank=True,
          )
          product_image_id = models.UUIDField(
            null=True,
            blank=True,
          )
          product_image = models.FileField(
            upload_to="listings/product_images/",
            null=True,
            blank=True,
          )

          certification_text = models.TextField(
            null=True,
            blank=True,
          )

          certification_image_id = models.UUIDField(
            null=True,
            blank=True,
          )
          certification_image = models.FileField(
            upload_to="listings/cert_images/",
            null=True,
            blank=True,
          )
          published_at = models.DateTimeField(null=True,blank=True,)
          suspended_at = models.DateTimeField(null=True,blank=True,)
          keywords = models.JSONField(default=list,blank=True)
          is_deleted = models.BooleanField(default=False, db_index=True)
          created_at=models.DateTimeField(auto_now_add=True)
          updated_at=models.DateTimeField(auto_now=True)

          objects = ActiveManager()
          all_objects = models.Manager()

          class Meta:
              ordering = ["-created_at"]
              indexes = [
                  # Cookbook Section 9: GIN index for keyword containment lookups.
                  GinIndex(fields=["keywords"], name="idx_listings_keywords"),
              ]
              # Trigram indexes on UPPER(title)/UPPER(description) - so browse/search
              # `icontains` (which Django wraps in UPPER()) is index-backed - are
              # created via raw SQL in migration 0006 (Django's OpClass emits invalid
              # SQL for functional expression + opclass GIN indexes).
              constraints = [
                  models.CheckConstraint(
                      name="listings_price_currency_check",
                      condition=(
                          models.Q(price_without_vat__isnull=True)
                          | models.Q(currency__isnull=False)
                      ),
                  ),
                  models.CheckConstraint(
                      name="listings_product_image_check",
                      condition=(
                          models.Q(product_image_id__isnull=True)
                          | (
                              models.Q(listing_type="offer")
                              & models.Q(category_type="product")
                          )
                      ),
                  ),
              ]

          def __str__(self):
              return self.title


class ListingReaction(models.Model):

    NEW = "new"
    READ = "read"
    REPLIED = "replied"
    CLOSED = "closed"

    STATUS_CHOICES = (
        (NEW, "New"),
        (READ, "Read"),
        (REPLIED, "Replied"),
        (CLOSED, "Closed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="reactions",
        db_index=True
    )

    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_listing_reactions",
    )

    from_company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="sent_listing_reactions",
    )

    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_listing_reactions",

    )

    to_company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="received_listing_reactions",
    )

    message = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=NEW,
        db_index=True
        
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
       ordering = ["-created_at"]

       constraints = [
        models.UniqueConstraint(
            fields=["listing", "from_user"],
            name="unique_listing_reaction",
        )
    ]
    def __str__(self):
      return f"{self.from_user.email} -> {self.listing.title}"
    
class ListingAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=100, db_index=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="listing_audit_logs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.action} - {self.listing.title}"

