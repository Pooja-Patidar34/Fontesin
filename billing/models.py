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

    name = models.CharField(max_length=100)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    currency = models.CharField(max_length=10)

    billing_period = models.CharField(
        max_length=10,
        choices=BILLING_PERIOD
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("trial", "Trial"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
    ]

    certification = models.ForeignKey(
        "billing.Certification",
        on_delete=models.CASCADE
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
                fields=["certification"],
                condition=Q(status__in=["active", "trial"]),
                name="unique_active_subscription_per_certification"
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

    currency = models.CharField(max_length=10)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    due_date = models.DateTimeField()

    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


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

    transaction_id = models.CharField(max_length=255)

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

