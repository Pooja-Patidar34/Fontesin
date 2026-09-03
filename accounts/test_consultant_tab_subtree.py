"""The Consultants tab (Network → Consultant Users) is subtree-scoped at EVERY
franchise level.

Each holder sees the consultants assigned to the node they own plus those
assigned to every node BELOW it, and never the ones their parent franchise
assigned (spec §7.1 downward visibility, §7.3 no parallel/upward leakage):

  Master   → its own roster + National + Regional + Micro
  National → its own roster + Regional + Micro, but not Master's
  Regional → its own roster + Micro, but not National's or Master's
  Micro    → its own roster only

The tree used here is the canonical one, Master ▸ National ▸ Regional ▸ Micro,
matching FranchiseLevel.RANK — a child must have a strictly greater rank than
its parent, so a National can never sit under a Regional. One consultant is
assigned at each level.

Visibility itself follows PARENT LINKS, not territory codes: a Master over
India sees a Bhopal Micro because that Micro is a descendant of their node, not
because both carry "IN". RANK only constrains which parent a node may be
attached to when it is created.

Tenant scoping used to run first and pin the list to the holder's own tenant —
the same bug that emptied the Coordinators tab (see
test_coordinator_tab_territory). A franchise is a tree, not a tenant, and a
holder has no reason to share a tenant with the consultants operating under a
sub-franchise, so the subtree filter is the only scope that belongs here; it
fails closed on its own (a holder with nobody assigned under them sees nobody).

The last test covers the reporting note: from a consultant's row a holder can
read which franchise that consultant is assigned to and which they own.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.constants import (
    ConsultantAssignmentStatus,
    ConsultantType,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import Company, ConsultantAssignment, Role, Tenant, User


class ConsultantTabSubtreeTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-consult-subtree")
        # Consultants register in the platform tenant, holders in whichever one
        # their company sits in — deliberately different, so a tenant pin would
        # empty every tab below.
        self.staff_tenant = Tenant.objects.create(
            name="Staff", slug="staff-consult-subtree",
        )

        self.consultant_role = self._role("consultant", "Consultant")
        self.holder_role = self._role("business_user", "Business User")

        # Master ▸ National ▸ Regional ▸ Micro, each with its own holder.
        self.master_owner = self._holder("master@subtree.test", "Master Co")
        self.national_owner = self._holder("national@subtree.test", "National Co")
        self.regional_owner = self._holder("regional@subtree.test", "Regional Co")
        self.micro_owner = self._holder("micro@subtree.test", "Micro Co")

        self.master = self._node(
            FranchiseLevel.MASTER, "master-node", self.master_owner,
            territory_country="IN",
        )
        self.national = self._node(
            FranchiseLevel.NATIONAL, "national-node", self.national_owner,
            parent=self.master, territory_country="IN",
        )
        self.regional = self._node(
            FranchiseLevel.REGIONAL, "regional-node", self.regional_owner,
            parent=self.national, territory_country="IN",
            territory_region="Madhya Pradesh",
        )
        self.micro = self._node(
            FranchiseLevel.MICRO, "micro-node", self.micro_owner,
            parent=self.regional, territory_country="IN",
            territory_region="Madhya Pradesh", territory_city="Bhopal",
        )

        # A separate tree nobody in the tree above may see into (§7.3).
        self.outsider_owner = self._holder("outsider@subtree.test", "Outsider Co")
        self.other_master = self._node(
            FranchiseLevel.MASTER, "other-master-node", self.outsider_owner,
            territory_country="DE",
        )

        self.c_master = self._consultant("c-master@subtree.test", self.master)
        self.c_regional = self._consultant("c-regional@subtree.test", self.regional)
        self.c_national = self._consultant("c-national@subtree.test", self.national)
        self.c_micro = self._consultant("c-micro@subtree.test", self.micro)
        self.c_other = self._consultant("c-other@subtree.test", self.other_master)
        # Assigned nowhere — belongs to no subtree, so no holder sees them.
        self.c_unassigned = self._consultant("c-unassigned@subtree.test", None)
        # Assigned under the Micro but terminated — no longer part of the roster.
        self.c_former = self._consultant(
            "c-former@subtree.test", self.micro,
            status=ConsultantAssignmentStatus.TERMINATED,
        )

    # -- helpers ----------------------------------------------------------

    def _role(self, code, name):
        role = Role.objects.filter(code__iexact=code).first()
        if role is None:
            role = Role.objects.create(code=code, name=name, tier_level=1)
        return role

    def _holder(self, email, company_name):
        """A Business User who owns an activated node — buying a franchise is
        additive and leaves the role alone. Verified and company-owning so the
        onboarding middleware lets the page load."""
        user = User.objects.create_user(
            email=email, password="x", is_active=True,
            tenant=self.tenant, role=self.holder_role,
            application_status="approved", verification_status="approved",
        )
        Company.objects.create(
            tenant=self.tenant, name=company_name, owner_user=user,
        )
        return user

    def _node(self, level, slug, owner, **fields):
        return Tenant.objects.create(
            name=slug, slug=slug, franchise_level=level,
            franchise_status=FranchiseUnitStatus.ACTIVE,
            owner_user=owner, **fields
        )

    def _consultant(self, email, node, status=ConsultantAssignmentStatus.ACTIVE):
        user = User.objects.create_user(
            email=email, password="x", is_active=True,
            tenant=self.staff_tenant, role=self.consultant_role,
            application_status="approved",
        )
        if node is not None:
            ConsultantAssignment.objects.create(
                consultant_user=user, franchise_node=node, status=status,
                consultant_type=ConsultantType.STANDARD_CONSULTANT,
            )
        return user

    def _rows_for(self, holder):
        self.client.force_login(holder)
        response = self.client.get(
            reverse("consultant-users"), SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 200)
        return response.context["users_json"]

    def _listed_emails(self, holder):
        return {row["email"] for row in self._rows_for(holder)}

    # -- one test per level ----------------------------------------------

    def test_master_sees_its_own_roster_and_every_subfranchise(self):
        self.assertEqual(
            self._listed_emails(self.master_owner),
            {self.c_master.email, self.c_national.email,
             self.c_regional.email, self.c_micro.email},
        )

    def test_national_sees_below_it_but_not_its_parent(self):
        listed = self._listed_emails(self.national_owner)
        self.assertEqual(
            listed,
            {self.c_national.email, self.c_regional.email, self.c_micro.email},
        )
        self.assertNotIn(self.c_master.email, listed)

    def test_regional_sees_below_it_but_not_its_parents(self):
        listed = self._listed_emails(self.regional_owner)
        self.assertEqual(listed, {self.c_regional.email, self.c_micro.email})
        self.assertNotIn(self.c_national.email, listed)
        self.assertNotIn(self.c_master.email, listed)

    def test_micro_sees_only_its_own_roster(self):
        listed = self._listed_emails(self.micro_owner)
        self.assertEqual(listed, {self.c_micro.email})
        self.assertNotIn(self.c_regional.email, listed)
        self.assertNotIn(self.c_national.email, listed)
        self.assertNotIn(self.c_master.email, listed)

    def test_the_tree_under_test_is_one_the_app_would_accept(self):
        """These nodes are created directly, bypassing the parent-choice
        validation, so nothing else here would notice if the fixture encoded a
        tree the app refuses to build. A child must rank strictly deeper than
        its parent (FranchiseLevel.RANK), which is what fixes the tier order as
        Master ▸ National ▸ Regional ▸ Micro."""
        rank = FranchiseLevel.RANK
        for child in (self.national, self.regional, self.micro):
            self.assertLess(
                rank[child.parent.franchise_level], rank[child.franchise_level],
                f"{child.name} may not sit under {child.parent.name}",
            )

    # -- what never shows up ---------------------------------------------

    def test_parallel_tree_unassigned_and_terminated_are_excluded(self):
        listed = self._listed_emails(self.master_owner)
        self.assertNotIn(self.c_other.email, listed)
        self.assertNotIn(self.c_unassigned.email, listed)
        self.assertNotIn(self.c_former.email, listed)

    def test_holder_and_consultants_need_not_share_a_tenant(self):
        """Regression: the tenant pin ran before the subtree filter and emptied
        the tab, since holders and consultants register in different tenants."""
        self.assertNotEqual(self.master_owner.tenant_id, self.c_micro.tenant_id)
        self.assertIn(self.c_micro.email, self._listed_emails(self.master_owner))

    # -- the reporting note ----------------------------------------------

    def test_row_reports_the_franchise_a_consultant_is_assigned_to_and_owns(self):
        """From a consultant's row a holder can read which franchise that
        consultant works for, and which (if any) they hold themselves — a
        Micro-Franchise owner is also a consultant, so both can be filled in."""
        # Make the Micro's owner their own node's consultant, as spec §9.1.2 has it.
        ConsultantAssignment.objects.create(
            consultant_user=self.micro_owner, franchise_node=self.micro,
            status=ConsultantAssignmentStatus.ACTIVE,
            consultant_type=ConsultantType.MICRO_FRANCHISE_OWNER,
        )
        self.micro_owner.role = self.consultant_role
        self.micro_owner.save(update_fields=["role"])

        rows = {row["email"]: row for row in self._rows_for(self.master_owner)}

        assigned = rows[self.c_micro.email]["franchise_assigned"]
        self.assertEqual(len(assigned), 1)
        self.assertIn("micro-node", assigned[0])
        self.assertIn("Bhopal", assigned[0])
        self.assertEqual(rows[self.c_micro.email]["franchise_owned"], [])

        owner_row = rows[self.micro_owner.email]
        self.assertTrue(any("micro-node" in a for a in owner_row["franchise_assigned"]))
        self.assertTrue(any("micro-node" in o for o in owner_row["franchise_owned"]))
