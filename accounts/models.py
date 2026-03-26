from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.utils.text import slugify
from accounts.constants import CompanyClassificationChoices


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Tenant.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}-{counter}"
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

    # ---- Address ----
    address_line1 = models.CharField(max_length=255, null=True, blank=True)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=150, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    # ---- Contact ----
    phone = models.CharField(max_length=50, null=True, blank=True)
    phone_secondary = models.CharField(max_length=50, null=True, blank=True)
    fax = models.CharField(max_length=50, null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)

    owner_user = models.ForeignKey("User",null=True,blank=True,related_name="owned_companies",on_delete=models.SET_NULL)
    consultant = models.ForeignKey("User",null=True,blank=True,related_name="consulting_companies",on_delete=models.SET_NULL)
    certification_status = models.CharField(max_length=50,default="uncertified")
    certified_by = models.ForeignKey("User",null=True,blank=True,related_name="certified_companies",on_delete=models.SET_NULL)

    certified_at = models.DateTimeField(null=True,blank=True)

    # ---- Status ----
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "name"]),
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
    preferred_language = models.CharField(max_length=10, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    photo_url = models.URLField(max_length=500, null=True, blank=True)

    # ---- Address ----
    address_line1 = models.CharField(max_length=255, null=True, blank=True)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=150, null=True, blank=True)
    state_region = models.CharField(max_length=150, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    owner = models.ForeignKey("self",null=True,blank=True,related_name="commercial_children",on_delete=models.SET_NULL)

    coordinator = models.ForeignKey("self",null=True,blank=True,related_name="management_children",on_delete=models.SET_NULL)

    territory_country = models.CharField(max_length=2, null=True, blank=True)
    territory_region = models.CharField(max_length=100, null=True, blank=True)
    territory_city = models.CharField(max_length=100, null=True, blank=True)

    consultant_sub_role = models.CharField(max_length=20,null=True,blank=True)

    subscription_plan = models.CharField(max_length=20,null=True,blank=True)

    # ---- Security / KYC ----
    kyc_id_hash = models.CharField(max_length=255, null=True, blank=True)

    # ---- System ----
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        unique_together = ("tenant", "email")
        indexes = [
            models.Index(fields=["tenant", "email"]),
        ]

    def __str__(self):
        return self.email


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)


class Role(models.Model):
    ADMIN = "ADMIN"
    COMPANY = "COMPANY"
    USER = "USER"

    ROLE_CHOICES = (
        (ADMIN, "Admin"),
        (COMPANY, "Company"),
        (USER, "User"),
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