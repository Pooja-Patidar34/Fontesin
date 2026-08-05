from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.utils.text import slugify
from accounts.constants import (
    CompanyClassificationChoices,
    CompanyEntityTypeChoices,
    ConsultantAssignmentStatus,
    ConsultantType,
    ContractStatus,
    CountryChoices,
    EmployeeCountRangeChoices,
    FranchiseApplicationStatus,
    FranchiseFeeStatus,
    FranchiseLevel,
    FranchiseUnitStatus,
    SupportedLocale,
)
from accounts.common.active_manager import ActiveManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Tenant(models.Model):
    """Org-partition boundary AND franchise-tree node.

    A Tenant row is a franchise node when `franchise_level` is set; a row with a
    null level is a plain partition (the legacy meaning, unchanged). The MVP
    franchise hierarchy (spec §8) is layered on here instead of a standalone
    table: `parent` builds the tree, the `territory_*` fields carry the assigned
    area, and `franchise_status` drives the access lifecycle. "Franchise" is the
    user-facing name for this model throughout the UI.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, null=True, blank=True, unique=True)

    is_active = models.BooleanField(default=True)

    # ---- Franchise hierarchy (spec §8.1) ----
    # Parent node in the franchise tree. Null for a Master (top of a tree) or a
    # legacy non-franchise partition. PROTECT so a node can't be hard-deleted
    # out from under its children (soft-delete via `is_deleted` instead).
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    franchise_level = models.CharField(
        max_length=20,
        choices=FranchiseLevel.CHOICES,
        null=True,
        blank=True,
    )
    # The franchise holder (the user who owns/operates this node) and the
    # primary company behind it. Both optional until the node is set up.
    owner_user = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="owned_franchises",
        null=True,
        blank=True,
    )
    owner_company = models.ForeignKey(
        "Company",
        on_delete=models.SET_NULL,
        related_name="owned_franchises",
        null=True,
        blank=True,
    )

    # ---- Assigned territory (spec §8.5, denormalised) ----
    # Territory is stored as ISO-alpha-2 country + free-text subdivisions,
    # matching the existing convention on User (territory_country, etc.). An
    # empty deeper level means "the whole of the level above" (e.g. blank city
    # = the whole region). These four fields together form the exclusivity key
    # for Micro-Franchises.
    territory_country = models.CharField(max_length=2, blank=True, default="")
    territory_region = models.CharField(max_length=120, blank=True, default="")
    territory_city = models.CharField(max_length=120, blank=True, default="")
    territory_local_area = models.CharField(max_length=120, blank=True, default="")

    # ---- Exclusivity & lifecycle (spec §8.1, §9.2) ----
    is_exclusive = models.BooleanField(default=False)
    franchise_status = models.CharField(
        max_length=20,
        choices=FranchiseUnitStatus.CHOICES,
        null=True,
        blank=True,
    )
    franchise_fee_status = models.CharField(
        max_length=20,
        choices=FranchiseFeeStatus.CHOICES,
        null=True,
        blank=True,
    )
    contract_status = models.CharField(
        max_length=20,
        choices=ContractStatus.CHOICES,
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="approved_franchises",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="created_franchises",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            # Micro-Franchise exclusivity (spec §5.3, §11.2, Rule 7): at most one
            # ACTIVE Micro-Franchise per territory. Enforced at the DB level so a
            # race between two activations can't create a duplicate. Legacy
            # partitions and non-micro nodes are excluded by the condition.
            #
            # Compared on Lower(Trim(...)) rather than the raw columns so that
            # "Berlin", "berlin" and " Berlin " are one territory, matching
            # `territory_key`. Without this, case/whitespace variants slipped
            # past both this constraint and the clean() clash check and broke
            # Rule 7. `save()` strips the values on write, so the Trim() here is
            # really only covering rows written before that (bulk_create, raw
            # SQL, legacy data).
            models.UniqueConstraint(
                Lower(Trim("territory_country")),
                Lower(Trim("territory_region")),
                Lower(Trim("territory_city")),
                Lower(Trim("territory_local_area")),
                condition=Q(
                    franchise_level=FranchiseLevel.MICRO,
                    franchise_status=FranchiseUnitStatus.ACTIVE,
                    is_deleted=False,
                ),
                name="unique_active_micro_franchise_per_territory",
            ),
        ]

    def __str__(self):

        return self.name

    # ---- Franchise helpers ----
    @property
    def is_franchise_node(self):
        """True when this Tenant participates in the franchise tree."""
        return self.franchise_level is not None

    @property
    def is_franchise_active(self):
        """A node only holds full franchise rights while ACTIVE (spec §9.2)."""
        return self.franchise_status == FranchiseUnitStatus.ACTIVE

    @property
    def is_franchise_suspended(self):
        """Suspended: historical data stays readable, active rights are gone."""
        return self.franchise_status == FranchiseUnitStatus.SUSPENDED

    @property
    def territory_key(self):
        """Normalised (country, region, city, local_area) tuple used for
        territory comparison and exclusivity."""
        return (
            (self.territory_country or "").strip().upper(),
            (self.territory_region or "").strip().casefold(),
            (self.territory_city or "").strip().casefold(),
            (self.territory_local_area or "").strip().casefold(),
        )

    def _normalise_territory(self):
        """Canonicalise the territory columns before they are persisted.

        Whitespace is collapsed (leading, trailing and internal) so " Berlin",
        "Berlin" and "Ganga  Ghat" vs "Ganga Ghat" are stored identically — the
        same rule `canonical_territory()` already applies on the franchise view
        path, applied here so writes that bypass those views are canonical too.
        The country code is upper-cased because it is an ISO-3166 code, not free
        text.

        Casing of region/city/local_area is deliberately left as the user typed
        it — those values are shown in the franchise tree and reports, so folding
        them would change what the UI displays. The case-insensitivity
        exclusivity needs is handled by the Lower(Trim(...)) unique constraint
        and the __iexact lookups in `clean()` instead."""
        self.territory_country = (self.territory_country or "").strip().upper()
        self.territory_region = " ".join((self.territory_region or "").split())
        self.territory_city = " ".join((self.territory_city or "").split())
        self.territory_local_area = " ".join((self.territory_local_area or "").split())

    def is_territory_within(self, other):
        """True when this node's territory is contained in `other`'s (spec Rule
        3). A blank level on the parent means "no constraint at that level", so
        a parent covering a whole country contains any region/city inside it."""
        for mine, theirs in zip(self.territory_key, other.territory_key):
            if not theirs:
                # Parent doesn't constrain this level (or anything deeper).
                break
            if mine != theirs:
                return False
        return True

    def get_ancestors(self):
        """Return ancestor nodes from immediate parent up to the root (Master).

        Upward visibility is deliberately limited (spec §7.2) — callers should
        expose only basic info from these, never their business data."""
        ancestors = []
        node = self.parent
        seen = {self.id}
        while node is not None and node.id not in seen:
            ancestors.append(node)
            seen.add(node.id)
            node = node.parent
        return ancestors

    def get_descendant_ids(self, include_self=False):
        """Return the ids of every node in this node's subtree.

        This is the backbone of downward visibility (spec §7.1): a franchise
        holder sees its own node plus everything beneath it, and nothing on a
        parallel branch. Iterative BFS over `children` (no DB CTE dependency)."""
        collected = set()
        frontier = [self.id]
        while frontier:
            batch = (
                Tenant.objects.filter(parent_id__in=frontier)
                .values_list("id", flat=True)
            )
            batch = [tid for tid in batch if tid not in collected]
            collected.update(batch)
            frontier = batch
        if include_self:
            collected.add(self.id)
        return collected

    def _ensure_slug(self):
        """Derive a unique slug from the name when none was supplied."""
        if self.slug:
            return
        max_slug_len = self._meta.get_field("slug").max_length
        base_slug = slugify(self.name)[:max_slug_len]
        slug = base_slug
        counter = 1

        while Tenant.all_objects.filter(slug=slug).exclude(id=self.id).exists():
            suffix = f"-{counter}"
            slug = base_slug[: max_slug_len - len(suffix)] + suffix
            counter += 1

        self.slug = slug

    def clean(self):
        """Validate franchise-tree invariants (spec §10, §11, §15).

        Only runs for franchise nodes (level set). Django doesn't call this on
        every save() — it backs ModelForm/full_clean() and the franchise
        service layer, giving friendly errors ahead of the DB constraints."""
        from django.core.exceptions import ValidationError

        if self.franchise_level is None:
            return  # Plain partition — no franchise rules apply.

        # Rule 1 (structural): a node can't be its own parent.
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": _("A franchise cannot be its own parent.")})

        is_master = self.franchise_level == FranchiseLevel.MASTER

        if is_master and self.parent_id:
            raise ValidationError(
                {"parent": _("A Master Franchise sits at the top of a tree and has no parent.")}
            )
        if not is_master and not self.parent_id:
            raise ValidationError(
                {"parent": _("A sub-franchise must have a parent franchise (spec §10.2).")}
            )

        if self.parent_id:
            parent = self.parent
            # Rule 2: the parent must itself be a franchise node and be ACTIVE.
            if not parent.is_franchise_node:
                raise ValidationError(
                    {"parent": _("The selected parent is not a franchise node.")}
                )
            if not parent.is_franchise_active:
                raise ValidationError(
                    {"parent": _("The parent franchise must be ACTIVE before adding a sub-franchise (spec Rule 2).")}
                )
            # Depth: child must be strictly deeper than parent (gaps allowed).
            child_rank = FranchiseLevel.RANK.get(self.franchise_level, 0)
            parent_rank = FranchiseLevel.RANK.get(parent.franchise_level, 0)
            if child_rank <= parent_rank:
                raise ValidationError(
                    {"franchise_level": _("A sub-franchise must be a lower tier than its parent.")}
                )
            # Rule 3: the child territory must sit inside the parent territory.
            if not self.is_territory_within(parent):
                raise ValidationError(
                    _("The franchise territory must be inside the parent franchise's territory (spec Rule 3).")
                )

        # Exclusivity (spec §11.1): an active franchise unit is exclusive within
        # its territory AND level — at most one ACTIVE franchise of a given level
        # per territory. Enforced for every level here; the Micro level ALSO has
        # a DB unique constraint as an authoritative backstop (spec §5.3/§11.2).
        # Matched case-insensitively on the stripped values (same normalisation
        # as `territory_key` and the DB constraint) — an exact match on the raw
        # columns let " berlin" pass as a different territory from "Berlin".
        if self.franchise_status == FranchiseUnitStatus.ACTIVE:
            clash = (
                Tenant.objects.filter(
                    franchise_level=self.franchise_level,
                    franchise_status=FranchiseUnitStatus.ACTIVE,
                    territory_country__iexact=(self.territory_country or "").strip(),
                    territory_region__iexact=(self.territory_region or "").strip(),
                    territory_city__iexact=(self.territory_city or "").strip(),
                    territory_local_area__iexact=(self.territory_local_area or "").strip(),
                )
                .exclude(id=self.id)
                .exists()
            )
            if clash:
                from accounts.constants import FranchiseLevel as _FL
                level_label = dict(_FL.CHOICES).get(self.franchise_level, self.franchise_level)
                raise ValidationError(
                    _("An active %(level)s already exists in this territory (spec §11.1).")
                    % {"level": level_label}
                )

        # A user may hold MANY franchises — different countries, different
        # levels, bought by different companies they own (product decision,
        # Jul 2026; supersedes the earlier one-franchise-per-user rule). What is
        # still forbidden is holding two franchises whose territories overlap:
        # you cannot be your own franchisee, so a German National holder can't
        # also take a Regional inside Germany, while a Brazilian Master is fine.
        # Territory exclusivity (above) separately keeps two DIFFERENT holders
        # out of the same territory.
        self.validate_owner_territories_do_not_overlap()

    def conflicting_franchise_owned(self):
        """A live franchise node held by this node's owner whose territory
        overlaps this node's — one contains the other — if any.

        "Live" excludes wound-down (TERMINATED/EXPIRED) and soft-deleted nodes,
        so a former holder can be granted a new franchise. Containment is
        checked both ways, which covers the parent/child case (a child territory
        is always inside its parent's) as well as a same-level duplicate.
        Territories that don't overlap — a German National and a Brazilian
        Master, say — are fine and are not reported here."""
        if not self.owner_user_id or self.franchise_level is None:
            return None
        others = (
            Tenant.objects.filter(
                owner_user_id=self.owner_user_id,
                franchise_level__isnull=False,
            )
            .exclude(id=self.id)
            .exclude(franchise_status__in=[
                FranchiseUnitStatus.TERMINATED,
                FranchiseUnitStatus.EXPIRED,
            ])
        )
        for other in others:
            if self.is_territory_within(other) or other.is_territory_within(self):
                return other
        return None

    def validate_owner_territories_do_not_overlap(self):
        from django.core.exceptions import ValidationError

        other = self.conflicting_franchise_owned()
        if other is not None:
            raise ValidationError(
                {"owner_user":
                    _("This user already holds %(name)s, whose territory overlaps "
                      "this one. A holder cannot also hold a franchise inside (or "
                      "containing) their own territory — pick another territory.")
                    % {"name": other.name}}
            )

    def save(self, *args, **kwargs):
        """Fill in the slug, then enforce the overlapping-territory owner rule.

        `clean()` carries the full tree ruleset but Django never calls it from
        `save()`, so it only guards the paths that invoke it explicitly. The
        owner rule is the one invariant that must hold no matter how the row is
        written — view, shell, data import or fixture — so it runs here too.
        Only this single rule is re-checked; the structural/territory rules stay
        in `clean()` because legitimate transitions (suspending a parent, for
        instance) re-save children that would otherwise trip them.

        Winding a node down (terminate / expire / soft-delete) is always allowed
        — otherwise a pre-existing duplicate could never be cleaned up."""
        self._ensure_slug()
        self._normalise_territory()
        winding_down = (
            self.is_deleted
            or self.franchise_status in (
                FranchiseUnitStatus.TERMINATED, FranchiseUnitStatus.EXPIRED,
            )
        )
        if not winding_down:
            self.validate_owner_territories_do_not_overlap()
        return super().save(*args, **kwargs)


class IndustryCodeBase(models.Model):
    """Shared shape for hierarchical industry classification tables.

    NACE and NAICS are both code-driven hierarchies where the parent is
    derivable from the code prefix, but storing `parent` explicitly lets
    us issue tree queries without prefix-matching at every call site.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    level = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.title}"


class NaceCode(IndustryCodeBase):
    """NACE Rev. 2 (EU industry classification).

    Codes are 1–5 chars without separators (e.g. `A`, `A01`, `A0111`).
    Level: 1=Section, 2=Division, 3=Group, 4=Class.
    """

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.PROTECT,
    )

    class Meta(IndustryCodeBase.Meta):
        verbose_name = "NACE Code"
        verbose_name_plural = "NACE Codes"
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["level"]),
        ]


class NaicsCode(IndustryCodeBase):
    """NAICS 2022 (North American industry classification).

    Codes are 2–6 digit strings, plus a few range codes for top-level
    sectors (e.g. `31-33`, `44-45`, `48-49`). Level matches digit count
    for normal codes and is 2 for range codes.
    """

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.PROTECT,
    )

    class Meta(IndustryCodeBase.Meta):
        verbose_name = "NAICS Code"
        verbose_name_plural = "NAICS Codes"
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["level"]),
        ]


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
    # Industry classification.
    #
    # `nace_code` is the canonical/default (EU NACE Rev.2). `naics_code` is
    # an optional parallel reference for US/global lookups — the two systems
    # are not 1:1, so we store both rather than maintain a fake concordance.
    #
    # `industry_code` (free text below) is the *legacy* column that the
    # existing forms, dashboard templates, and bulk importer still write to.
    # It is being kept until those call sites migrate to the new FKs; new
    # code should populate the FKs instead. Don't reuse `industry_code` for
    # anything other than backward-compat reads.
    nace_code = models.ForeignKey(
        "NaceCode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="companies",
    )
    naics_code = models.ForeignKey(
        "NaicsCode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="companies",
    )
    industry_code = models.CharField(max_length=20, null=True, blank=True)
    keywords = models.CharField(max_length=500, null=True, blank=True)
    employee_count_range = models.CharField(
        max_length=20,
        choices=EmployeeCountRangeChoices.CHOICES,
        null=True,
        blank=True,
    )

    # ---- Contact ----
    # contact_first_name / contact_last_name name the human point of contact at
    # the company. They are filled in (and edited) by the certifying consultant
    # — Business Users can see them in the Company view but cannot change them.
    contact_first_name = models.CharField(max_length=80, null=True, blank=True)
    contact_last_name = models.CharField(max_length=80, null=True, blank=True)
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

    # ---- Bulk-import passthrough ----
    # Catch-all JSONB for columns that arrive via the bulk CSV importer but
    # don't have a typed home (~95 fields from the InfoGroup-style export).
    # Known fields are still routed to their typed columns; only the
    # leftovers land here. Not surfaced in the UI; queryable via
    # extra_data->>'<key>'.
    extra_data = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        indexes = [
            # Kept (without the uniqueness constraint) because list views
            # still filter by tenant first, name second.
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
            # Company name is globally unique across the platform. Soft-deleted
            # rows are excluded so deleting a company frees its name.
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_deleted=False),
                name="unique_company_name_when_active",
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
    preferred_language = models.CharField(
        max_length=10,
        choices=SupportedLocale.CHOICES,
        null=True,
        blank=True,
    )
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

    # Application status. Lifecycle for staff registrations (consultant /
    # coordinator / franchise): "pending" (registered, apply form not yet
    # submitted) → "submitted" (apply form done, awaiting super-admin review)
    # → "approved" / "declined". Only coordinator & franchise are GATED on
    # this (RequireApplicationApprovalMiddleware) — consultants are not gated.
    application_status = models.CharField(max_length=20, default="pending", null=True, blank=True)
    # Super-admin review metadata for the application (mirrors CoordinatorRequest).
    application_decline_reason = models.TextField(null=True, blank=True)
    application_decided_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="decided_applications",
        null=True,
        blank=True,
    )
    application_decided_at = models.DateTimeField(null=True, blank=True)

    # ---- Security / KYC ----
    kyc_id_hash = models.CharField(max_length=255, null=True, blank=True)

    # Veriff identity verification. `verification_status` mirrors the status
    # Veriff reports on its decision webhook — "approved" is the only state
    # that counts as a passed check; everything else (pending, declined,
    # resubmission_requested, expired, abandoned) leaves the account gated on
    # the /verify/ step and out of plan selection / the dashboard. New
    # registrations start as "pending"; existing accounts were grandfathered
    # to "approved" in the migration that introduced this field so they don't
    # get locked out retroactively. See RequireIdentityVerificationMiddleware
    # for the gate and accounts/view/webhook.py for where it's written.
    veriff_session_id = models.CharField(max_length=255, null=True, blank=True)
    verification_status = models.CharField(
        max_length=30, null=True, blank=True, default="pending"
    )

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

    @property
    def display_name(self):
        """Human label for this user: full name when we have one, else email.

        Built as a whole rather than falling back per-field — defaulting only
        last_name renders "Ada ada@example.com" for a user with no surname, and
        a leading space before the email when both names are blank.
        """
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def persist_preferred_language(self, language):
        """Write preferred_language directly to the database."""
        from FontEsin.middleware.locale import normalize_locale

        lang = normalize_locale(language)
        if lang not in SupportedLocale.ALL:
            lang = SupportedLocale.EN
        type(self).all_objects.filter(pk=self.pk).update(
            preferred_language=lang,
            updated_at=timezone.now(),
        )
        self.preferred_language = lang
        return lang

    @property
    def effective_preferred_language(self):
        """Resolved locale for this user; NULL/blank falls back to English."""
        if self.preferred_language:
            from FontEsin.middleware.locale import normalize_locale

            return normalize_locale(self.preferred_language)
        return SupportedLocale.EN


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


class CompanyJoinRequest(models.Model):
    """A Business User's request to JOIN an existing company from their profile.

    Distinct from CompanyConnection (the paid-plan "Connect" / partnership flow
    triggered off the Companies directory). A join request originates from the
    profile "Join Existing Company" picker, is open to every business user
    regardless of plan, and is approved or declined by the target company's
    owner from the dedicated "Join Requests" tab. On approval the requester is
    linked to the company via UserCompany so it shows up in their My Companies
    and they can view its details.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    # Lazy so get_status_display() localizes: the label is embedded inside an
    # already-translated sentence ("This request was already %(status)s."), and
    # a plain string there renders an English word in an otherwise translated
    # message for non-English users.
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_APPROVED, _("Approved")),
        (STATUS_DECLINED, _("Declined")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="join_requests"
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="join_requests"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    message = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_join_requests",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "company")
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user.email} ⇒ {self.company.name} ({self.status})"


class CompanyImportJob(models.Model):
    STATE_QUEUED = "queued"
    STATE_RUNNING = "running"
    STATE_COMPLETED = "completed"
    STATE_FAILED = "failed"
    STATE_CHOICES = (
        (STATE_QUEUED, "Queued"),
        (STATE_RUNNING, "Running"),
        (STATE_COMPLETED, "Completed"),
        (STATE_FAILED, "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        "User",
        on_delete=models.PROTECT,
        related_name="company_import_jobs",
    )
    target_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="company_import_jobs",
    )
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_QUEUED)

    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    error_log_path = models.CharField(max_length=500, null=True, blank=True)

    total_rows = models.BigIntegerField(default=0)
    processed_rows = models.BigIntegerField(default=0)
    inserted_rows = models.BigIntegerField(default=0)
    skipped_duplicates = models.BigIntegerField(default=0)
    failed_rows = models.BigIntegerField(default=0)

    error_message = models.TextField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_by", "-created_at"])]

    def __str__(self):
        return f"CompanyImportJob {self.id} ({self.state})"


class Notification(models.Model):
    """In-app message dropped onto a user's Messages page.

    Used for things like "Company X requested certification" landing in the
    routed consultant's inbox, or "Your company was certified" landing in the
    business user's inbox. Every account type sees their own inbox via the
    same Messages sidebar link.
    """

    KIND_CERTIFICATION_REQUEST = "certification_request"
    KIND_CERTIFICATION_APPROVED = "certification_approved"
    KIND_CERTIFICATION_DECLINED = "certification_declined"
    KIND_COORDINATOR_REQUEST = "coordinator_request"
    KIND_COORDINATOR_APPROVED = "coordinator_approved"
    KIND_COORDINATOR_DECLINED = "coordinator_declined"
    KIND_APPLICATION_REQUEST = "application_request"
    KIND_APPLICATION_APPROVED = "application_approved"
    KIND_APPLICATION_DECLINED = "application_declined"
    KIND_FRANCHISE_REQUEST = "franchise_request"
    KIND_FRANCHISE_APPROVED = "franchise_approved"
    KIND_FRANCHISE_REJECTED = "franchise_rejected"
    KIND_FRANCHISE_ACTIVATED = "franchise_activated"
    KIND_FRANCHISE_REMOVED = "franchise_removed"
    KIND_NEW_USER = "new_user"
    KIND_GENERIC = "generic"
    KIND_CHOICES = (
        (KIND_CERTIFICATION_REQUEST, "Certification request"),
        (KIND_CERTIFICATION_APPROVED, "Certification approved"),
        (KIND_CERTIFICATION_DECLINED, "Certification declined"),
        (KIND_COORDINATOR_REQUEST, "Coordinator request"),
        (KIND_COORDINATOR_APPROVED, "Coordinator request approved"),
        (KIND_COORDINATOR_DECLINED, "Coordinator request declined"),
        (KIND_APPLICATION_REQUEST, "Account application submitted"),
        (KIND_APPLICATION_APPROVED, "Account application approved"),
        (KIND_APPLICATION_DECLINED, "Account application declined"),
        (KIND_FRANCHISE_REQUEST, "Franchise application submitted"),
        (KIND_FRANCHISE_APPROVED, "Franchise application approved"),
        (KIND_FRANCHISE_REJECTED, "Franchise application rejected"),
        (KIND_FRANCHISE_ACTIVATED, "Franchise activated"),
        (KIND_FRANCHISE_REMOVED, "Franchise removed"),
        (KIND_NEW_USER, "New user in region"),
        (KIND_GENERIC, "Generic"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    sender = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="sent_notifications",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, default=KIND_GENERIC)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    # Catalog-backed source of `title` / `body`: the msgids plus their
    # interpolation params, re-rendered through gettext on every read so the
    # inbox follows the language switcher instead of freezing in whatever
    # language the recipient preferred when the row was written. The two text
    # columns stay as the fallback for rows written before this existed (and
    # for the few call sites that pass raw, untranslatable text).
    title_i18n = models.JSONField(null=True, blank=True)
    body_i18n = models.JSONField(null=True, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    related_company = models.ForeignKey(
        "Company",
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"Notification({self.kind}) → {self.recipient_id}"

    @property
    def display_title(self):
        """Title in the language the viewer has selected right now."""
        from accounts.utils.i18n_messages import render_payload

        return render_payload(self.title_i18n) or self.title

    @property
    def display_body(self):
        """Body in the language the viewer has selected right now."""
        from accounts.utils.i18n_messages import render_payload

        return render_payload(self.body_i18n) or self.body

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class ContactMessage(models.Model):
    """A message submitted from the public website "Contact" form.

    The landing page contact form lands here so the Super Admin can read and
    act on enquiries from a dedicated "Messages" inbox in the sidebar. Each
    submission also fans out a Notification to every active superuser (see
    accounts.utils.notifications.notify_contact_message) so it surfaces in the
    regular notifications inbox + badge too.

    Submitters are typically anonymous prospects (not logged-in users), so we
    store their contact details inline rather than linking to a User.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_read", "-created_at"]),
        ]

    def __str__(self):
        who = f"{self.first_name} {self.last_name}".strip() or self.email
        return f"ContactMessage from {who}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class CoordinatorRequest(models.Model):
    """A Business User's request to be upgraded to a Coordinator role.

    The BU submits the form from their profile page; the request lands in the
    Super Admin's Coordinator Requests queue. On approval, the requester's
    role is switched to COORDINATOR (primary_company linkage is preserved).
    On decline, the requester remains a Business User and can see the
    decline reason on their profile.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DECLINED, "Declined"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="coordinator_requests",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    target_region = models.CharField(max_length=200, blank=True)
    motivation = models.TextField(blank=True)
    decline_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="decided_coordinator_requests",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"CoordinatorRequest({self.user_id}, {self.status})"


class FranchiseApplication(models.Model):
    """A user's request to hold a franchise (spec §2, §8.4).

    A user never self-assigns a franchise role. They submit an application for a
    target level + territory, it routes to the approver (Master applications →
    Platform/Super Admin; sub-franchise applications → the parent franchise
    holder), and only after approval + contract + payment is a franchise node
    (Tenant) activated. This is distinct from the staff-registration flow stored
    inline on User.application_status — that gates dashboard access for
    consultant/coordinator/franchise *roles*; this models the franchise *tree*.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    applicant_user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="franchise_applications",
    )
    # The company the applicant was acting as when they bought the franchise.
    # A Business User with several companies can buy a franchise for each of
    # them in different territories, so the holding company is recorded here and
    # copied onto the node's `owner_company` at approval. Blank for applicants
    # who have no company (consultants, coordinators) or for the pre-Jul-2026
    # rows that predate the field.
    applicant_company = models.ForeignKey(
        "Company",
        on_delete=models.SET_NULL,
        related_name="franchise_applications",
        null=True,
        blank=True,
    )
    requested_level = models.CharField(
        max_length=20,
        choices=FranchiseLevel.CHOICES,
    )
    # Requested territory (denormalised, same shape as Tenant's territory_*).
    requested_country = models.CharField(max_length=2, blank=True, default="")
    requested_region = models.CharField(max_length=120, blank=True, default="")
    requested_city = models.CharField(max_length=120, blank=True, default="")
    requested_local_area = models.CharField(max_length=120, blank=True, default="")

    # The node this franchise would attach under. Null for a Master application
    # (approved by the Super Admin, becomes the root of a new tree).
    parent_franchise = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        related_name="child_applications",
        null=True,
        blank=True,
    )

    # Prospective franchisee's business + contact details captured on the
    # Add Sub-Franchise form (spec §8.1). The owner is still linked via
    # `applicant_user` (an existing account), but these record the legal entity
    # and contact the holder proposed, so the Platform Admin has them on hand at
    # activation. Blank for the outside-applicant flow, which doesn't collect them.
    legal_name = models.CharField(max_length=255, blank=True, default="")
    contact_person = models.CharField(max_length=255, blank=True, default="")
    contact_phone = models.CharField(max_length=40, blank=True, default="")

    application_status = models.CharField(
        max_length=20,
        choices=FranchiseApplicationStatus.CHOICES,
        default=FranchiseApplicationStatus.SUBMITTED,
    )
    application_note = models.TextField(blank=True)
    board_note = models.TextField(blank=True)

    approved_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="approved_franchise_applications",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="rejected_franchise_applications",
        null=True,
        blank=True,
    )
    rejected_at = models.DateTimeField(null=True, blank=True)

    # The franchise node created when this application is approved (spec §16 —
    # "an active Master Franchise is created only after approval").
    created_franchise = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        # Plural: this is a ForeignKey, so the reverse side is a manager over
        # every application that produced this node — a re-application after a
        # cancelled or superseded one can point at the same franchise.
        related_name="source_applications",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["application_status", "-created_at"]),
            models.Index(fields=["applicant_user", "-created_at"]),
            models.Index(fields=["parent_franchise", "application_status"]),
        ]

    def __str__(self):
        return f"FranchiseApplication({self.requested_level}, {self.application_status})"


class ConsultantAssignment(models.Model):
    """Links a consultant to the franchise node they operate under (spec §8.3).

    Standard Consultants are NOT franchise nodes — they are attached to a node
    via this table. A Micro-Franchise owner also appears here (as
    MICRO_FRANCHISE_OWNER) so a node's consultant roster is queryable in one
    place. Only the Micro owner carries territorial exclusivity; standard
    consultants never block a territory (spec §6, Rule 8).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    consultant_user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="consultant_assignments",
    )
    franchise_node = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="consultant_assignments",
    )

    # Territory the consultant works (denormalised; may narrow the node's area).
    territory_country = models.CharField(max_length=2, blank=True, default="")
    territory_region = models.CharField(max_length=120, blank=True, default="")
    territory_city = models.CharField(max_length=120, blank=True, default="")

    consultant_type = models.CharField(
        max_length=30,
        choices=ConsultantType.CHOICES,
        default=ConsultantType.STANDARD_CONSULTANT,
    )
    status = models.CharField(
        max_length=20,
        choices=ConsultantAssignmentStatus.CHOICES,
        default=ConsultantAssignmentStatus.ACTIVE,
    )

    assigned_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="made_consultant_assignments",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["franchise_node", "status"]),
            models.Index(fields=["consultant_user", "status"]),
        ]
        constraints = [
            # A consultant holds one active assignment per node.
            models.UniqueConstraint(
                fields=["consultant_user", "franchise_node"],
                condition=Q(status=ConsultantAssignmentStatus.ACTIVE),
                name="unique_active_assignment_per_node",
            ),
        ]

    def __str__(self):
        return f"ConsultantAssignment({self.consultant_user_id}, {self.consultant_type})"


class FranchiseRemovalRequest(models.Model):
    """A holder's request to give up one of their franchises.

    A holder can't simply drop a territory: ending a franchise ends its
    sub-franchises and consultant rosters too, so it goes through the same
    approver that granted it (mirroring FranchiseApplication in the opposite
    direction). A Master is reviewed by the Platform Admin; every sub-franchise
    is reviewed by its DIRECT parent holder — a Regional's exit is approved by
    the National above it. On approval the node is wound down through
    `accounts.utils.franchise_removal.remove_franchise`.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (PENDING, _("Pending")),
        (APPROVED, _("Approved")),
        (REJECTED, _("Rejected")),
        (CANCELLED, _("Cancelled")),
    ]

    # Statuses that still occupy the reviewer's queue.
    OPEN = frozenset({PENDING})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    node = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="removal_requests",
    )
    requested_by = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="franchise_removal_requests",
    )
    # The node whose holder reviews this request — the direct parent. Null for a
    # Master, which the Platform Admin reviews (same convention as
    # FranchiseApplication.parent_franchise).
    reviewer_franchise = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        related_name="child_removal_requests",
        null=True,
        blank=True,
    )

    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    decision_note = models.TextField(blank=True, default="")

    decided_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        related_name="decided_franchise_removal_requests",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["reviewer_franchise", "status"]),
            models.Index(fields=["requested_by", "-created_at"]),
        ]
        constraints = [
            # One open request per node keeps the queue unambiguous.
            models.UniqueConstraint(
                fields=["node"],
                condition=Q(status="PENDING"),
                name="unique_open_removal_request_per_node",
            ),
        ]

    def __str__(self):
        return f"FranchiseRemovalRequest({self.node_id}, {self.status})"
