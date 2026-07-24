"""
Listings Engine - server-rendered (template) views.

These pages power the Business User + Admin UI with Django templates. They
reuse the SAME validation and rules as the API: `ListingWriteSerializer`
(cookbook Section 6) and the `services` helpers (ownership / visibility /
audit). The DRF API under /api/listings/ remains available for AJAX.
"""

import os
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.constants import COUNTRY_ENGLISH_NAMES, COUNTRY_STATES
from accounts.models import Company, NaceCode
from listings.models import Listing, ListingReaction
from listings.serializers import ListingWriteSerializer
from listings import services
from listings import module_registry


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _owned_companies(user):
    if services.is_admin(user):
        return Company.objects.filter(tenant=user.tenant)
    return Company.objects.filter(owner_user=user)


def _parse_keywords(raw):
    if not raw:
        return []
    parts = [p.strip() for chunk in raw.splitlines() for p in chunk.split(",")]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _resolve_module_id(raw, default="products_services"):
    """Accept a module id or slug and return a valid module id.

    Empty input falls back to the default module; an unknown *non-empty* value
    returns None so the caller can reject it instead of silently coercing it to
    Products & Services (cookbook Section 19.6 - module access must be enforced).
    """
    if not raw:
        return default
    for m in module_registry.MODULE_REGISTRY:
        if raw in (m["id"], m["slug"]):
            return m["id"]
    return None


def _collect_module_data(request, module_id):
    """Read the module-specific fields (Section 19.11) into a dict + errors."""
    data, errors = {}, {}
    for field in module_registry.module_fields(module_id):
        raw = request.POST.get(f"ms_{field['key']}", "")
        if field["type"] == "boolean":
            value = bool(raw)
        else:
            value = (raw or "").strip()
        if field.get("required") and not value:
            errors[f"ms_{field['key']}"] = _("%(label)s is required.") % {"label": field["label"]}
        if value != "" and value is not False:
            data[field["key"]] = value
    return data, errors


def _build_payload(request, listing_type, module_id):
    """Turn the posted form into a serializer payload."""
    post = request.POST
    price = post.get("price_without_vat", "").strip()
    module_data, _module_errors = _collect_module_data(request, module_id)
    payload = {
        "listing_type": listing_type,
        "category_type": post.get("category_type") or Listing.PRODUCT,
        "owner_company": post.get("owner_company") or None,
        "nace_code": post.get("nace_code") or None,
        "title": post.get("title", "").strip(),
        "description": post.get("description", "").strip(),
        "keywords": _parse_keywords(post.get("keywords")),
        "visibility_scope": post.get("visibility_scope") or Listing.PUBLIC,
        "module_id": module_id,
        "module_specific_data": module_data,
        "country": post.get("country", "").strip(),
        "region": post.get("region", "").strip(),
        "city": post.get("city", "").strip(),
    }
    # Offer-only commercial fields
    if listing_type == Listing.OFFER:
        payload["price_without_vat"] = price or None
        payload["currency"] = post.get("currency") or None
        payload["minimum_quantity_or_scope"] = post.get("minimum_quantity_or_scope", "").strip()
        payload["unit"] = post.get("unit", "").strip()
        payload["video_url"] = post.get("video_url", "").strip()
        payload["certification_text"] = post.get("certification_text", "").strip()
    return payload


def _shorten_upload_name(uploaded):
    """Rename an uploaded file to a short, unique name (preserving extension).

    Original names (e.g. AI-generated image filenames) can exceed the
    FileField ``max_length`` of 100 and make storage raise
    ``SuspiciousFileOperation``. A uuid-based name sidesteps that entirely.
    """
    ext = os.path.splitext(uploaded.name)[1].lower()[:10]
    uploaded.name = f"{uuid.uuid4().hex}{ext}"
    return uploaded


def _apply_images(request, listing):
    """Attach uploaded images. Product image only for a Product Offer."""
    fields = []
    if listing.listing_type == Listing.OFFER:
        img = request.FILES.get("product_image")
        if img and listing.category_type == Listing.PRODUCT:
            listing.product_image = _shorten_upload_name(img)
            fields.append("product_image")
        cert = request.FILES.get("certification_image")
        if cert:
            listing.certification_image = _shorten_upload_name(cert)
            fields.append("certification_image")
    if fields:
        listing.save(update_fields=fields)


def _form_context(user, listing_type, module_id="products_services", values=None, errors=None):
    module = next((m for m in module_registry.MODULE_REGISTRY if m["id"] == module_id), None)
    values = values or {}
    errors = errors or {}
    # Enrich each module-specific field with its posted name / current value /
    # error so the template needs no dynamic dict lookup.
    module_fields = []
    for f in module_registry.module_fields(module_id):
        name = f"ms_{f['key']}"
        module_fields.append({
            **f,
            "name": name,
            "value": values.get(name, ""),
            "error": errors.get(name, ""),
        })
    # Resolve the currently-selected NACE code to a display string for the
    # searchable picker (covers both edit prefill and validation-error redraws).
    nace_display = ""
    nace_id = values.get("nace_code")
    if nace_id:
        obj = NaceCode.objects.filter(id=nace_id).first()
        if obj:
            nace_display = f"{obj.code} — {obj.title}"

    return {
        "listing_type": listing_type,
        "is_offer": listing_type == Listing.OFFER,
        "companies": _owned_companies(user),
        "nace_display": nace_display,
        "category_choices": Listing.CATEGORY_CHOICES,
        "currency_choices": Listing.CURRENCY_CHOICES,
        "visibility_choices": Listing.VISIBILITY_CHOICES,
        "module_id": module_id,
        "module_name": module["name"] if module else "Products & Services",
        "module_fields": module_fields,
        # Location dropdowns: (code, English name) pairs, sorted by name, plus
        # the country → subdivisions map indexed client-side when a country is
        # picked (mirrors the Company create modal).
        "country_choices": sorted(COUNTRY_ENGLISH_NAMES.items(), key=lambda kv: kv[1]),
        "country_states": COUNTRY_STATES,
        "values": values,
        "errors": errors,
        "active_menu": "listings-add",
    }


def _paginate(request, qs, per_page=10):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(request.GET.get("page", 1))
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


# ---------------------------------------------------------------------------
# Module Registry - dashboard + landing (cookbook Section 19)
# ---------------------------------------------------------------------------
@login_required
def modules_dashboard(request):
    """Icon-card dashboard of all enabled professional modules (Section 19.4)."""
    return render(request, "listings/modules_dashboard.html", {
        "modules": module_registry.visible_modules(request.user),
        "active_menu": "modules",
    })


@login_required
def module_landing(request, slug):
    """Per-module landing page (Section 19.4). Live modules link into the
    shared listings screens filtered by module_id; others show coming-soon."""
    module = module_registry.get_module(slug)
    if not module or not module["enabled"]:
        messages.error(request, _("Module not found."))
        return redirect("modules:dashboard")
    if not module_registry.user_can_access(request.user, module):
        messages.error(request, _("You do not have access to this module."))
        return redirect("modules:dashboard")

    stats = {}
    if module["status"] == "live":
        base = Listing.objects.filter(module_id=module["id"], status=Listing.ACTIVE)
        if not services.is_admin(request.user):
            base = base.filter(tenant=request.user.tenant)
        stats = {
            "offers": base.filter(listing_type=Listing.OFFER).count(),
            "demands": base.filter(listing_type=Listing.DEMAND).count(),
        }

    return render(request, "listings/module_landing.html", {
        "module": module,
        "stats": stats,
        "is_business_user": services.is_business_user(request.user),
        "active_menu": "modules",
    })


# ---------------------------------------------------------------------------
# Business User - create / edit
# ---------------------------------------------------------------------------
@login_required
def add_listing(request):
    user = request.user
    if not (services.is_business_user(user) or services.is_admin(user)):
        messages.error(request, _("Only Business Users can create listings."))
        return redirect("listings_web:browse")

    listing_type = request.GET.get("type", Listing.OFFER)
    if listing_type not in (Listing.OFFER, Listing.DEMAND):
        listing_type = Listing.OFFER
    module_id = _resolve_module_id(request.GET.get("module"))
    if module_id is None or not module_registry.user_can_access_id(user, module_id):
        messages.error(request, _("You do not have access to this module."))
        return redirect("modules:dashboard")

    if request.method == "POST":
        listing_type = request.POST.get("listing_type", listing_type)
        module_id = _resolve_module_id(request.POST.get("module_id"))
        if module_id is None or not module_registry.user_can_access_id(user, module_id):
            messages.error(request, _("You do not have access to this module."))
            return redirect("modules:dashboard")
        payload = _build_payload(request, listing_type, module_id)
        _md, module_errors = _collect_module_data(request, module_id)
        serializer = ListingWriteSerializer(data=payload, context={"request": request})

        if not serializer.is_valid() or module_errors:
            errors = {**serializer.errors, **module_errors}
            messages.error(request, _("Please correct the errors below."))
            return render(request, "listings/listing_form.html",
                          _form_context(user, listing_type, module_id, payload, errors))

        company = serializer.validated_data["owner_company"]
        if not services.company_belongs_to_user(company, user):
            messages.error(request, _("You can only create listings for a company you own."))
            return render(request, "listings/listing_form.html",
                          _form_context(user, listing_type, module_id, payload,
                                        {"owner_company": [_("Not your company.")]}))

        target_status = Listing.ACTIVE if request.POST.get("action") == "publish" else Listing.DRAFT
        published_at = timezone.now() if target_status == Listing.ACTIVE else None
        listing = serializer.save(
            owner_user=user, tenant=user.tenant,
            status=target_status, published_at=published_at,
        )
        _apply_images(request, listing)
        services.create_audit_log(listing, "listing_created", None, None, user)
        messages.success(request, _("Listing saved."))
        return redirect("listings_web:my-offers" if listing_type == Listing.OFFER else "listings_web:my-demands")

    return render(request, "listings/listing_form.html", _form_context(user, listing_type, module_id))


@login_required
def edit_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    user = request.user

    if not services.is_listing_owner(listing, user) and not services.is_admin(user):
        messages.error(request, _("You cannot edit another user's listing."))
        return redirect("listings_web:browse")

    if listing.status == Listing.SUSPENDED and not services.is_admin(user):
        messages.error(request, _("Suspended listing cannot be edited."))
        return redirect("listings_web:detail", listing_id=listing.id)

    if not services.is_admin(user) and not module_registry.user_can_access_id(user, listing.module_id):
        messages.error(request, _("You do not have access to this module."))
        return redirect("modules:dashboard")

    if request.method == "POST":
        payload = _build_payload(request, listing.listing_type, listing.module_id)
        _md, module_errors = _collect_module_data(request, listing.module_id)
        serializer = ListingWriteSerializer(listing, data=payload, partial=True, context={"request": request})
        if not serializer.is_valid() or module_errors:
            errors = {**serializer.errors, **module_errors}
            messages.error(request, _("Please correct the errors below."))
            ctx = _form_context(user, listing.listing_type, listing.module_id, payload, errors)
            ctx["listing"] = listing
            return render(request, "listings/listing_form.html", ctx)

        listing = serializer.save()
        _apply_images(request, listing)
        services.create_audit_log(listing, "listing_updated", None, None, user)
        messages.success(request, _("Listing updated."))
        return redirect("listings_web:detail", listing_id=listing.id)

    values = {
        "category_type": listing.category_type, "owner_company": listing.owner_company_id,
        "nace_code": listing.nace_code_id, "title": listing.title, "description": listing.description,
        "keywords": ", ".join(listing.keywords or []), "visibility_scope": listing.visibility_scope,
        "price_without_vat": listing.price_without_vat, "currency": listing.currency,
        "minimum_quantity_or_scope": listing.minimum_quantity_or_scope, "unit": listing.unit,
        "video_url": listing.video_url, "certification_text": listing.certification_text,
        "country": listing.country, "region": listing.region, "city": listing.city,
        "module_id": listing.module_id,
    }
    # Prefill module-specific fields (Section 19.11) as ms_<key>.
    for key, val in (listing.module_specific_data or {}).items():
        values[f"ms_{key}"] = val
    ctx = _form_context(user, listing.listing_type, listing.module_id, values)
    ctx["listing"] = listing
    return render(request, "listings/listing_form.html", ctx)


# ---------------------------------------------------------------------------
# Business User - my listings + reactions
# ---------------------------------------------------------------------------
@login_required
def my_listings(request):
    """Combined My Listings - offers + demands together (cookbook Section 19.5).

    Optional ?type=offer|demand narrows the same screen without leaving it.
    """
    qs = (Listing.objects.filter(owner_user=request.user)
          .select_related("owner_company").order_by("-created_at"))
    current_type = request.GET.get("type", "")
    if current_type in (Listing.OFFER, Listing.DEMAND):
        qs = qs.filter(listing_type=current_type)
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "combined": True, "current_type": current_type,
        "title": _("My Listings"), "active_menu": "listings-my-listings",
    })


@login_required
def my_offers(request):
    qs = Listing.objects.filter(owner_user=request.user, listing_type=Listing.OFFER).select_related("owner_company")
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "listing_type": Listing.OFFER, "title": _("My Offers"),
        "active_menu": "listings-my-offers",
    })


@login_required
def my_demands(request):
    qs = Listing.objects.filter(owner_user=request.user, listing_type=Listing.DEMAND).select_related("owner_company")
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "listing_type": Listing.DEMAND, "title": _("My Demands"),
        "active_menu": "listings-my-demands",
    })


@login_required
def my_reactions(request):
    qs = (ListingReaction.objects.filter(to_user=request.user)
          .select_related("listing", "from_user", "from_company"))
    return render(request, "listings/my_reactions.html", {
        "page_obj": _paginate(request, qs), "active_menu": "listings-reactions",
        "status_choices": ListingReaction.STATUS_CHOICES,
    })


@login_required
def reaction_set_status(request):
    """Owner advances a received reaction through new→read→replied→closed."""
    if request.method != "POST":
        return redirect("listings_web:my-reactions")
    reaction = get_object_or_404(ListingReaction, id=request.POST.get("reaction_id"))
    if reaction.to_user_id != request.user.id:
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:my-reactions")
    new_status = request.POST.get("status")
    if new_status not in dict(ListingReaction.STATUS_CHOICES):
        messages.error(request, _("Invalid status."))
    else:
        reaction.status = new_status
        reaction.save(update_fields=["status", "updated_at"])
        messages.success(request, _("Reaction status updated."))
    return redirect("listings_web:my-reactions")


@login_required
def set_status(request, listing_id, target):
    """Owner activate/deactivate."""
    listing = get_object_or_404(Listing, id=listing_id)
    user = request.user
    if not services.is_listing_owner(listing, user) and not services.is_admin(user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")
    if listing.status == Listing.SUSPENDED and not services.is_admin(user):
        messages.error(request, _("Suspended listing cannot be changed."))
        return redirect("listings_web:detail", listing_id=listing.id)

    if target == "activate":
        listing.status = Listing.ACTIVE
        if listing.published_at is None:
            listing.published_at = timezone.now()
        action = "listing_activated"
    else:
        listing.status = Listing.INACTIVE
        action = "listing_deactivated"
    listing.save(update_fields=["status", "published_at", "updated_at"])
    services.create_audit_log(listing, action, None, None, user)
    messages.success(request, _("Status updated."))
    back = "my-offers" if listing.listing_type == Listing.OFFER else "my-demands"
    return redirect(f"listings_web:{back}")


# ---------------------------------------------------------------------------
# Search + detail + reaction
# ---------------------------------------------------------------------------
@login_required
def browse_listings(request):
    user = request.user
    qs = Listing.objects.filter(
        status=Listing.ACTIVE,
        visibility_scope__in=services.get_user_visible_scopes(user),
    ).select_related("owner_company", "nace_code")
    if not services.is_admin(user):
        qs = qs.filter(tenant=user.tenant)

    f = request.GET
    if f.get("listing_type") in (Listing.OFFER, Listing.DEMAND):
        qs = qs.filter(listing_type=f["listing_type"])
    if f.get("category_type") in (Listing.PRODUCT, Listing.SERVICE):
        qs = qs.filter(category_type=f["category_type"])
    if f.get("nace_isic_code"):
        nace = f["nace_isic_code"]
        qs = qs.filter(Q(nace_code__code__icontains=nace) | Q(nace_code__title__icontains=nace))
    if f.get("country"):
        qs = qs.filter(country__icontains=f["country"])
    if f.get("keyword"):
        kw = f["keyword"]
        qs = qs.filter(
            Q(title__icontains=kw) | Q(description__icontains=kw) | Q(keywords__icontains=kw)
        )

    return render(request, "listings/browse.html", {
        "page_obj": _paginate(request, qs),
        "filters": f,
        "listing_type_choices": Listing.LISTING_TYPE_CHOICES,
        "category_choices": Listing.CATEGORY_CHOICES,
        "active_menu": "listings-browse",
    })


@login_required
def listing_detail(request, listing_id):
    listing = get_object_or_404(
        Listing.objects.select_related("owner_company", "owner_user", "nace_code"), id=listing_id
    )
    user = request.user
    is_owner = services.is_listing_owner(listing, user)
    can_view = is_owner or services.is_admin(user) or (
        listing.status == Listing.ACTIVE and services.can_view_scope(user, listing.visibility_scope)
    )
    if not can_view:
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")

    already_reacted = ListingReaction.objects.filter(listing=listing, from_user=user).exists()
    return render(request, "listings/detail.html", {
        "listing": listing, "is_owner": is_owner, "is_admin": services.is_admin(user),
        "can_react": (not is_owner) and listing.status == Listing.ACTIVE and not already_reacted,
        "already_reacted": already_reacted,
        "active_menu": "listings-browse",
    })


@login_required
def react_listing(request, listing_id):
    if request.method != "POST":
        return redirect("listings_web:detail", listing_id=listing_id)
    listing = get_object_or_404(Listing, id=listing_id)
    user = request.user

    if listing.status != Listing.ACTIVE:
        messages.error(request, _("Reaction is allowed only for active listings."))
    elif services.is_listing_owner(listing, user):
        messages.error(request, _("You cannot react to your own listing."))
    elif not services.can_view_scope(user, listing.visibility_scope):
        messages.error(request, _("Permission denied."))
    else:
        default_msg = _("I am interested in this listing and would like to start communication through FONTESIN.")
        message = (request.POST.get("message") or "").strip() or default_msg
        reaction, created = ListingReaction.objects.get_or_create(
            listing=listing, from_user=user,
            defaults=dict(
                from_company=user.primary_company, to_user=listing.owner_user,
                to_company=listing.owner_company, message=message, status=ListingReaction.NEW,
            ),
        )
        if created:
            from accounts.utils.notifications import notify
            notify(recipient=listing.owner_user, sender=user,
                   title=_("New reaction to your listing"),
                   body=_("%(title)s received a new reaction.") % {"title": listing.title},
                   related_company=listing.owner_company)
            messages.success(request, _("Your interest was sent."))
        else:
            messages.info(request, _("You have already reacted to this listing."))
    return redirect("listings_web:detail", listing_id=listing.id)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@login_required
def admin_listings(request):
    user = request.user
    if not services.is_admin(user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")

    qs = Listing.objects.select_related("owner_company", "owner_user").order_by("-created_at")
    f = request.GET
    if f.get("status") in dict(Listing.STATUS_CHOICES):
        qs = qs.filter(status=f["status"])
    if f.get("listing_type") in (Listing.OFFER, Listing.DEMAND):
        qs = qs.filter(listing_type=f["listing_type"])
    if f.get("keyword"):
        qs = qs.filter(Q(title__icontains=f["keyword"]) | Q(description__icontains=f["keyword"]))

    return render(request, "listings/admin_listings.html", {
        "page_obj": _paginate(request, qs, 20),
        "filters": f,
        "status_choices": Listing.STATUS_CHOICES,
        "listing_type_choices": Listing.LISTING_TYPE_CHOICES,
        "active_menu": "listings-admin",
    })


@login_required
def audit_history(request, listing_id):
    """Audit history for a listing (cookbook Step 7.35). Owner or admin."""
    listing = get_object_or_404(Listing.objects.select_related("owner_company"), id=listing_id)
    user = request.user
    if not services.is_listing_owner(listing, user) and not services.is_admin(user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")
    return render(request, "listings/audit_history.html", {
        "listing": listing,
        "page_obj": _paginate(request, listing.audit_logs.select_related("changed_by"), 25),
        "active_menu": "listings-admin" if services.is_admin(user) else "",
    })


@login_required
def admin_suspend(request, listing_id):
    user = request.user
    if not services.is_admin(user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")
    listing = get_object_or_404(Listing, id=listing_id)
    reason = (request.POST.get("reason") or "").strip()
    if len(reason) < 5:
        messages.error(request, _("Suspension reason is required (min 5 characters)."))
        return redirect("listings_web:admin")

    listing.status = Listing.SUSPENDED
    listing.suspension_reason = reason
    listing.suspended_at = timezone.now()
    listing.save(update_fields=["status", "suspension_reason", "suspended_at", "updated_at"])
    services.create_audit_log(listing, "listing_suspended", None, None, user)
    from accounts.utils.notifications import notify
    notify(recipient=listing.owner_user, sender=user,
           title=_("Your listing was suspended"),
           body=_("%(title)s was suspended. Reason: %(reason)s") % {"title": listing.title, "reason": reason},
           related_company=listing.owner_company)
    messages.success(request, _("Listing suspended."))
    return redirect("listings_web:admin")


@login_required
def admin_reactivate(request, listing_id):
    user = request.user
    if not services.is_admin(user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")
    listing = get_object_or_404(Listing, id=listing_id)
    listing.status = Listing.ACTIVE
    listing.suspension_reason = ""
    listing.suspended_at = None
    if listing.published_at is None:
        listing.published_at = timezone.now()
    listing.save(update_fields=["status", "suspension_reason", "suspended_at", "published_at", "updated_at"])
    services.create_audit_log(listing, "listing_reactivated", None, None, user)
    messages.success(request, _("Listing reactivated."))
    return redirect("listings_web:admin")
