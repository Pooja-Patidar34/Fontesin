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
from listings.models import Listing


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

        # Professional modules are paid-only (listings.module_registry), so an
        # account that publishes into one must sit on a paid plan. These tests
        # are about listing CRUD, not about the plan gate, so both owners get a
        # Basic subscription on their company; the gate itself is covered
        # separately. Without this every module call 403s on the Free floor.
        self._give_paid_plan(self.owner, self.company)
        self._give_paid_plan(self.other, self.other_company)

        self.nace = NaceCode.objects.create(code="25.11", title="Metal structures", level=4)

    @staticmethod
    def _give_paid_plan(user, company):
        """Mirror billing.utils.ensure_free_subscription's row shape, on Basic:
        start_date / end_date are NOT NULL, so they have to be set here too."""
        from dateutil.relativedelta import relativedelta
        from django.utils import timezone
        from billing.models import CommercialPlan, Subscription

        plan, _ = CommercialPlan.objects.get_or_create(
            code="basic",
            defaults={"name": "Basic Plan", "price": 150, "billing_period": "yearly"},
        )
        now = timezone.now()
        Subscription.objects.create(
            user=user, company=company, plan=plan,
            billing_period=plan.billing_period, status="active",
            start_date=now, end_date=now + relativedelta(years=1),
        )

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

    def test_title_accepts_100_chars(self):
        resp = self.create_listing(title="A" * 100)
        self.assertEqual(resp.status_code, 201)

    def test_title_over_100_chars_rejected(self):
        resp = self.create_listing(title="A" * 101)
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

    def test_web_my_offers_reaction_chip_carries_one_count(self):
        """The chip shows the total once; unread is the accent state, not a
        second number sitting next to it."""
        from django.test import Client
        from django.urls import reverse
        from listings.models import ListingReaction

        lid = _json(self.create_listing())["data"]["id"]
        web = Client()
        web.force_login(self.other)
        web.post(reverse("listings_web:react", args=[lid]), {"message": "Hi"}, SERVER_NAME="localhost")

        web.force_login(self.owner)
        r = web.get(reverse("listings_web:my-offers"), SERVER_NAME="localhost")
        # match the markup, not the class name — the stylesheet is inlined on the
        # page, so a bare class-name search hits the CSS rule too.
        chip = 'class="ps-react ps-react--new"'
        dot = '<span class="ps-react__dot"'
        body = r.content.decode()
        self.assertIn(chip, body)
        self.assertIn(dot, body)
        self.assertNotIn('<span class="ps-react__new">', body)  # the old badge is gone

        # read it, and the chip drops back to the quiet state
        rx = ListingReaction.objects.get(listing_id=lid)
        rx.status = ListingReaction.READ
        rx.save(update_fields=["status"])
        body = web.get(reverse("listings_web:my-offers"), SERVER_NAME="localhost").content.decode()
        self.assertIn('class="ps-react"', body)
        self.assertNotIn(chip, body)
        self.assertNotIn(dot, body)

    def test_web_reaction_without_primary_company_is_attributed_to_owned_company(self):
        """A reaction is company-to-company, but plenty of accounts have no
        `primary_company` set — that null used to hit the NOT NULL constraint on
        ListingReaction.from_company and 500 on "Send Interest"."""
        from django.test import Client
        from django.urls import reverse
        from listings.models import ListingReaction

        lid = _json(self.create_listing())["data"]["id"]
        self.other.primary_company = None
        self.other.save(update_fields=["primary_company"])

        web = Client()
        web.force_login(self.other)
        r = web.post(reverse("listings_web:react", args=[lid]),
                     {"message": "Interested"}, SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        rx = ListingReaction.objects.get(listing_id=lid, from_user=self.other)
        self.assertEqual(rx.from_company_id, self.other_company.id)

    def test_web_reaction_follows_the_active_company(self):
        """Owning several companies, the reaction is attributed to the one the
        session is acting as — the same company you'd publish a listing as."""
        from django.test import Client
        from django.urls import reverse
        from listings.models import ListingReaction

        second = Company.objects.create(
            tenant=self.tenant, name="Other Co Two", owner_user=self.other,
        )
        lid = _json(self.create_listing())["data"]["id"]

        web = Client()
        web.force_login(self.other)
        session = web.session
        session["active_company_id"] = str(second.id)
        session.save()
        r = web.post(reverse("listings_web:react", args=[lid]),
                     {"message": "Interested"}, SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        rx = ListingReaction.objects.get(listing_id=lid, from_user=self.other)
        self.assertEqual(rx.from_company_id, second.id)

    def test_api_reaction_without_any_company_is_refused_not_crashed(self):
        companyless = User.objects.create_user(
            email="nocompany@example.com", password="x",
            tenant=self.tenant, role=self.business_role,
        )
        lid = _json(self.create_listing())["data"]["id"]
        body = self.call(api.ListingReactionAPIView.as_view(), "post", companyless, lid,
                         {"message": "Interested"})
        self.assertFalse(body["status"])
        from listings.models import ListingReaction
        self.assertFalse(
            ListingReaction.objects.filter(listing_id=lid, from_user=companyless).exists()
        )

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

    def test_web_edit_keeps_existing_images_when_no_new_upload(self):
        """Editing without re-picking a file must not drop the stored images."""
        from django.test import Client
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        from listings.models import Listing

        web = Client()
        web.force_login(self.owner)
        base = dict(
            listing_type="offer", module_id="products_services", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="Steel Pipes", description="High grade steel pipes in bulk supply.",
            keywords="steel, pipes", visibility_scope="public", action="publish",
        )
        web.post(
            reverse("listings_web:add") + "?type=offer&module=products_services",
            dict(base,
                 product_image=SimpleUploadedFile("p.png", b"\x89PNG\r\n", content_type="image/png"),
                 certification_image=SimpleUploadedFile("c.png", b"\x89PNG\r\n", content_type="image/png")),
            SERVER_NAME="localhost")
        listing = Listing.objects.get(title="Steel Pipes")
        product_name = listing.product_image.name
        cert_name = listing.certification_image.name
        self.assertTrue(product_name and cert_name)

        # the edit form shows the stored image, so it is clear no re-upload is needed
        form = web.get(reverse("listings_web:edit", args=[listing.id]), SERVER_NAME="localhost")
        self.assertContains(form, listing.product_image.url)
        self.assertContains(form, listing.certification_image.url)

        web.post(reverse("listings_web:edit", args=[listing.id]),
                 dict(base, title="Steel Pipes v2"), SERVER_NAME="localhost")
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Steel Pipes v2")
        self.assertEqual(listing.product_image.name, product_name)
        self.assertEqual(listing.certification_image.name, cert_name)

    def test_web_add_keeps_company_selected_on_validation_error(self):
        """A rejected submit must redisplay with the chosen company still selected."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        selected = '<option value="%s" selected>' % self.company.id
        base = dict(
            listing_type="offer", module_id="products_services", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="Steel Pipes", description="High grade steel pipes in bulk supply.",
            keywords="steel", visibility_scope="public", action="publish",
            country="IN", region="Punjab", city="Mohali",
        )
        for label, bad in [
            ("title", {"title": "ab"}),
            ("description", {"description": "short"}),
            ("keywords", {"keywords": ""}),
            ("nace_code", {"nace_code": ""}),
            ("currency", {"price_without_vat": "10", "currency": ""}),
            ("unit", {"unit": "abc"}),
        ]:
            with self.subTest(field=label):
                r = web.post(reverse("listings_web:add") + "?type=offer&module=products_services",
                             dict(base, **bad), SERVER_NAME="localhost")
                self.assertEqual(r.status_code, 200)
                self.assertIn(selected, r.content.decode())

    def test_web_add_keeps_uploaded_image_on_validation_error(self):
        """A rejected submit must keep the picked image, and the retry must save
        it without the user choosing the file a second time."""
        from django.test import Client
        from django.urls import reverse
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile

        web = Client()
        web.force_login(self.owner)
        url = reverse("listings_web:add") + "?type=offer&module=products_services"
        base = dict(
            listing_type="offer", module_id="products_services", category_type="product",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            description="High grade steel pipes in bulk supply.",
            keywords="steel", visibility_scope="public", action="publish",
            country="IN", region="Punjab", city="Mohali",
        )
        # 1st submit: image picked, but the title is too short -> redisplay.
        r = web.post(url, dict(base, title="ab",
                               product_image=SimpleUploadedFile("p.png", b"\x89PNG\r\n",
                                                                content_type="image/png"),
                               certification_image=SimpleUploadedFile("c.png", b"\x89PNG\r\n",
                                                                      content_type="image/png")),
                     SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 200)
        values = r.context["values"]
        stashed = values["product_image_stashed"]
        cert_stashed = values["certification_image_stashed"]
        self.assertTrue(default_storage.exists(stashed))
        # the thumbnail proves to the user that the file is still attached
        self.assertContains(r, default_storage.url(stashed))

        # 2nd submit: still invalid and no file re-picked -> the stash carries over.
        r = web.post(url, dict(base, title="ab", product_image_stashed=stashed,
                               certification_image_stashed=cert_stashed),
                     SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["values"]["product_image_stashed"], stashed)

        # 3rd submit: fixed, no file re-picked -> the stashed images are stored.
        r = web.post(url, dict(base, title="Steel Pipes", product_image_stashed=stashed,
                               certification_image_stashed=cert_stashed),
                     SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        listing = Listing.objects.get(title="Steel Pipes")
        self.assertTrue(bool(listing.product_image))
        self.assertTrue(bool(listing.certification_image))
        self.assertEqual(listing.product_image.read(), b"\x89PNG\r\n")
        # the listing owns its own copy, so the stash entry is released
        self.assertFalse(default_storage.exists(stashed))

    def test_web_add_rejects_forged_stash_reference(self):
        """The stash reference is user input: a crafted path must be ignored."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        r = web.post(
            reverse("listings_web:add") + "?type=offer&module=products_services",
            dict(listing_type="offer", module_id="products_services", category_type="product",
                 owner_company=str(self.company.id), nace_code=str(self.nace.id),
                 title="Steel Pipes Forged", description="High grade steel pipes in bulk supply.",
                 keywords="steel", visibility_scope="public", action="publish",
                 product_image_stashed="listing_tmp/../../manage.py"),
            SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(bool(Listing.objects.get(title="Steel Pipes Forged").product_image))

    def test_unit_must_come_from_the_list_and_match_the_category(self):
        """Free text is out, and a unit only counts for its own category."""
        resp = self.create_listing(category_type="service", unit="Per Hour, roughly")
        self.assertEqual(resp.status_code, 400)

        # a service priced per pallet is a data-entry slip, not a valid offer
        resp = self.create_listing(category_type="service", unit="pallet")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("unit", _json(resp).get("errors", _json(resp)))

        resp = self.create_listing(category_type="product", unit="consultation")
        self.assertEqual(resp.status_code, 400)

        # the matching pairs go through
        for category, unit in (("service", "hour"), ("service", "project"), ("product", "piece")):
            with self.subTest(category=category, unit=unit):
                resp = self.create_listing(category_type=category, unit=unit,
                                           title=f"Offer {category} {unit}")
                self.assertEqual(resp.status_code, 201)
                self.assertEqual(_json(resp)["data"]["unit"], unit)

    def test_web_service_offer_form_lists_service_units(self):
        """The Add Offer form ships both unit sets, so picking Service offers
        Per Hour / Per Project instead of a free-text box."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        r = web.get(reverse("listings_web:add") + "?type=offer&module=products_services",
                    SERVER_NAME="localhost")
        body = r.content.decode()
        self.assertNotIn('<input type="text" name="unit"', body)
        self.assertIn('<select name="unit"', body)
        self.assertIn('data-unit-group="service"', body)
        for label in ("Per Hour", "Per Project", "Per Consultation"):
            self.assertIn(label, body)

    def test_web_keywords_survive_repeated_rejected_submits(self):
        """Keywords come back as the line the user typed. They used to redisplay
        as the parsed list, so each retry re-parsed "['a', 'b']" and buried the
        keywords under another layer of brackets and quotes."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        url = reverse("listings_web:add") + "?type=offer&module=products_services"
        typed = "software development, IT consulting, web development"
        # invalid NACE, everything else fine - exactly the reported flow
        data = dict(
            listing_type="offer", module_id="products_services", category_type="product",
            owner_company=str(self.company.id), nace_code="",
            title="IT Services", description="Custom software and IT consulting services.",
            keywords=typed, visibility_scope="public", action="publish",
        )
        for attempt in range(1, 4):
            with self.subTest(attempt=attempt):
                r = web.post(url, data, SERVER_NAME="localhost")
                self.assertEqual(r.status_code, 200)
                self.assertIn("nace_code", r.context["errors"])
                self.assertEqual(r.context["values"]["keywords"], typed)
                body = r.content.decode()
                self.assertIn('name="keywords" class="form-control" value="%s"' % typed, body)
                for junk in ("[", "]", "&#x27;", "&quot;", "\\"):
                    self.assertNotIn(junk, body.split('name="keywords"')[1].split(">")[0])
                # the next attempt resubmits whatever the field now holds
                data["keywords"] = r.context["values"]["keywords"]

        # once the NACE code is valid the keywords save as typed, not mangled
        data["nace_code"] = str(self.nace.id)
        self.assertEqual(web.post(url, data, SERVER_NAME="localhost").status_code, 302)
        self.assertEqual(
            Listing.objects.get(title="IT Services").keywords,
            ["software development", "IT consulting", "web development"],
        )

    def test_web_service_offer_hides_product_image_field(self):
        """Product Image applies to a Product Offer only, so a Service form must
        not show it — and the redisplay must not bring it back."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        url = reverse("listings_web:add") + "?type=offer&module=products_services"

        # the fresh form defaults to Product, so the field is there
        body = web.get(url, SERVER_NAME="localhost").content.decode()
        self.assertIn('id="product_image_group">', body)

        # a rejected Service submit redraws with it already hidden, so it never
        # flashes into view while the page settles
        body = web.post(url, dict(
            listing_type="offer", module_id="products_services", category_type="service",
            owner_company=str(self.company.id), nace_code=str(self.nace.id),
            title="ab", description="On-site welding and inspection service.",
            keywords="welding", visibility_scope="public", action="publish",
        ), SERVER_NAME="localhost").content.decode()
        self.assertIn('id="product_image_group" hidden>', body)

    def test_web_service_offer_ignores_a_product_image_that_slips_through(self):
        """Hiding is a UI courtesy; a Service offer must store no product image
        even when one is posted anyway."""
        from django.test import Client
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile

        web = Client()
        web.force_login(self.owner)
        r = web.post(
            reverse("listings_web:add") + "?type=offer&module=products_services",
            dict(listing_type="offer", module_id="products_services", category_type="service",
                 owner_company=str(self.company.id), nace_code=str(self.nace.id),
                 title="Welding Service Only", description="On-site welding and inspection service.",
                 keywords="welding", visibility_scope="public", action="publish", unit="hour",
                 product_image=SimpleUploadedFile("p.png", b"\x89PNG\r\n", content_type="image/png")),
            SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(bool(Listing.objects.get(title="Welding Service Only").product_image))

    def test_web_service_offer_rejects_product_unit(self):
        """The page-level swap is convenience; the server is what enforces it."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        r = web.post(
            reverse("listings_web:add") + "?type=offer&module=products_services",
            dict(listing_type="offer", module_id="products_services", category_type="service",
                 owner_company=str(self.company.id), nace_code=str(self.nace.id),
                 title="Welding Service", description="On-site welding and inspection service.",
                 keywords="welding", visibility_scope="public", action="publish",
                 price_without_vat="80", currency="EUR", unit="pallet"),
            SERVER_NAME="localhost")
        self.assertEqual(r.status_code, 200)
        self.assertIn("unit", r.context["errors"])
        self.assertFalse(Listing.objects.filter(title="Welding Service").exists())

    def test_web_add_preselects_acting_company(self):
        """The fresh form opens on the company the session is acting as."""
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.owner)
        r = web.get(reverse("listings_web:add") + "?type=offer&module=products_services",
                    SERVER_NAME="localhost")
        self.assertIn('<option value="%s" selected>' % self.company.id, r.content.decode())

    def test_web_detail_shows_city_region_and_country(self):
        """Detail page renders the full location, not just city + country code."""
        from django.test import Client
        from django.urls import reverse
        from listings.models import Listing

        lid = _json(self.create_listing(country="IN", region="Punjab", city="Mohali"))["data"]["id"]
        web = Client()
        web.force_login(self.owner)
        r = web.get(reverse("listings_web:detail", args=[lid]), SERVER_NAME="localhost")
        self.assertContains(r, "Mohali, Punjab, India")

        # a listing with only a country still renders cleanly (no stray commas)
        Listing.objects.filter(id=lid).update(city="", region="")
        r = web.get(reverse("listings_web:detail", args=[lid]), SERVER_NAME="localhost")
        self.assertContains(r, "India")

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

    # ---- browse filters (NACE / ISIC + country) ----
    def _nace_fixture(self):
        """A small NACE subtree + one listing classified at its leaf."""
        section = NaceCode.objects.create(
            code="A", title="AGRICULTURE, FORESTRY AND FISHING", level=1
        )
        division = NaceCode.objects.create(
            code="A01", title="Crop and animal production", level=2, parent=section
        )
        leaf = NaceCode.objects.create(
            code="A0111", title="Growing of cereals", level=4, parent=division
        )
        lid = _json(self.create_listing(
            title="Wheat Offer", nace_code=str(leaf.id), country="IN",
        ))["data"]["id"]
        return section, division, leaf, lid

    def test_browse_nace_filter_matches_subtree_by_code(self):
        """Filtering by a section returns listings classified anywhere beneath it."""
        from listings.services import nace_filter as _nace_filter

        section, division, leaf, _ = self._nace_fixture()
        for code in (section.code, division.code, leaf.code):
            q, display = _nace_filter(code)
            titles = list(Listing.objects.filter(q).values_list("title", flat=True))
            self.assertIn("Wheat Offer", titles, code)
            self.assertTrue(display.startswith(code + " \u2014 "), display)

    def test_browse_nace_filter_accepts_pasted_display_string(self):
        """The 'CODE — Title' string shown on the detail page must filter too.

        Regression: it was matched as a raw substring against code AND title
        separately, so the combined form matched neither and returned nothing.
        """
        from listings.services import nace_filter as _nace_filter

        section, _, _, _ = self._nace_fixture()
        for pasted in (
            "A \u2014 AGRICULTURE, FORESTRY AND FISHING",   # em dash (copy/paste)
            "A - AGRICULTURE, FORESTRY AND FISHING",        # hyphen (hand-typed)
        ):
            q, _display = _nace_filter(pasted)
            titles = list(Listing.objects.filter(q).values_list("title", flat=True))
            self.assertIn("Wheat Offer", titles, pasted)

    def test_browse_nace_filter_free_text_searches_titles(self):
        """Typing words without picking from the list still searches by title."""
        from listings.services import nace_filter as _nace_filter

        self._nace_fixture()
        q, _ = _nace_filter("cereals")
        self.assertIn(
            "Wheat Offer", list(Listing.objects.filter(q).values_list("title", flat=True))
        )

    def test_browse_nace_filter_code_is_prefix_not_substring(self):
        """Section 'A' must not drag in unrelated codes that contain an 'A'."""
        from listings.services import nace_filter as _nace_filter

        self._nace_fixture()
        unrelated = NaceCode.objects.create(code="C10A", title="Bakery", level=4)
        self.create_listing(title="Bread Offer", nace_code=str(unrelated.id))

        q, _ = _nace_filter("A")
        titles = list(Listing.objects.filter(q).values_list("title", flat=True))
        self.assertIn("Wheat Offer", titles)
        self.assertNotIn("Bread Offer", titles)

    def test_browse_country_filter_accepts_code_or_name(self):
        """The dropdown stores ISO codes, so the English name must resolve too.

        Regression: country was a free-text box matched with icontains, so
        'India' never matched a row stored as 'IN'.
        """
        from listings.services import country_filter as _country_filter

        self._nace_fixture()   # creates the IN-based "Wheat Offer"
        for value in ("IN", "India"):
            titles = list(
                Listing.objects.filter(_country_filter(value)).values_list("title", flat=True)
            )
            self.assertIn("Wheat Offer", titles, value)

    def test_browse_page_applies_nace_and_country_filters(self):
        """End-to-end through the view: matching filters keep the row, others drop it."""
        from django.test import Client
        from django.urls import reverse

        self._nace_fixture()
        web = Client()
        web.force_login(self.owner)
        url = reverse("listings_web:browse")

        # The dropdown submits the ISO code; a hand-edited URL may carry the
        # English name. Both have to return the row.
        for country in ("IN", "India"):
            hit = web.get(
                url, {"nace_isic_code": "A", "country": country}, SERVER_NAME="localhost"
            )
            self.assertEqual(hit.status_code, 200)
            self.assertIn(b"Wheat Offer", hit.content, country)
            # The dropdown re-opens on the country that was filtered.
            self.assertIn(b'value="IN" selected', hit.content, country)
        # The box repaints with the readable label, not the bare code.
        self.assertIn(b"A \xe2\x80\x94 AGRICULTURE, FORESTRY AND FISHING", hit.content)

        # A different section (seeded here as it is in production) excludes it.
        NaceCode.objects.create(code="G", title="WHOLESALE AND RETAIL TRADE", level=1)
        miss = web.get(url, {"nace_isic_code": "G"}, SERVER_NAME="localhost")
        self.assertNotIn(b"Wheat Offer", miss.content)

        # A country the listing isn't in excludes it too.
        miss2 = web.get(url, {"country": "France"}, SERVER_NAME="localhost")
        self.assertNotIn(b"Wheat Offer", miss2.content)

    def test_api_search_shares_the_browse_filters(self):
        """/api/listings/ must agree with the browse page on NACE + country."""
        section, _division, _leaf, _lid = self._nace_fixture()

        for params in ({"country": "India"}, {"country": "IN"},
                       {"nace_isic_code": section.code}):
            req = self.factory.get("/", params)
            force_authenticate(req, user=self.owner)
            body = _json(api.ListingCollectionAPIView.as_view()(req))
            titles = [row["title"] for row in body["data"]]
            self.assertIn("Wheat Offer", titles, params)

        # And still excludes non-matches.
        req = self.factory.get("/", {"country": "France"})
        force_authenticate(req, user=self.owner)
        body = _json(api.ListingCollectionAPIView.as_view()(req))
        self.assertNotIn("Wheat Offer", [row["title"] for row in body["data"]])
