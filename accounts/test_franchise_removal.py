"""Platform-Admin removal of a franchise (accounts/utils/franchise_removal.py).

The admin has to be able to take a franchise back from any holder, at any level,
in any status — suspension only pauses rights. Removal is a subtree wind-down,
so these tests pin the cascade: sub-franchises, consultant rosters, the
applications behind the nodes, holder roles, and the freed territory.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.constants import (
    ConsultantAssignmentStatus,
    ConsultantType,
    FranchiseApplicationStatus,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import (
    AuditLog,
    Company,
    ConsultantAssignment,
    FranchiseApplication,
    Notification,
    Role,
    Tenant,
    User,
)


class FranchiseRemovalTestCase(TestCase):
    """Shared fixture: a Platform Admin plus the roles activation moves users between."""

    def setUp(self):
        self.base_tenant = Tenant.objects.create(name="Base", slug="base")
        self.admin = User.objects.create_superuser(
            email="admin@fr.test", password="admin123", tenant=self.base_tenant,
        )
        # Roles are seeded by migration 0008 with UPPER-CASE codes; the app
        # matches them with code__iexact, so reuse the seeded rows rather than
        # creating lower-case duplicates.
        self.franchise_role = self.role_named("franchise", 4)
        self.business_role = self.role_named("business_user", 5)
        self.consultant_role = self.role_named("consultant", 3)

    @staticmethod
    def role_named(code, tier_level):
        role = Role.objects.filter(code__iexact=code).first()
        if role is None:
            role = Role.objects.create(
                code=code.upper(), name=code.replace("_", " ").title(),
                tier_level=tier_level,
            )
        return role

    # ---- fixture helpers -------------------------------------------------

    def holder(self, email, role=None):
        return User.objects.create_user(
            email=email, password="x", is_active=True, tenant=self.base_tenant,
            role=role or self.franchise_role, application_status="approved",
        )

    def node(self, name, level=FranchiseLevel.MASTER, *, parent=None, owner=None,
             company=None, status=FranchiseUnitStatus.ACTIVE, city=""):
        return Tenant.objects.create(
            name=name, slug=name.lower().replace(" ", "-"),
            franchise_level=level, franchise_status=status, parent=parent,
            owner_user=owner, owner_company=company,
            territory_country="IN", territory_city=city,
        )

    def remove(self, node, **post):
        self.client.login(email="admin@fr.test", password="admin123")
        return self.client.post(reverse("franchise-remove", args=[node.id]), post)


class FranchiseRemovePermissionTests(FranchiseRemovalTestCase):

    def test_requires_login(self):
        target = self.node("Anon Target", owner=self.holder("anon@fr.test"))
        response = self.client.post(reverse("franchise-remove", args=[target.id]))
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertFalse(target.is_deleted)

    def test_non_superuser_denied(self):
        owner = self.holder("holder@fr.test")
        target = self.node("Holder Master", owner=owner)
        self.client.login(email="holder@fr.test", password="x")
        response = self.client.post(reverse("franchise-remove", args=[target.id]))
        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertFalse(target.is_deleted)

    def test_get_not_allowed(self):
        target = self.node("Get Target", owner=self.holder("get@fr.test"))
        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.get(reverse("franchise-remove", args=[target.id]))
        self.assertEqual(response.status_code, 405)

    def test_already_removed_is_404(self):
        target = self.node("Twice", owner=self.holder("twice@fr.test"))
        self.assertEqual(self.remove(target).status_code, 302)
        self.assertEqual(self.remove(target).status_code, 404)

    def test_plain_tenant_is_not_removable_here(self):
        """franchise-remove is for franchise nodes; a plain partition uses
        tenant-delete, so it must not be reachable through this endpoint."""
        plain = Tenant.objects.create(name="Plain Partition", slug="plain-partition")
        self.assertEqual(self.remove(plain).status_code, 404)
        plain.refresh_from_db()
        self.assertFalse(plain.is_deleted)


class FranchiseRemoveEveryLevelTests(FranchiseRemovalTestCase):

    def test_every_level_and_status_can_be_removed(self):
        cases = [
            (FranchiseLevel.MASTER, FranchiseUnitStatus.ACTIVE),
            (FranchiseLevel.NATIONAL, FranchiseUnitStatus.SUSPENDED),
            (FranchiseLevel.REGIONAL, FranchiseUnitStatus.PENDING_CONTRACT),
            (FranchiseLevel.MICRO, FranchiseUnitStatus.PENDING_PAYMENT),
        ]
        for index, (level, status) in enumerate(cases):
            owner = self.holder(f"{level.lower()}{index}@fr.test")
            target = self.node(f"Node {level} {index}", level, owner=owner,
                               status=status, city=f"City{index}")
            response = self.remove(target, reason="territory reassigned")
            self.assertEqual(response.status_code, 302, msg=f"{level}/{status}")

            target = Tenant.all_objects.get(id=target.id)
            self.assertTrue(target.is_deleted, msg=f"{level}/{status}")
            self.assertFalse(target.is_active, msg=f"{level}/{status}")
            self.assertEqual(target.franchise_status, FranchiseUnitStatus.TERMINATED)
            self.assertIsNotNone(target.terminated_at)

            owner.refresh_from_db()
            self.assertEqual(owner.role.code, self.business_role.code,
                             msg=f"{level}/{status}")

    def test_franchise_held_by_a_company_is_removable(self):
        owner = self.holder("co@fr.test")
        company = Company.objects.create(
            tenant=self.base_tenant, name="Holder Co", owner_user=owner,
        )
        target = self.node("Company Master", owner=owner, company=company)
        self.assertEqual(self.remove(target).status_code, 302)
        self.assertTrue(Tenant.all_objects.get(id=target.id).is_deleted)

    def test_node_without_owner_is_removable(self):
        """Admin-created nodes can sit unassigned; removal must not need a holder."""
        target = self.node("Unowned Master")
        self.assertEqual(self.remove(target).status_code, 302)
        self.assertTrue(Tenant.all_objects.get(id=target.id).is_deleted)

    def test_reason_is_audited(self):
        target = self.node("Audited", owner=self.holder("audit@fr.test"))
        self.remove(target, reason="contract breach")
        log = AuditLog.objects.filter(action="franchise.removed",
                                      entity_id=str(target.id)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor_id, self.admin.id)
        self.assertEqual(log.metadata["reason"], "contract breach")


class FranchiseRemoveCascadeTests(FranchiseRemovalTestCase):

    def setUp(self):
        super().setUp()
        self.master_owner = self.holder("master@fr.test")
        self.national_owner = self.holder("national@fr.test")
        self.regional_owner = self.holder("regional@fr.test")

        self.master = self.node("Cascade Master", FranchiseLevel.MASTER,
                                owner=self.master_owner)
        self.national = self.node("Cascade National", FranchiseLevel.NATIONAL,
                                  parent=self.master, owner=self.national_owner)
        self.regional = self.node("Cascade Regional", FranchiseLevel.REGIONAL,
                                  parent=self.national, owner=self.regional_owner)

    def test_whole_subtree_is_removed(self):
        self.remove(self.master)
        for node in (self.master, self.national, self.regional):
            fresh = Tenant.all_objects.get(id=node.id)
            self.assertTrue(fresh.is_deleted, msg=node.name)
            self.assertEqual(fresh.franchise_status, FranchiseUnitStatus.TERMINATED,
                             msg=node.name)

    def test_every_holder_in_the_subtree_is_reset(self):
        self.remove(self.master)
        for owner in (self.master_owner, self.national_owner, self.regional_owner):
            owner.refresh_from_db()
            self.assertEqual(owner.role.code, self.business_role.code, msg=owner.email)

    def test_removing_a_child_leaves_the_parent_alone(self):
        self.remove(self.national)
        self.master.refresh_from_db()
        self.assertFalse(self.master.is_deleted)
        self.assertEqual(self.master.franchise_status, FranchiseUnitStatus.ACTIVE)
        self.master_owner.refresh_from_db()
        self.assertEqual(self.master_owner.role.code, self.franchise_role.code)
        # ...but the child's own subtree still goes with it.
        self.assertTrue(Tenant.all_objects.get(id=self.regional.id).is_deleted)

    def test_each_removed_node_is_audited(self):
        self.remove(self.master)
        ids = {self.master.id, self.national.id, self.regional.id}
        audited = set(
            AuditLog.objects.filter(action="franchise.removed")
            .values_list("entity_id", flat=True)
        )
        self.assertTrue(ids.issubset(audited), msg=sorted(map(str, audited)))

    def test_cascade_is_recorded_on_the_descendants(self):
        self.remove(self.master)
        child_log = AuditLog.objects.filter(
            action="franchise.removed", entity_id=str(self.national.id),
        ).first()
        self.assertEqual(child_log.metadata["removed_with"], str(self.master.id))
        own_log = AuditLog.objects.filter(
            action="franchise.removed", entity_id=str(self.master.id),
        ).first()
        self.assertEqual(own_log.metadata["removed_with"], "")

    def test_holders_are_notified(self):
        self.remove(self.master, reason="restructuring")
        for owner in (self.master_owner, self.national_owner, self.regional_owner):
            note = Notification.objects.filter(
                recipient=owner, kind=Notification.KIND_FRANCHISE_REMOVED,
            ).first()
            self.assertIsNotNone(note, msg=owner.email)
            self.assertIn("restructuring", note.body)

    def test_success_message_counts_the_subtree(self):
        response = self.remove(self.master, follow=False)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(any("2" in m for m in messages), msgs := messages)


class FranchiseRemoveConsultantTests(FranchiseRemovalTestCase):

    def test_consultant_assignments_are_terminated(self):
        owner = self.holder("rosterowner@fr.test")
        target = self.node("Roster Master", owner=owner)
        consultant = self.holder("standard@fr.test", role=self.consultant_role)
        assignment = ConsultantAssignment.objects.create(
            franchise_node=target, consultant_user=consultant,
            consultant_type=ConsultantType.STANDARD_CONSULTANT,
            status=ConsultantAssignmentStatus.ACTIVE,
        )
        self.remove(target)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, ConsultantAssignmentStatus.TERMINATED)

    def test_micro_owner_self_assignment_is_terminated(self):
        """The Micro owner's own roster row is what carries their certify /
        sell-plans rights, so it must not survive the removal."""
        owner = self.holder("microowner@fr.test")
        target = self.node("Micro Node", FranchiseLevel.MICRO, owner=owner,
                           city="Pune")
        self_row = ConsultantAssignment.objects.create(
            franchise_node=target, consultant_user=owner,
            consultant_type=ConsultantType.MICRO_FRANCHISE_OWNER,
            status=ConsultantAssignmentStatus.ACTIVE,
        )
        self.remove(target)
        self_row.refresh_from_db()
        self.assertEqual(self_row.status, ConsultantAssignmentStatus.TERMINATED)

    def test_consultant_who_also_holds_a_franchise_keeps_their_role(self):
        owner = self.holder("consholder@fr.test", role=self.consultant_role)
        target = self.node("Cons Held", FranchiseLevel.MICRO, owner=owner,
                           city="Nashik")
        self.remove(target)
        owner.refresh_from_db()
        self.assertEqual(owner.role.code, self.consultant_role.code)

    def test_removal_frees_the_holder_to_be_granted_a_new_franchise(self):
        """One franchise per owner is a model invariant, so a holder can only
        get a different territory after the old one is actually removed."""
        owner = self.holder("regrant@fr.test")
        first = self.node("First Master", owner=owner)
        with self.assertRaises(ValidationError):
            self.node("Second Regional", FranchiseLevel.REGIONAL, owner=owner,
                      city="Delhi")
        self.remove(first)
        replacement = self.node("Second Regional", FranchiseLevel.REGIONAL,
                                owner=owner, city="Delhi")
        self.assertEqual(replacement.franchise_status, FranchiseUnitStatus.ACTIVE)


class FranchiseRemoveApplicationTests(FranchiseRemovalTestCase):

    def test_source_application_is_cancelled_with_a_reason(self):
        owner = self.holder("app@fr.test")
        target = self.node("App Master", owner=owner)
        application = FranchiseApplication.objects.create(
            applicant_user=owner, requested_level=FranchiseLevel.MASTER,
            requested_country="IN",
            application_status=FranchiseApplicationStatus.APPROVED,
            created_franchise=target,
        )
        self.remove(target)
        application.refresh_from_db()
        self.assertEqual(application.application_status,
                         FranchiseApplicationStatus.CANCELLED)
        self.assertTrue(application.board_note)

    def test_pending_request_routed_to_a_removed_node_is_closed(self):
        """Its reviewer no longer exists, so leaving it SUBMITTED would keep the
        applicant waiting on a decision that can never come."""
        parent_owner = self.holder("routedparent@fr.test")
        parent = self.node("Routed Parent", owner=parent_owner)
        applicant = self.holder("applicant@fr.test", role=self.business_role)
        pending = FranchiseApplication.objects.create(
            applicant_user=applicant, requested_level=FranchiseLevel.REGIONAL,
            requested_country="IN", parent_franchise=parent,
            application_status=FranchiseApplicationStatus.SUBMITTED,
        )
        self.remove(parent)
        pending.refresh_from_db()
        self.assertEqual(pending.application_status,
                         FranchiseApplicationStatus.CANCELLED)

    def test_rejected_application_is_left_alone(self):
        owner = self.holder("rejected@fr.test")
        target = self.node("Rejected Src", owner=owner)
        application = FranchiseApplication.objects.create(
            applicant_user=owner, requested_level=FranchiseLevel.MASTER,
            requested_country="IN",
            application_status=FranchiseApplicationStatus.REJECTED,
            created_franchise=target,
        )
        self.remove(target)
        application.refresh_from_db()
        self.assertEqual(application.application_status,
                         FranchiseApplicationStatus.REJECTED)


class FranchiseRemoveFreesTerritoryTests(FranchiseRemovalTestCase):

    def test_micro_territory_can_be_granted_again(self):
        """Micro exclusivity is a DB constraint on ACTIVE rows: removal has to
        TERMINATE the node, or the territory stays blocked forever."""
        first_owner = self.holder("first@fr.test")
        first = self.node("Micro One", FranchiseLevel.MICRO, owner=first_owner,
                          city="Kochi")
        self.remove(first)

        second_owner = self.holder("second@fr.test")
        replacement = self.node("Micro Two", FranchiseLevel.MICRO,
                                owner=second_owner, city="Kochi")
        self.assertEqual(replacement.franchise_status, FranchiseUnitStatus.ACTIVE)


class FranchiseListRemovalUiTests(FranchiseRemovalTestCase):

    def test_admin_sees_remove_for_a_franchise_row(self):
        owner = self.holder("uiowner@fr.test")
        target = self.node("UI Master", owner=owner)
        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.get(reverse("tenants"))
        self.assertContains(response, reverse("franchise-remove", args=[target.id]))

    def test_plain_tenant_row_keeps_the_generic_delete(self):
        plain = Tenant.objects.create(name="Plain Row", slug="plain-row")
        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.get(reverse("tenants"))
        self.assertContains(response, reverse("tenant-delete", args=[plain.id]))
        self.assertNotContains(response, reverse("franchise-remove", args=[plain.id]))

    def test_remove_appears_in_the_franchise_requests_queue(self):
        owner = self.holder("queue@fr.test")
        target = self.node("Queue Master", owner=owner)
        FranchiseApplication.objects.create(
            applicant_user=owner, requested_level=FranchiseLevel.MASTER,
            requested_country="IN",
            application_status=FranchiseApplicationStatus.APPROVED,
            created_franchise=target,
        )
        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.get(reverse("franchise-applications"))
        self.assertContains(response, reverse("franchise-remove", args=[target.id]))


class TenantDeleteCascadesTests(FranchiseRemovalTestCase):
    """The Franchises-list delete used to soft-delete a single row, leaving the
    sub-franchises alive and ACTIVE under a parent the app filters out."""

    def test_tenant_delete_on_a_franchise_node_removes_the_subtree(self):
        parent_owner = self.holder("legacyparent@fr.test")
        child_owner = self.holder("legacychild@fr.test")
        parent = self.node("Legacy Master", owner=parent_owner)
        child = self.node("Legacy National", FranchiseLevel.NATIONAL,
                          parent=parent, owner=child_owner)

        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.post(reverse("tenant-delete", args=[parent.id]))
        self.assertEqual(response.status_code, 302)

        child = Tenant.all_objects.get(id=child.id)
        self.assertTrue(child.is_deleted)
        self.assertEqual(child.franchise_status, FranchiseUnitStatus.TERMINATED)
        child_owner.refresh_from_db()
        self.assertEqual(child_owner.role.code, self.business_role.code)

    def test_tenant_delete_still_works_for_a_plain_tenant(self):
        plain = Tenant.objects.create(name="Plain Delete", slug="plain-delete")
        self.client.login(email="admin@fr.test", password="admin123")
        response = self.client.post(reverse("tenant-delete", args=[plain.id]))
        self.assertEqual(response.status_code, 302)
        plain = Tenant.all_objects.get(id=plain.id)
        self.assertTrue(plain.is_deleted)
        self.assertTrue(
            AuditLog.objects.filter(action="tenant.deleted",
                                    entity_id=str(plain.id)).exists()
        )
