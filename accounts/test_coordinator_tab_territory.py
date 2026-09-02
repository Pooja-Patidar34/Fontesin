"""The Coordinators tab is region-scoped at EVERY franchise level.

Each level narrows to exactly the territory its node holds:

  Master   IN                  → every coordinator in India
  National IN                  → every coordinator in India
  Regional IN / Madhya Pradesh → the Madhya Pradesh coordinators
  Micro    IN / MP / Bhopal    → the Bhopal coordinators

Two bugs kept this from working at any level (bug report, Sep 2026):

  * The coordinator's region was read from ``territory_region`` /
    ``territory_city`` alone. The coordinator application form is a single
    country dropdown (accounts/view/auth.py:apply_submit) and never fills those
    in — a coordinator's state and city come from REGISTRATION, which requires
    both, and live in ``state_region`` / ``city``. Master's node names only a
    country so it matched; every level below named a region and matched nobody.
  * Tenant scoping ran first and pinned the list to the holder's own tenant.
    A franchise is a geography, not a tenant, and in the live data no holder
    shared a tenant with any coordinator — so the tab was empty even for Master.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import FranchiseLevel, FranchiseUnitStatus
from accounts.models import Company, Role, Tenant, User


class CoordinatorTabTerritoryTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-coord-territory")

        self.coordinator_role = self._role("coordinator", "Coordinator")
        self.holder_role = self._role("business_user", "Business User")

        # A franchise holder is a Business User who owns an activated node —
        # buying a franchise is additive and leaves the role alone. Verified
        # and company-owning so the onboarding middleware lets the page load.
        self.holder = User.objects.create_user(
            email="holder@coordterr.test", password="x", is_active=True,
            tenant=self.tenant, role=self.holder_role,
            application_status="approved", verification_status="approved",
        )
        self.holder_company = Company.objects.create(
            tenant=self.tenant, name="Holder Co", owner_user=self.holder,
        )

        # A real coordinator: the application form sets territory_country +
        # target_region, registration sets state_region + city.
        self.bhopal = self._coordinator(
            "bhopal@coordterr.test", territory_country="IN",
            target_region="India", state_region="Madhya Pradesh", city="Bhopal",
        )
        self.indore = self._coordinator(
            "indore@coordterr.test", territory_country="IN",
            target_region="India", state_region="Madhya Pradesh", city="Indore",
        )
        self.patna = self._coordinator(
            "patna@coordterr.test", territory_country="IN",
            target_region="India", state_region="Bihar", city="Patna",
        )
        self.berlin = self._coordinator(
            "berlin@coordterr.test", territory_country="DE",
            target_region="Germany", state_region="Berlin", city="Berlin",
        )
        # A legacy row with no state or city — pre-dates the registration
        # fields being required, so it cannot be placed inside any state.
        self.in_country_only = self._coordinator(
            "in-only@coordterr.test", territory_country="IN",
            target_region="India",
        )

        self.client.force_login(self.holder)

    # -- helpers ----------------------------------------------------------

    def _role(self, code, name):
        role = Role.objects.filter(code__iexact=code).first()
        if role is None:
            role = Role.objects.create(code=code, name=name, tier_level=1)
        return role

    def _coordinator(self, email, **fields):
        return User.objects.create_user(
            email=email, password="x", is_active=True, tenant=self.tenant,
            role=self.coordinator_role, application_status="approved", **fields
        )

    def _node(self, level, slug, **territory):
        return Tenant.objects.create(
            name=slug, slug=slug, franchise_level=level,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.holder, **territory
        )

    def _listed_emails(self):
        response = self.client.get(
            reverse("coordinator-users"), SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 200)
        return {row["email"] for row in response.context["users_json"]}

    # -- one test per level ----------------------------------------------

    def test_master_over_india_lists_every_indian_coordinator(self):
        self._node(FranchiseLevel.MASTER, "master-in", territory_country="IN")
        self.assertEqual(
            self._listed_emails(),
            {self.bhopal.email, self.indore.email, self.patna.email,
             self.in_country_only.email},
        )

    def test_national_over_india_lists_every_indian_coordinator(self):
        self._node(FranchiseLevel.NATIONAL, "national-in", territory_country="IN")
        self.assertEqual(
            self._listed_emails(),
            {self.bhopal.email, self.indore.email, self.patna.email,
             self.in_country_only.email},
        )

    def test_national_that_names_a_state_narrows_to_it(self):
        """A National may name a state (canonical_territory allows it); when it
        does, it is scoped like a Regional rather than country-wide."""
        self._node(
            FranchiseLevel.NATIONAL, "national-in-mp",
            territory_country="IN", territory_region="Madhya Pradesh",
        )
        self.assertEqual(
            self._listed_emails(), {self.bhopal.email, self.indore.email},
        )

    def test_regional_over_madhya_pradesh_lists_only_that_state(self):
        self._node(
            FranchiseLevel.REGIONAL, "regional-in-mp",
            territory_country="IN", territory_region="Madhya Pradesh",
        )
        listed = self._listed_emails()
        self.assertEqual(listed, {self.bhopal.email, self.indore.email})
        self.assertNotIn(self.patna.email, listed)       # Bihar
        self.assertNotIn(self.berlin.email, listed)      # Germany

    def test_micro_over_bhopal_lists_only_that_city(self):
        self._node(
            FranchiseLevel.MICRO, "micro-in-mp-bhopal",
            territory_country="IN", territory_region="Madhya Pradesh",
            territory_city="Bhopal",
        )
        listed = self._listed_emails()
        self.assertEqual(listed, {self.bhopal.email})
        self.assertNotIn(self.indore.email, listed)      # same state, other city

    # -- the same rule in a different country -----------------------------

    def test_the_rule_is_country_agnostic(self):
        """Nothing is special-cased per country: a German Master lists the
        German coordinators exactly as an Indian one lists the Indian ones, and
        the Indian coordinators stay out of it."""
        self._node(FranchiseLevel.MASTER, "master-de", territory_country="DE")
        self.assertEqual(self._listed_emails(), {self.berlin.email})

    def test_country_agnostic_down_to_micro(self):
        munich = self._coordinator(
            "munich@coordterr.test", territory_country="DE",
            target_region="Germany", state_region="Bavaria", city="Munich",
        )
        self._node(
            FranchiseLevel.MICRO, "micro-de-by-munich",
            territory_country="DE", territory_region="Bavaria",
            territory_city="Munich",
        )
        listed = self._listed_emails()
        self.assertEqual(listed, {munich.email})
        self.assertNotIn(self.berlin.email, listed)   # Germany, different city

    # -- how a coordinator's own region is resolved -----------------------

    def test_coordinator_known_only_by_target_region_is_matched(self):
        """No territory_country — the country comes from the application label,
        the same fallback chain the coordinator's own Company Database uses."""
        label_only = self._coordinator(
            "label@coordterr.test", target_region="India",
            state_region="Madhya Pradesh", city="Bhopal",
        )
        self._node(FranchiseLevel.REGIONAL, "regional-in-mp-2",
                   territory_country="IN", territory_region="Madhya Pradesh")
        self.assertIn(label_only.email, self._listed_emails())

    def test_admin_assigned_territory_beats_the_profile_address(self):
        """An admin who pins a coordinator to Bihar overrides where they live:
        territory_region wins over state_region."""
        reassigned = self._coordinator(
            "reassigned@coordterr.test", territory_country="IN",
            territory_region="Bihar",
            state_region="Madhya Pradesh", city="Bhopal",
        )
        self._node(FranchiseLevel.REGIONAL, "regional-in-mp-3",
                   territory_country="IN", territory_region="Madhya Pradesh")
        self.assertNotIn(reassigned.email, self._listed_emails())

    def test_explicit_territory_beats_the_profile_country(self):
        """A coordinator assigned to Germany who happens to live in India is a
        Germany coordinator, not an Indian one."""
        expat = self._coordinator(
            "expat@coordterr.test", territory_country="DE", country="IN",
        )
        self._node(FranchiseLevel.MASTER, "master-in-2", territory_country="IN")
        self.assertNotIn(expat.email, self._listed_emails())

    def test_country_only_coordinator_is_not_placed_in_a_state(self):
        """A coordinator with no state cannot be said to be IN Madhya Pradesh,
        so a Regional does not list them — while the country-level Master and
        National above do (see the per-level tests)."""
        self._node(FranchiseLevel.REGIONAL, "regional-in-mp-4",
                   territory_country="IN", territory_region="Madhya Pradesh")
        self.assertNotIn(self.in_country_only.email, self._listed_emails())

    def test_coordinator_in_another_tenant_is_still_listed(self):
        """A franchise is a geography, not a tenant.

        Coordinators register into whatever tenant they land in, which is not
        the holder's — in the live data no holder shared a tenant with any
        coordinator, so pinning the list to the holder's tenant emptied the tab
        at every level. Territory is the scope; tenant must not narrow it.
        """
        other_tenant = Tenant.objects.create(
            name="Other", slug="other-coord-territory",
        )
        stranger = self._coordinator(
            "stranger@coordterr.test", territory_country="IN",
            state_region="Madhya Pradesh", city="Bhopal",
        )
        stranger.tenant = other_tenant
        stranger.save(update_fields=["tenant"])

        self._node(FranchiseLevel.REGIONAL, "regional-in-mp-5",
                   territory_country="IN", territory_region="Madhya Pradesh")
        self.assertIn(stranger.email, self._listed_emails())

    def test_node_without_a_territory_lists_nobody(self):
        self._node(FranchiseLevel.MASTER, "master-none-terr")
        self.assertEqual(self._listed_emails(), set())
