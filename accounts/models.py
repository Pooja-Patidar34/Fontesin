from django.db import models
from django.db.models import Q
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.utils.text import slugify
from accounts.constants import (
    CompanyClassificationChoices,
    CompanyEntityTypeChoices,
    CountryChoices,
    EmployeeCountRangeChoices,
    LanguageChoices,
)
from accounts.common.active_manager import ActiveManager
from django.utils import timezone


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, null=True, blank=True, unique=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    def __str__(self):
        
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            max_slug_len = self._meta.get_field("slug").max_length
            base_slug = slugify(self.name)[:max_slug_len]
            slug = base_slug
            counter = 1

            while Tenant.all_objects.filter(slug=slug).exclude(id=self.id).exists():
                suffix = f"-{counter}"
                slug = base_slug[: max_slug_len - len(suffix)] + suffix
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="companies"
    )

    # ---- Core Identity ----
    name = models.CharField(max_length=255)
    registration_id = models.CharField(max_length=100, null=True, blank=True)

    classification = models.CharField(
        max_length=50,
        choices=CompanyClassificationChoices.CHOICES,
        null=True,
        blank=True,
    )

    entity_type = models.CharField(
        max_length=30,
        choices=CompanyEntityTypeChoices.CHOICES,
        null=True,
        blank=True,
    )

    # ---- Address ----
    # address_line1 carries the Street; house_number is captured separately so
    # the UI can render them as two side-by-side fields per the onboarding form.
    address_line1 = models.CharField(max_length=255, null=True, blank=True)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    house_number = models.CharField(max_length=30, null=True, blank=True)
    district = models.CharField(max_length=120, null=True, blank=True)
    region = models.CharField(max_length=120, null=True, blank=True)
    city = models.CharField(max_length=150, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    # ---- Business attributes ----
    year_established = models.PositiveIntegerField(null=True, blank=True)
    industry_code = models.CharField(max_length=20, null=True, blank=True)
    keywords = models.CharField(max_length=500, null=True, blank=True)
    employee_count_range = models.CharField(
        max_length=20,
        choices=EmployeeCountRangeChoices.CHOICES,
        null=True,
        blank=True,
    )

    # ---- Contact ----
    phone = models.CharField(max_length=50, null=True, blank=True)
    phone_secondary = models.CharField(max_length=50, null=True, blank=True)
    fax = models.CharField(max_length=50, null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)
    contact_email = models.EmailField(max_length=254, null=True, blank=True)

    # ---- Branding ----
    logo = models.FileField(upload_to="company_logos/", null=True, blank=True)

    owner_user = models.ForeignKey("User",null=True,blank=True,related_name="owned_companies",on_delete=models.SET_NULL)
    consultant = models.ForeignKey("User",null=True,blank=True,related_name="consulting_companies",on_delete=models.SET_NULL)
    certification_status = models.CharField(max_length=50,default="uncertified")
    certified_by = models.ForeignKey("User",null=True,blank=True,related_name="certified_companies",on_delete=models.SET_NULL)

    certified_at = models.DateTimeField(null=True,blank=True)

    # ---- Status ----
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "name"]),
        ]
        constraints = [
            # registration_id is the legal identity of a company (company-house
            # number, EIN, CIN, etc.). Two rows sharing it ARE the same entity,
            # so enforce global uniqueness — but only when a value is provided.
            # Null and empty strings are excluded so the 169 existing rows
            # without a registration_id continue to coexist.
            models.UniqueConstraint(
                fields=["registration_id"],
                condition=Q(registration_id__isnull=False) & ~Q(registration_id__exact=""),
                name="unique_company_registration_id",
            ),
        ]

    def __str__(self):
        return self.name


class CompanyEnrichment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="enrichment"
    )

    # ---- Industry Codes ----
    naics_code = models.CharField(max_length=10, null=True, blank=True)
    naics_description = models.CharField(max_length=255, null=True, blank=True)

    sic2_code = models.CharField(max_length=10, null=True, blank=True)
    sic4_code = models.CharField(max_length=10, null=True, blank=True)
    sic6_code = models.CharField(max_length=10, null=True, blank=True)

    sic2_description = models.CharField(max_length=255, null=True, blank=True)
    sic4_description = models.CharField(max_length=255, null=True, blank=True)
    sic6_description = models.CharField(max_length=255, null=True, blank=True)
    sic_division = models.CharField(max_length=50, null=True, blank=True)

    # ---- Sales & Employees ----
    exact_sales_volume = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    sales_range = models.CharField(max_length=100, null=True, blank=True)
    sales_code = models.CharField(max_length=10, null=True, blank=True)

    exact_employee_count = models.IntegerField(null=True, blank=True)
    employee_range = models.CharField(max_length=100, null=True, blank=True)
    employee_code = models.CharField(max_length=10, null=True, blank=True)

    # ---- Business Attributes ----
    business_type = models.CharField(max_length=100, null=True, blank=True)
    location_type = models.CharField(max_length=50, null=True, blank=True)

    year_started = models.IntegerField(null=True, blank=True)
    month_started = models.IntegerField(null=True, blank=True)

    franchise = models.BooleanField(null=True, blank=True)
    chain = models.BooleanField(null=True, blank=True)
    home_office = models.BooleanField(null=True, blank=True)

    # ---- Census / Area Data ----
    median_income_census_area = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    mean_housing_census_area = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    # ---- Analytics ----
    ebiz_score = models.CharField(max_length=20, null=True, blank=True)
    ebiz_decile = models.CharField(max_length=20, null=True, blank=True)
    ebiz_percentile = models.CharField(max_length=20, null=True, blank=True)

    # ---- Telecom / IT ----
    monthly_telco_spend = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    monthly_data_spend = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    number_of_lines = models.IntegerField(null=True, blank=True)
    number_of_pcs = models.IntegerField(null=True, blank=True)

    # ---- Flags ----
    is_manufacturing = models.BooleanField(null=True, blank=True)
    is_subsidiary = models.BooleanField(null=True, blank=True)
    is_foreign_company = models.BooleanField(null=True, blank=True)
    fortune_company = models.BooleanField(null=True, blank=True)

    # ---- Import Metadata ----
    source = models.CharField(max_length=100, null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Enrichment"
        verbose_name_plural = "Company Enrichments"

    def __str__(self):
        return f"Enrichment for {self.company.name}"


class UserManager(BaseUserManager):
    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="users"
    )

    role = models.ForeignKey(
        "Role",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    primary_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_users"
    )

    # ---- Identity ----
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    phone = models.CharField(max_length=50, null=True, blank=True)
    national_prefix = models.CharField(max_length=10, null=True, blank=True)

    # ---- Personal (Client-required) ----
    birth_date = models.DateField(null=True, blank=True)
    ethnicity = models.CharField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)

    # ---- Profile ----
    preferred_language = models.CharField(max_length=10, choices=LanguageChoices.CHOICES, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    photo_url = models.URLField(max_length=500, null=True, blank=True)

    # ---- Address ----
    address_line1 = models.CharField(max_length=255, null=True, blank=True)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=150, null=True, blank=True)
    state_region = models.CharField(max_length=150, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, choices=CountryChoices.CHOICES, null=True, blank=True)

    owner = models.ForeignKey("self",null=True,blank=True,related_name="commercial_children",on_delete=models.SET_NULL)

    coordinator = models.ForeignKey("self",null=True,blank=True,related_name="management_children",on_delete=models.SET_NULL)

    territory_country = models.CharField(max_length=2, null=True, blank=True)
    territory_region = models.CharField(max_length=100, null=True, blank=True)
    territory_city = models.CharField(max_length=100, null=True, blank=True)

    consultant_sub_role = models.CharField(max_length=20,null=True,blank=True)

    subscription_plan = models.CharField(max_length=20,null=True,blank=True)

    # ---- Application Fields ----
    nationality = models.CharField(max_length=100, null=True, blank=True)
    linkedin_url = models.URLField(max_length=500, null=True, blank=True)
    current_position = models.CharField(max_length=255, null=True, blank=True)
    years_of_experience = models.CharField(max_length=50, null=True, blank=True)
    primary_industry = models.CharField(max_length=100, null=True, blank=True)
    professional_summary = models.TextField(null=True, blank=True)

    # Company info from application
    applied_company_name = models.CharField(max_length=255, null=True, blank=True)
    applied_company_reg_number = models.CharField(max_length=100, null=True, blank=True)
    applied_country_of_incorporation = models.CharField(max_length=100, null=True, blank=True)
    applied_legal_form = models.CharField(max_length=100, null=True, blank=True)
    applied_year_founded = models.IntegerField(null=True, blank=True)
    applied_num_employees = models.CharField(max_length=50, null=True, blank=True)
    applied_company_website = models.URLField(max_length=500, null=True, blank=True)

    # Role-specific
    target_region = models.CharField(max_length=255, null=True, blank=True)
    franchise_type = models.CharField(max_length=100, null=True, blank=True)
    motivation = models.TextField(null=True, blank=True)
    network_connections = models.TextField(null=True, blank=True)
    expected_companies = models.CharField(max_length=100, null=True, blank=True)
    reference_1 = models.CharField(max_length=255, null=True, blank=True)
    reference_2 = models.CharField(max_length=255, null=True, blank=True)

    # Application status
    application_status = models.CharField(max_length=20, default="pending", null=True, blank=True)

    # ---- Security / KYC ----
    kyc_id_hash = models.CharField(max_length=255, null=True, blank=True)

    # ---- System ----
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    all_objects = BaseUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        unique_together = ("tenant", "email")
        indexes = [
            models.Index(fields=["tenant", "email"]),
        ]

    def __str__(self):
        return self.email


class DueDiligence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        "User",
        on_delete=models.CASCADE,
        related_name="due_diligence"
    )

    # Q1: Criminal offence
    criminal_offence = models.CharField(max_length=10, default="no")
    criminal_offence_details = models.TextField(null=True, blank=True)

    # Q2: Regulatory sanctions
    regulatory_sanctions = models.CharField(max_length=10, default="no")
    regulatory_sanctions_details = models.TextField(null=True, blank=True)

    # Q3: Politically Exposed Person
    is_pep = models.CharField(max_length=10, default="no")

    # Q4: Insolvency history
    insolvency_history = models.CharField(max_length=10, default="no")
    insolvency_history_details = models.TextField(null=True, blank=True)

    # Q5: Financial resources
    sufficient_financial_resources = models.CharField(max_length=10, default="yes")

    # Q6: Legal disputes
    pending_legal_disputes = models.CharField(max_length=10, default="no")
    pending_legal_disputes_details = models.TextField(null=True, blank=True)

    # Q7: Competitor interest
    competitor_interest = models.CharField(max_length=10, default="no")
    competitor_interest_details = models.TextField(null=True, blank=True)

    # Q8: Contractual obligations
    contractual_obligations = models.CharField(max_length=10, default="no")
    contractual_obligations_details = models.TextField(null=True, blank=True)

    # Declarations
    declared_truthful = models.BooleanField(default=False)
    declared_update = models.BooleanField(default=False)
    accepted_terms = models.BooleanField(default=False)
    consented_aml = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"DueDiligence - {self.user.email}"


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)


class Role(models.Model):
    ADMIN = "ADMIN"
    BUSINESS_USER = "BUSINESS_USER"
    CONSULTANT = "CONSULTANT"
    COORDINATOR = "COORDINATOR"
    FRANCHISE = "FRANCHISE"

    ROLE_CHOICES = (
        (ADMIN, "Admin"),
        (BUSINESS_USER, "Business User"),
        (CONSULTANT, "Consultant"),
        (COORDINATOR, "Coordinator"),
        (FRANCHISE, "Franchise Partner"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100)
    permissions = models.ManyToManyField(
        Permission,
        related_name="roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    code = models.CharField(max_length=50, blank=True, null=True)

    tier_level = models.IntegerField()

    is_franchise = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")


class UserCompany(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "company")
        default_permissions = ()


class UserCompanyRole(models.Model):
    user_company = models.ForeignKey(UserCompany, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user_company", "role")
        default_permissions = ()


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="audit_logs"
    )

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()

    metadata = models.JSONField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


    def save(self, *args, **kwargs):
        # Allow only INSERT, block UPDATE
        if not self._state.adding:
            raise RuntimeError("Audit logs are immutable")
        super().save(*args, **kwargs)
        
        
class CertificationLog(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE
    )

    action = models.CharField(max_length=50)

    performed_by = models.ForeignKey(
        "User",
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at


class SavedFilter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_filters")
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("user", "name")
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def __str__(self):
        return self.name


class CompanyConnection(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="company_connections")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="connection_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "company")
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user.email} → {self.company.name} ({self.status})"
