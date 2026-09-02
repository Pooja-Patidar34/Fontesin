"""Staff requests land in the tab named after their role.

Before (Sep 2026) a coordinator could arrive through either of two doors — an
upgrade request from an existing Business User (CoordinatorRequest) in
"Coordinator Requests", or a registration application (User.application_status)
in a separate "Staff Applications" list — and an admin had to know which to
check. Consultants had no tab of their own at all, and their sign-ups were not
even counted in the sidebar badge, so a waiting consultant was invisible.

Each role's requests now appear in exactly one queue, whichever way they arrived.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import CoordinatorRequest, Role, Tenant, User


class StaffRequestRoutingTests(TestCase):

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Base", slug="base-routing")
        self.admin = User.objects.create_user(
            email="admin@routing.test", password="x", is_active=True,
            tenant=self.tenant, is_staff=True, is_superuser=True,
            application_status="approved",
        )
        self.client.force_login(self.admin)

    # -- helpers ----------------------------------------------------------

    def role(self, code):
        existing = Role.objects.filter(code__iexact=code).first()
        if existing is not None:
            return existing
        return Role.objects.create(code=code, name=code.title(), tier_level=3)

    def signup(self, email, role_code, status="submitted"):
        """Someone who REGISTERED under a staff role and is awaiting a decision."""
        return User.objects.create_user(
            email=email, password="x", is_active=True, tenant=self.tenant,
            role=self.role(role_code), application_status=status,
        )

    def upgrade_request(self, email):
        """An existing Business User asking to become a coordinator."""
        user = User.objects.create_user(
            email=email, password="x", is_active=True, tenant=self.tenant,
            role=self.role("business_user"), application_status="approved",
        )
        return CoordinatorRequest.objects.create(
            user=user, status=CoordinatorRequest.STATUS_PENDING,
        )

    def visit(self, name):
        response = self.client.get(reverse(name), SERVER_NAME="localhost")
        self.assertEqual(response.status_code, 200)
        return response

    def emails(self, response, key):
        return {u.email for u in response.context[key]}

    # -- coordinator: both doors, one tab ---------------------------------

    def test_coordinator_tab_shows_upgrades_and_signups_together(self):
        self.upgrade_request("upgrader@routing.test")
        self.signup("newcoord@routing.test", "coordinator")

        response = self.visit("coordinator-requests")
        self.assertEqual(
            {r.user.email for r in response.context["pending"]},
            {"upgrader@routing.test"},
        )
        self.assertEqual(
            self.emails(response, "signup_pending"), {"newcoord@routing.test"},
        )

    def test_a_coordinator_signup_no_longer_sits_in_the_general_queue(self):
        self.signup("newcoord@routing.test", "coordinator")
        response = self.visit("applications")
        self.assertNotIn("newcoord@routing.test", self.emails(response, "pending"))

    # -- consultant: its own tab ------------------------------------------

    def test_consultant_signups_appear_in_the_consultant_tab(self):
        self.signup("newconsultant@routing.test", "consultant")
        response = self.visit("consultant-requests")
        self.assertEqual(
            self.emails(response, "signup_pending"), {"newconsultant@routing.test"},
        )

    def test_a_consultant_signup_no_longer_sits_in_the_general_queue(self):
        self.signup("newconsultant@routing.test", "consultant")
        response = self.visit("applications")
        self.assertNotIn("newconsultant@routing.test", self.emails(response, "pending"))

    def test_the_queues_do_not_bleed_into_each_other(self):
        self.signup("c@routing.test", "consultant")
        self.signup("k@routing.test", "coordinator")
        self.assertNotIn(
            "k@routing.test",
            self.emails(self.visit("consultant-requests"), "signup_pending"),
        )
        self.assertNotIn(
            "c@routing.test",
            self.emails(self.visit("coordinator-requests"), "signup_pending"),
        )

    # -- franchise keeps the general queue --------------------------------

    def test_franchise_signups_still_use_the_general_queue(self):
        """Untouched on purpose: the franchise role has no sign-up tab of its
        own, so removing it from here would strand it."""
        self.signup("newfranchise@routing.test", "franchise")
        response = self.visit("applications")
        self.assertIn("newfranchise@routing.test", self.emails(response, "pending"))

    # -- acting on a request ----------------------------------------------

    def test_approving_returns_to_the_role_s_own_queue(self):
        user = self.signup("newconsultant@routing.test", "consultant")
        response = self.client.post(
            reverse("application-action", args=[user.id]),
            {"decision": "approve"}, SERVER_NAME="localhost",
        )
        self.assertRedirects(
            response, reverse("consultant-requests"),
            fetch_redirect_response=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.application_status, "approved")

    def test_approving_a_coordinator_signup_returns_to_coordinator_requests(self):
        user = self.signup("newcoord@routing.test", "coordinator")
        response = self.client.post(
            reverse("application-action", args=[user.id]),
            {"decision": "approve"}, SERVER_NAME="localhost",
        )
        self.assertRedirects(
            response, reverse("coordinator-requests"),
            fetch_redirect_response=False,
        )

    def test_declining_records_the_reason_and_keeps_them_out(self):
        user = self.signup("newconsultant@routing.test", "consultant")
        self.client.post(
            reverse("application-action", args=[user.id]),
            {"decision": "decline", "decline_reason": "Not a fit"},
            SERVER_NAME="localhost",
        )
        user.refresh_from_db()
        self.assertEqual(user.application_status, "declined")
        self.assertEqual(user.application_decline_reason, "Not a fit")

    # -- the badges match the pages ---------------------------------------

    def test_a_waiting_consultant_is_counted_in_the_sidebar(self):
        """The old badge hardcoded coordinator+franchise, so a pending consultant
        produced no count at all and could sit unnoticed while locked out."""
        self.signup("newconsultant@routing.test", "consultant")
        context = self.visit("consultant-requests").context
        self.assertEqual(context["pending_consultant_request_count"], 1)
        self.assertEqual(context["pending_application_count"], 0)

    def test_coordinator_badge_counts_both_doors(self):
        self.upgrade_request("upgrader@routing.test")
        self.signup("newcoord@routing.test", "coordinator")
        context = self.visit("coordinator-requests").context
        self.assertEqual(context["pending_coordinator_request_count"], 2)

    def test_the_total_badge_still_adds_every_queue_once(self):
        self.upgrade_request("upgrader@routing.test")
        self.signup("newcoord@routing.test", "coordinator")
        self.signup("newconsultant@routing.test", "consultant")
        self.signup("newfranchise@routing.test", "franchise")
        context = self.visit("applications").context
        self.assertEqual(
            context["pending_requests_total"],
            context["pending_coordinator_request_count"]
            + context["pending_consultant_request_count"]
            + context["pending_application_count"]
            + context["pending_franchise_application_count"],
        )

    # -- the retired Staff Applications tab -------------------------------

    def test_the_staff_applications_tab_is_gone_from_the_sidebar(self):
        """Consultants and coordinators have their own tabs now, and a franchise
        account is never self-created (spec §16 #1), so the catch-all queue has
        nothing to show and is not rendered."""
        self.upgrade_request("upgrader@routing.test")
        self.signup("newcoord@routing.test", "coordinator")
        self.signup("newconsultant@routing.test", "consultant")
        body = self.visit("coordinator-requests").content.decode()
        self.assertNotIn("Staff Applications", body)

    def test_it_comes_back_only_if_someone_would_otherwise_be_stranded(self):
        """Hidden while empty rather than deleted: anyone left in this queue is
        locked out by the approval middleware, so the row has to reappear rather
        than leave them behind a direct URL."""
        self.signup("legacy@routing.test", "franchise")
        body = self.visit("coordinator-requests").content.decode()
        self.assertIn("Staff Applications", body)

    # -- access -----------------------------------------------------------

    def test_the_consultant_queue_is_superuser_only(self):
        outsider = self.signup("outsider@routing.test", "consultant", status="approved")
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("consultant-requests"), SERVER_NAME="localhost",
        )
        self.assertEqual(response.status_code, 403)
