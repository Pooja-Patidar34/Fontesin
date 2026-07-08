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

    # The company this plan is attached to. Plans are per-company (a Business
    # User picks a plan for EACH company they own), so feature-gating,
    # geographic scope, and commission attribution all resolve through the
    # subscription's company rather than the buying user. `user` still records
    # WHO pays (the company's owner). Nullable to keep legacy/global rows and
    # a brief pre-company window valid; the unique-active constraint below is
    # scoped to non-null companies.
    company = models.ForeignKey(
        "accounts.Company",
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

    # Snapshot of the plan's billing period at the moment this subscription
    # was created. We don't read it back off `plan.billing_period` because
    # an admin editing the plan template later (yearly → monthly) would
    # otherwise retroactively flip every subscription pointing at that
    # plan. Defaults to "yearly" so legacy rows without an explicit value
    # match the most-common case; the migration backfills existing rows
    # from their plan's current period at one-shot time.
    billing_period = models.CharField(
        max_length=10,
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        default="yearly",
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
            # At most one active/trial subscription PER COMPANY. Plans are now
            # company-scoped, so a Business User can hold several active
            # subscriptions at once (one per company) — but never two live
            # plans on the same company. Scoped to non-null companies so
            # legacy/global rows without a company aren't caught.
            models.UniqueConstraint(
                fields=["company"],
                condition=Q(status__in=["active", "trial"]) & Q(company__isnull=False),
                name="unique_active_subscription_per_company"
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


class ConsultantCommission(models.Model):
    """Commission owed to a consultant when a business user whose primary
    company they created subscribes to a paid plan and the admin approves it.

    One row per (consultant, subscription) — re-approval is idempotent. The
    amount/currency are frozen at approval time so later invoice edits or FX
    drift don't retroactively change a payout. `status` tracks the disbursement
    lifecycle (pending until the admin records the actual payout).
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    consultant = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="commissions_earned",
    )
    business_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="commissions_generated",
    )
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        related_name="referral_commissions",
        null=True,
        blank=True,
    )
    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.PROTECT,
        related_name="commissions",
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        related_name="commissions",
        null=True,
        blank=True,
    )

    subscription_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["consultant", "subscription"],
                name="unique_consultant_subscription_commission",
            ),
        ]
        ordering = ["-created_at"]

    @property
    def admin_share(self):
        """Platform share = subscription amount minus the consultant's cut.
        Same currency as `subscription_amount` / `commission_amount`."""
        return (self.subscription_amount - self.commission_amount).quantize(Decimal("0.01"))

    @property
    def admin_share_percent(self):
        """100 - consultant's rate. Useful for label rendering in templates."""
        return (Decimal("100") - self.rate_percent).quantize(Decimal("0.01"))

    def __str__(self):
        return (
            f"{self.consultant.email} <- {self.commission_amount} {self.currency} "
            f"({self.business_user.email}, {self.status})"
        )
