"""Regression tests: business logic must not change when the UI locale changes."""

from django.db.models import Count
from django.test import Client
from django.urls import reverse
from django.utils import translation

from accounts.models import Company, Permission, Role, User
from accounts.tests import BaseBillingTestCase, _make_role
from accounts.utils.certification_routing import find_consultant_for_company
from accounts.utils.country_matching import country_match_q, resolve_country_code
from accounts.utils.permissions import has_permission
from accounts.view.company import (
    business_user_plan_scope_q,
    business_user_visible_companies,
    coordinator_territory_q,
    _coordinator_region_code,
)
from billing import utils as billing_utils


LOCALES = ("en", "fr", "de", "es")


def _ids(qs):
    return set(qs.values_list("id", flat=True))


def _counts_across_locales(fn):
    """Run ``fn()`` under each locale; return the first result and assert equality."""
    results = []
    for locale in LOCALES:
        with translation.override(locale):
            results.append(fn())
    first = results[0]
    for other in results[1:]:
        if isinstance(first, set):
            assert other == first
        else:
            assert other == first
    return first


class CountryMatchingLocaleTests(BaseBillingTestCase):
  def test_country_match_q_invariant_across_locales(self):
    Company.objects.create(
      tenant=self.tenant, name="US English", country="United States", is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="US Code", country="US", is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="DE English", country="Germany", is_active=True,
    )

    def matched_us_ids():
      return _ids(Company.objects.filter(country_match_q("US")))

    us_ids = _counts_across_locales(matched_us_ids)
    self.assertEqual(len(us_ids), 2)

  def test_cached_label_map_is_immutable_and_shared(self):
    """lru_cache hands every caller the same object, so it must be read-only —
    one stray write would corrupt country resolution process-wide."""
    from accounts.utils.country_matching import all_country_label_to_code
    mapping = all_country_label_to_code()
    self.assertIs(mapping, all_country_label_to_code())
    with self.assertRaises(TypeError):
      mapping["notacountry"] = "ZZ"
    # Still resolves after the rejected write.
    self.assertEqual(resolve_country_code("United States"), "US")

  def test_resolve_country_code_handles_translated_labels(self):
    with translation.override("de"):
      from accounts.constants import CountryChoices
      german_label = str(dict(CountryChoices.CHOICES)["DE"])
    self.assertEqual(resolve_country_code(german_label), "DE")
    self.assertEqual(resolve_country_code("Germany"), "DE")
    self.assertEqual(resolve_country_code("DE"), "DE")

  def test_coordinator_region_code_resolves_translated_target_region(self):
    coord_role = _make_role("Coordinator", "coordinator")
    with translation.override("fr"):
      from accounts.constants import CountryChoices
      french_de = str(dict(CountryChoices.CHOICES)["DE"])
    user = User.objects.create_user(
      email="coord-locale@test.com",
      password="x",
      tenant=self.tenant,
      role=coord_role,
      target_region=french_de,
    )

    def region_code():
      return _coordinator_region_code(user)

    self.assertEqual(_counts_across_locales(region_code), "DE")


class BusinessUserVisibilityLocaleTests(BaseBillingTestCase):
  def setUp(self):
    super().setUp()
    view_perm, _ = Permission.objects.get_or_create(
      code="company.view",
      defaults={"description": "View companies"},
    )
    self.bu_role = _make_role("Business User", "business_user")
    self.bu_role.permissions.add(view_perm)
    self.bu = User.objects.create_user(
      email="bu-locale@test.com",
      password="x",
      tenant=self.tenant,
      role=self.bu_role,
      country="US",
      city="Arvada",
    )
    self._create_subscription(self.bu, self.plan_free)
    # The Free plan is scoped to the user's TOWN, so every row here shares the
    # town — what's under test is that the COUNTRY half of the match is
    # locale-invariant (ISO code vs canonical English name vs translated label).
    Company.objects.create(
      tenant=self.tenant, name="US Co", country="US", city="Arvada", is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="US Name", country="United States", city="Arvada",
      is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="DE Co", country="Germany", city="Arvada", is_active=True,
    )

  def test_free_plan_visible_companies_invariant(self):
    def visible_ids():
      return _ids(business_user_visible_companies(self.bu))

    ids = _counts_across_locales(visible_ids)
    names = set(
      Company.objects.filter(id__in=ids).values_list("name", flat=True)
    )
    self.assertIn("US Co", names)
    self.assertIn("US Name", names)
    self.assertNotIn("DE Co", names)

  def test_plan_scope_q_invariant(self):
    def scope_ids():
      q = business_user_plan_scope_q(self.bu)
      return _ids(Company.objects.filter(q)) if q is not None else set()

    ids = _counts_across_locales(scope_ids)
    self.assertEqual(len(ids), 2)


class BillingScopeLocaleTests(BaseBillingTestCase):
  def setUp(self):
    super().setUp()
    self.user.country = "US"
    self.user.save()
    self.us_co = Company.objects.create(
      tenant=self.tenant, name="US Co", country="US", is_active=True,
    )
    self.us_name_co = Company.objects.create(
      tenant=self.tenant, name="US Name Co", country="United States", is_active=True,
    )
    self.de_co = Company.objects.create(
      tenant=self.tenant, name="DE Co", country="Germany", is_active=True,
    )

  def test_filter_companies_by_plan_scope_invariant(self):
    self._create_subscription(self.user, self.plan_basic)

    def filtered_ids():
      qs = billing_utils.filter_companies_by_plan_scope(Company.objects.all(), self.user)
      return _ids(qs)

    ids = _counts_across_locales(filtered_ids)
    self.assertIn(self.us_co.id, ids)
    self.assertIn(self.us_name_co.id, ids)
    self.assertNotIn(self.de_co.id, ids)

  def test_geographic_scope_invariant(self):
    self._create_subscription(self.user, self.plan_basic)

    def scope():
      return billing_utils.get_user_geographic_scope(self.user)

    scope = _counts_across_locales(scope)
    self.assertEqual(scope["mode"], "country")
    self.assertEqual(scope["countries"], ["US"])


class CoordinatorTerritoryLocaleTests(BaseBillingTestCase):
  def setUp(self):
    super().setUp()
    self.coord_role = _make_role("Coordinator", "coordinator")
    self.coordinator = User.objects.create_user(
      email="coord-territory@test.com",
      password="x",
      tenant=self.tenant,
      role=self.coord_role,
      territory_country="DE",
    )
    self.certified_de = Company.objects.create(
      tenant=self.tenant,
      name="Certified DE",
      country="Germany",
      certification_status="certified",
      is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant,
      name="Certified US",
      country="US",
      certification_status="certified",
      is_active=True,
    )

  def test_coordinator_territory_q_invariant(self):
    def territory_ids():
      q = coordinator_territory_q(self.coordinator)
      return _ids(Company.objects.filter(q)) if q is not None else set()

    ids = _counts_across_locales(territory_ids)
    self.assertIn(self.certified_de.id, ids)
    self.assertEqual(len(ids), 1)


class CertificationRoutingLocaleTests(BaseBillingTestCase):
  def test_find_consultant_matches_country_across_locales(self):
    consultant_role = _make_role("Consultant", "consultant")
    consultant = User.objects.create_user(
      email="consult-routing@test.com",
      password="x",
      tenant=self.tenant,
      role=consultant_role,
    )
    Company.objects.create(
      tenant=self.tenant,
      name="Anchor",
      country="Germany",
      city="Berlin",
      consultant=consultant,
      certification_status="certified",
      is_active=True,
    )
    pending = Company.objects.create(
      tenant=self.tenant,
      name="Pending DE",
      country="Germany",
      city="Munich",
      certification_status="pending",
      is_active=False,
    )

    def picked_id():
      found = find_consultant_for_company(pending)
      return found.id if found else None

    self.assertEqual(_counts_across_locales(picked_id), consultant.id)


class PermissionsLocaleTests(BaseBillingTestCase):
  def test_has_permission_invariant(self):
    def allowed():
      return has_permission(self.user, "company.view")

    self.assertTrue(_counts_across_locales(allowed))


class DashboardStatsLocaleTests(BaseBillingTestCase):
  def setUp(self):
    super().setUp()
    Company.objects.create(
      tenant=self.tenant, name="Dash US", country="US", is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="Dash DE", country="Germany", is_active=True,
    )

  def test_active_regions_count_invariant(self):
    def active_regions():
      return (
        Company.objects
        .exclude(country__isnull=True)
        .exclude(country="")
        .values("country")
        .distinct()
        .count()
      )

    self.assertEqual(_counts_across_locales(active_regions), 2)

  def test_regional_performance_grouping_invariant(self):
    def region_counts():
      rows = (
        Company.objects
        .exclude(country__isnull=True)
        .exclude(country="")
        .values("country")
        .annotate(count=Count("id"))
        .order_by("-count")
      )
      return {r["country"]: r["count"] for r in rows}

    counts = _counts_across_locales(region_counts)
    self.assertEqual(counts.get("US"), 1)
    self.assertEqual(counts.get("Germany"), 1)


class GlobalSearchLocaleTests(BaseBillingTestCase):
  def setUp(self):
    super().setUp()
    view_perm, _ = Permission.objects.get_or_create(
      code="company.view",
      defaults={"description": "View companies"},
    )
    self.bu_role = _make_role("Business User", "business_user")
    self.bu_role.permissions.add(view_perm)
    self.bu = User.objects.create_user(
      email="search-locale@test.com",
      password="x",
      tenant=self.tenant,
      role=self.bu_role,
      country="US",
      city="Arvada",
    )
    # RequireCompanyForBusinessUserMiddleware bounces a Business User who owns
    # no company to /dashboard/, so without an owned company the request never
    # reaches the search view at all. Named so it can't match the "Searchable"
    # query and skew the result set the invariant is asserted on. It is also the
    # active company, so it anchors the Free plan's town scope.
    owner_company = Company.objects.create(
      tenant=self.tenant, name="Owner Co", country="United States", city="Arvada",
      is_active=True, owner_user=self.bu,
    )
    # Plans are company-scoped (billing.utils.get_active_subscription): the sub
    # must hang off the ACTIVE company or the plan resolves to None and the
    # discovery scope collapses to an empty queryset.
    subscription = self._create_subscription(self.bu, self.plan_free)
    subscription.company = owner_company
    subscription.save(update_fields=["company"])
    # Same town as the searcher (the Free plan is town-scoped); what varies is
    # the country spelling, which is what the invariant is about.
    Company.objects.create(
      tenant=self.tenant, name="Searchable US", country="United States", city="Arvada",
      is_active=True,
    )
    Company.objects.create(
      tenant=self.tenant, name="Hidden DE", country="Germany", city="Arvada",
      is_active=True,
    )

  def test_global_search_company_ids_invariant(self):
    client = Client()
    client.force_login(self.bu)

    def search_ids():
      # UserLocaleMiddleware calls translation.activate() on every request, which
      # overwrites the translation.override() this runs under — without ?lang=
      # the search would execute in the user's profile language (English) all
      # four times and the test would prove nothing. ?lang= is the one input the
      # middleware honours ahead of the profile, so it is what actually varies
      # the locale server-side; the Content-Language assert proves it took.
      locale = translation.get_language()
      response = client.get(
        reverse("global-search"), {"q": "Searchable", "lang": locale},
      )
      self.assertEqual(
        response.status_code, 200,
        msg=f"lang={locale} redirected to {response.get('Location')!r}",
      )
      self.assertEqual(response.headers.get("Content-Language"), locale)
      return set(c.id for c in response.context["companies"])

    ids = _counts_across_locales(search_ids)
    self.assertEqual(len(ids), 1)
