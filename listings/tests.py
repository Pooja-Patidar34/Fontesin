"""
Listings Engine - API tests (cookbook Section 15 - functional + negative).

Self-contained: each fixture (tenant, roles, users, company, NACE code) is built
in setUp, so the suite runs against a clean test database with no seed data.
"""

import json

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Tenant, Role, User, Company, NaceCode, Notification
from listings import api


def _json(resp):
    resp.render()
    return json.loads(resp.content or b"{}")

class ListingsAPITestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.tenant = Tenant.objects.create(name="Acme", slug="acme")

        self.business_role = Role.objects.create(
            name="Business User", code="business_user", tier_level=1
        )

        self.owner = User.objects.create_user(
            email="owner@example.com", password="x",
            first_name="Owner", last_name="One",
            tenant=self.tenant, role=self.business_role,
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="x",
            first_name="Other", last_name="Two",
            tenant=self.tenant, role=self.business_role,
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com", password="x",
            first_name="Admin", last_name="Root",
            tenant=self.tenant,
        )

        self.company = Company.objects.create(
            tenant=self.tenant, name="Acme Ltd", owner_user=self.owner
        )
        # `other` is a Business User with their OWN company, so they satisfy the
        # onboarding middleware (RequireCompanyForBusinessUser) on web POSTs.
        self.other_company = Company.objects.create(
            tenant=self.tenant, name="Other Co", owner_user=self.other
        )
        self.other.primary_company = self.other_company
        self.other.save(update_fields=["primary_company"])

        self.nace = NaceCode.objects.create(code="25.11", title="Metal structures", level=4)

    # ---- helpers ----
    def call(self, view, method, user, listing_id=None, data=None):
        req = getattr(self.factory, method)("/", data or {}, format="json")
        force_authenticate(req, user=user)
        kwargs = {"listing_id": listing_id} if listing_id else {}
        return _json(view(req, **kwargs))

    def valid_payload(self, **overrides):
        payload = dict(
            listing_type="offer", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="Steel Pipes Offer", description="High grade steel pipes in bulk.",
            keywords=["steel", "pipes"], visibility_scope="public",
            status="active", module_id="products_services",
            price_without_vat="99.90", currency="EUR",
        )
        payload.update(overrides)
        return payload

    def create_listing(self, user=None, **overrides):
        req = self.factory.post("/", self.valid_payload(**overrides), format="json")
        force_authenticate(req, user=user or self.owner)
        return api.ListingCollectionAPIView.as_view()(req)

    # ---- functional (cookbook 40-54) ----
    def test_create_product_offer_active_sets_published_at(self):
        resp = self.create_listing()
        self.assertEqual(resp.status_code, 201)
        data = _json(resp)["data"]
        self.assertEqual(data["status"], "active")
        self.assertIsNotNone(data["published_at"])

    def test_create_draft_has_no_published_at(self):
        resp = self.create_listing(status="draft")
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(_json(resp)["data"]["published_at"])

    def test_deactivate_and_activate(self):
        lid = _json(self.create_listing())["data"]["id"]
        body = self.call(api.ListingDeactivateAPIView.as_view(), "post", self.owner, lid)
        self.assertEqual(body["data"]["status"], "inactive")
        body = self.call(api.ListingActivateAPIView.as_view(), "post", self.owner, lid)
        self.assertEqual(body["data"]["status"], "active")

    def test_search_returns_only_active(self):
        self.create_listing()
        self.create_listing(status="draft", title="Draft Offer Hidden")
        body = self.call(api.ListingCollectionAPIView.as_view(), "get", self.other)
        self.assertTrue(all(x["status"] == "active" for x in body["data"]))

    def test_reaction_created_and_routed_to_owner(self):
        lid = _json(self.create_listing())["data"]["id"]
        body = self.call(api.ListingReactionAPIView.as_view(), "post", self.other, lid, {"message": "Interested"})
        self.assertEqual(body["data"]["to_user"], str(self.owner.id))
        self.assertEqual(body["data"]["status"], "new")

    def test_owner_sees_received_reaction(self):
        lid = _json(self.create_listing())["data"]["id"]
        self.call(api.ListingReactionAPIView.as_view(), "post", self.other, lid, {})
        body = self.call(api.MyReactionsAPIView.as_view(), "get", self.owner)
        self.assertEqual(len(body["data"]), 1)

    # ---- negative (cookbook 55-69) ----
    def test_create_requires_title(self):
        resp = self.create_listing(title="ab")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("title", _json(resp)["errors"])

    def test_create_requires_description(self):
        resp = self.create_listing(description="short")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("description", _json(resp)["errors"])

    def test_price_without_currency_rejected(self):
        resp = self.create_listing(currency=None)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("currency", _json(resp)["errors"])

    def test_product_image_on_service_offer_rejected(self):
        resp = self.create_listing(category_type="service", product_image_id=str(self.company.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("product_image_id", _json(resp)["errors"])

    def test_product_image_on_demand_rejected(self):
        resp = self.create_listing(listing_type="demand", product_image_id=str(self.company.id))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("product_image_id", _json(resp)["errors"])

    def test_company_not_owned_rejected(self):
        foreign = Company.objects.create(tenant=self.tenant, name="Foreign", owner_user=self.other)
        resp = self.create_listing(owner_company=str(foreign.id))
        self.assertEqual(resp.status_code, 403)

    def test_other_user_cannot_edit(self):
        lid = _json(self.create_listing())["data"]["id"]
        req = self.factory.put("/", {"title": "Hacked Title Here"}, format="json")
        force_authenticate(req, user=self.other)
        resp = api.ListingDetailAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 403)

    def test_self_reaction_blocked(self):
        lid = _json(self.create_listing())["data"]["id"]
        req = self.factory.post("/", {}, format="json")
        force_authenticate(req, user=self.owner)
        resp = api.ListingReactionAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_reaction_blocked(self):
        lid = _json(self.create_listing())["data"]["id"]
        self.call(api.ListingReactionAPIView.as_view(), "post", self.other, lid, {})
        req = self.factory.post("/", {}, format="json")
        force_authenticate(req, user=self.other)
        resp = api.ListingReactionAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 409)

    # ---- admin (cookbook 65-69) ----
    def test_admin_suspend_requires_reason(self):
        lid = _json(self.create_listing())["data"]["id"]
        req = self.factory.post("/", {"reason": "no"}, format="json")
        force_authenticate(req, user=self.admin)
        resp = api.ListingSuspendAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 400)

    def test_admin_suspend_then_business_user_blocked_and_reactivate(self):
        lid = _json(self.create_listing())["data"]["id"]

        # suspend
        body = self.call(api.ListingSuspendAPIView.as_view(), "post", self.admin, lid, {"reason": "Policy violation"})
        self.assertEqual(body["data"]["status"], "suspended")

        # business user cannot edit suspended
        req = self.factory.put("/", {"title": "New Legit Title"}, format="json")
        force_authenticate(req, user=self.owner)
        resp = api.ListingDetailAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 403)

        # suspended hidden from search
        body = self.call(api.ListingCollectionAPIView.as_view(), "get", self.other)
        self.assertNotIn(lid, [x["id"] for x in body["data"]])

        # admin reactivate
        body = self.call(api.ListingReactivateAPIView.as_view(), "post", self.admin, lid, {})
        self.assertEqual(body["data"]["status"], "active")

    def test_non_admin_cannot_suspend(self):
        lid = _json(self.create_listing())["data"]["id"]
        req = self.factory.post("/", {"reason": "Trying to suspend"}, format="json")
        force_authenticate(req, user=self.other)
        resp = api.ListingSuspendAPIView.as_view()(req, listing_id=lid)
        self.assertEqual(resp.status_code, 403)

    def test_reaction_notifies_owner(self):
        lid = _json(self.create_listing())["data"]["id"]
        self.call(api.ListingReactionAPIView.as_view(), "post", self.other, lid, {})
        note = Notification.objects.filter(recipient=self.owner, sender=self.other).first()
        self.assertIsNotNone(note)

    def test_suspend_notifies_owner(self):
        lid = _json(self.create_listing())["data"]["id"]
        self.call(api.ListingSuspendAPIView.as_view(), "post", self.admin, lid, {"reason": "Policy violation"})
        note = Notification.objects.filter(recipient=self.owner, sender=self.admin).first()
        self.assertIsNotNone(note)

    # ---- web (template) flows ----
    def test_web_reaction_and_status_workflow(self):
        from django.test import Client
        from django.urls import reverse
        from listings.models import ListingReaction

        lid = _json(self.create_listing())["data"]["id"]
        web = Client()

        # other user reacts via the HTML page
        web.force_login(self.other)
        r = web.post(reverse("listings_web:react", args=[lid]), {"message": "Hi"}, SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        rx = ListingReaction.objects.get(listing_id=lid, from_user=self.other)
        self.assertEqual(rx.status, "new")

        # owner advances the reaction status
        web.force_login(self.owner)
        web.post(reverse("listings_web:reaction-set-status"),
                 {"reaction_id": str(rx.id), "status": "replied"}, SERVER_NAME="localhost")
        rx.refresh_from_db()
        self.assertEqual(rx.status, "replied")

        # non-recipient cannot change it
        web.force_login(self.other)
        web.post(reverse("listings_web:reaction-set-status"),
                 {"reaction_id": str(rx.id), "status": "closed"}, SERVER_NAME="localhost")
        rx.refresh_from_db()
        self.assertEqual(rx.status, "replied")

    def test_web_module_create_with_specific_data_and_image(self):
        from django.test import Client
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        from listings.models import Listing

        web = Client()
        web.force_login(self.owner)
        png = SimpleUploadedFile("p.png", b"\x89PNG\r\n", content_type="image/png")
        data = dict(
            listing_type="offer", module_id="investments", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="Series A Round", description="Raising capital for EU expansion plans.",
            keywords="capital, equity", visibility_scope="public", action="publish",
            ms_investment_type="Equity", ms_ticket_size="500k", product_image=png,
        )
        r = web.post(reverse("listings_web:add") + "?type=offer&module=investments",
                     data, SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        l = Listing.objects.get(title="Series A Round")
        self.assertEqual(l.module_id, "investments")
        self.assertEqual(l.module_specific_data.get("investment_type"), "Equity")
        self.assertTrue(bool(l.product_image))

    def test_web_module_required_field_enforced(self):
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        data = dict(
            listing_type="offer", module_id="investments", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="No Type Round", description="Missing the required investment type field.",
            keywords="capital", visibility_scope="public", action="publish",
            ms_investment_type="",
        )
        r = web.post(reverse("listings_web:add") + "?type=offer&module=investments",
                     data, SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Investment Type is required", r.content)

    def test_web_pages_render(self):
        from django.test import Client
        from django.urls import reverse

        lid = _json(self.create_listing())["data"]["id"]
        web = Client()
        web.force_login(self.owner)
        for name, args in [
            ("modules:dashboard", []),
            ("modules:landing", ["products-services"]),
            ("listings_web:browse", []),
            ("listings_web:detail", [lid]),
            ("listings_web:add", []),
            ("listings_web:edit", [lid]),
            ("listings_web:my-offers", []),
            ("listings_web:my-listings", []),
            ("listings_web:history", [lid]),
        ]:
            url = reverse(name, args=args)
            self.assertEqual(web.get(url, SERVER_NAME="localhost").status_code, 200, url)

        # Add-demand variant (amber accent, no offer-details section)
        self.assertEqual(
            web.get(reverse("listings_web:add") + "?type=demand", SERVER_NAME="localhost").status_code,
            200,
        )

    def test_audit_log_records_status_changes(self):
        lid = _json(self.create_listing())["data"]["id"]
        self.call(api.ListingSuspendAPIView.as_view(), "post", self.admin, lid, {"reason": "Policy violation"})
        body = self.call(api.ListingAuditLogAPIView.as_view(), "get", self.owner, lid)
        actions = [x["action"] for x in body["data"]]
        self.assertIn("listing_created", actions)
        self.assertIn("listing_suspended", actions)
