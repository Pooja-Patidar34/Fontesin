from decimal import Decimal
from django.db import models
from accounts.models import User
from django.db.models import Q


class Certification(models.Model):

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=255)

    type = models.CharField(max_length=100, db_index=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CommercialPlan(models.Model):

    BILLING_PERIOD = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=200, blank=True, default="")
    icon = models.CharField(max_length=10, blank=True, default="")

    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD")

    billing_period = models.CharField(
        max_length=10,
        choices=BILLING_PERIOD,
        default="yearly"
    )

    badge_text = models.CharField(max_length=50, blank=True, default="")
    badge_style = models.CharField(max_length=20, blank=True, default="")

    features = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)
    comparison = models.JSONField(default=dict, blank=True)

    best_for = models.CharField(max_length=300, blank=True, default="")
    best_for_style = models.CharField(max_length=20, blank=True, default="")

    sort_order = models.IntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name

    @property
    def monthly_price(self):
        if self.price and self.billing_period == "yearly":
            return (self.price / Decimal("12")).quantize(Decimal("0.01"))
        return self.price

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > 0:
            return round((1 - self.price / self.original_price) * 100)
        return 0

    @property
    def savings(self):
        if self.original_price:
            return self.original_price - self.price
        return 0


class Subscription(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("trial", "Trial"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        null=True,
        blank=True,
    )

    certification = models.ForeignKey(
        "billing.Certification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    plan = models.ForeignKey(
        "billing.CommercialPlan",
        on_delete=models.PROTECT
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created"
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField(null=True, blank=True)

    trial_end = models.DateTimeField(null=True, blank=True)

    grace_period_end = models.DateTimeField(null=True, blank=True)

    auto_renew = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=["active", "trial"]),
                name="unique_active_subscription_per_user"
            )
        ]


class Invoice(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.CASCADE
    )

    invoice_number = models.CharField(max_length=100, unique=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    currency = models.CharField(max_length=10, default="USD")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    variable_symbol = models.CharField(max_length=20, blank=True, default="")
    specific_symbol = models.CharField(max_length=20, blank=True, default="")
    payment_reference = models.CharField(max_length=100, blank=True, default="")

    due_date = models.DateTimeField()

    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # ── Snapshots (frozen at invoice creation, never edited afterward) ──
    # JSON shape mirrors the bank-details dict in accounts/view/website.py:
    # { profile, currency, bank_name, bank_address, aba_routing, swift,
    #   account_label, account_number, account_kind, beneficiary_name,
    #   beneficiary_address, remittance_reference }
    bank_snapshot = models.JSONField(default=dict, blank=True)

    # JSON shape:
    # { name, email, phone, country, address_line1, address_line2, city,
    #   state_region, postal_code, full_address, tenant_name }
    sender_snapshot = models.JSONField(default=dict, blank=True)

    # FX info — explicit columns for queryability/aggregation.
    fx_source_currency = models.CharField(max_length=10, blank=True, default="")
    fx_source_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fx_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)


class WebhookEvent(models.Model):

    event_id = models.CharField(max_length=255, unique=True)

    event_type = models.CharField(max_length=100)

    payload = models.JSONField()

    processed_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]

    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.CASCADE
    )

    transaction_id = models.CharField(max_length=255, unique=True)

    webhook_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    currency = models.CharField(max_length=10)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )

    created_at = models.DateTimeField(auto_now_add=True)

