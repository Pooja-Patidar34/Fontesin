"""Add Sub-Franchise attaches a node to its DIRECT parent, not to whichever of
the holder's own nodes was picked in the form.

Bug report (Sep 2026): a Master holding Angola created a National, a Regional and
a Micro from its own Add Sub-Franchise form. All three were attached to the
Master as siblings, so the National had no descendants — and downward visibility
(`get_descendant_ids`, spec §7.1) meant it could not see the Regional's or the
Micro's consultants even though both territories sit inside its own country.

The direct parent is "the deepest ACTIVE node whose territory contains the
requested one" (`resolve_parent_node`, spec §4.2) — the rule the outside-applicant
flow and the Admin approval path already used.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import FranchiseLevel, FranchiseUnitStatus
from accounts.models import ConsultantAssignment, Role, Tenant, User
from accounts.view.franchise import subtree_consultant_ids


class SubFranchiseDirectParentTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-direct-parent")
        self.role = Role.objects.filter(code__iexact="franchise").first()
        if self.role is None:
            self.role = Role.objects.create(
                code="franchise", name="Franchise", tier_level=1,
            )
        self.master_owner = self.user("master@dp.test", approved=True)
        self.master = Tenant.objects.create(
            name="Master Franchise — Angola", slug="master-ao-dp",
            franchise_level=FranchiseLevel.MASTER,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.master_owner, territory_country="AO",
        )
        self.national_owner = self.user("national@dp.test")
        self.national = Tenant.objects.create(
            name="National Sub-Franchise — Angola", slug="national-ao-dp",
            franchise_level=FranchiseLevel.NATIONAL,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=self.national_owner, territory_country="AO",
            parent=self.master,
        )
        self.client.force_login(self.master_owner)

    # -- helpers ----------------------------------------------------------

    def user(self, email, approved=False):
        return User.objects.create_user(
            email=email, password="x", is_active=True, tenant=self.tenant,
            role=self.role,
            **({"application_status": "approved"} if approved else {}),
        )

    def propose(self, owner_email, level, region, city="", **extra):
        """The Master proposes a sub-franchise, always picking ITSELF as the
        parent in the form — which is all its picker offers."""
        payload = {
            "parent_node_id": str(self.master.id),
            "requested_level": level,
            "requested_region": region,
            "requested_city": city,
            "requested_local_area": city,
            "legal_name": "Co " + region,
            "contact_person": "Someone",
            "owner_email": owner_email,
        }
        payload.update(extra)
        response = self.client.post(
            reverse("franchise-subfranchise-submit"), payload, SERVER_NAME="localhost",
        )
        return response

    def node_for(self, owner):
        return Tenant.objects.filter(owner_user=owner).exclude(
            id__in=[self.master.id, self.national.id],
        ).first()

    # -- the tree ---------------------------------------------------------

    def test_regional_attaches_under_the_national_not_the_master(self):
        """The reported case: the Master proposes a Regional inside Angola while
        an ACTIVE National already covers the country."""
        owner = self.user("regional@dp.test")
        self.propose("regional@dp.test", "REGIONAL", "Malange")
        regional = self.node_for(owner)
        self.assertIsNotNone(regional)
        self.assertEqual(regional.parent, self.national)
        self.assertNotEqual(regional.parent, self.master)

    def test_micro_attaches_under_the_deepest_cover(self):
        regional_owner = self.user("regional2@dp.test")
        self.propose("regional2@dp.test", "REGIONAL", "Benguela")
        regional = self.node_for(regional_owner)
        self.assertEqual(regional.parent, self.national)

        micro_owner = self.user("micro@dp.test")
        self.propose("micro@dp.test", "MICRO", "Benguela", city="Lobito")
        micro = Tenant.objects.filter(owner_user=micro_owner).first()
        self.assertIsNotNone(micro)
        # Deepest ACTIVE cover wins — but the Regional is PENDING_CONTRACT until
        # the Admin activates it, so the National is still the deepest ACTIVE one.
        self.assertEqual(micro.parent, self.national)

    def test_master_stays_the_parent_when_nothing_deeper_covers(self):
        """No National over Angola → the Master really is the direct parent, and
        the resolution must not invent a different one."""
        self.national.franchise_status = FranchiseUnitStatus.TERMINATED
        self.national.save(update_fields=["franchise_status"])
        owner = self.user("solo@dp.test")
        self.propose("solo@dp.test", "REGIONAL", "Bengo")
        self.assertEqual(self.node_for(owner).parent, self.master)

    # -- what the tree shape buys: downward visibility ---------------------

    def test_national_sees_the_consultants_of_its_new_descendants(self):
        """The symptom behind the report — the National could not see the
        consultants working under franchises inside its own territory."""
        regional_owner = self.user("regional3@dp.test")
        self.propose("regional3@dp.test", "REGIONAL", "Malange")
        regional = self.node_for(regional_owner)
        # Activate it, then put a consultant under it.
        regional.franchise_status = FranchiseUnitStatus.ACTIVE
        regional.save(update_fields=["franchise_status"])
        consultant = self.user("consultant@dp.test")
        ConsultantAssignment.objects.create(
            consultant_user=consultant, franchise_node=regional,
            assigned_by=self.master_owner,
        )

        # The National now sees the Regional's consultant...
        self.assertIn(consultant.id, subtree_consultant_ids(self.national_owner))
        # ...and so does the Master, above it.
        self.assertIn(consultant.id, subtree_consultant_ids(self.master_owner))
        # The Regional's holder never sees UP the tree (spec §7.2/§7.3).
        other = self.user("outsider@dp.test")
        self.assertNotIn(consultant.id, subtree_consultant_ids(other))
