"""
Listings Engine - server-rendered (template) views.

These pages power the Business User + Admin UI with Django templates. They
reuse the SAME validation and rules as the API: `ListingWriteSerializer`
(cookbook Section 6) and the `services` helpers (ownership / visibility /
audit). The DRF API under /api/listings/ remains available for AJAX.
"""

import os
import re
import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Count, Q
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
def _owned_companies(user, selected_id=None):
    """Companies the user may file a listing for.

    ``selected_id`` is the company currently chosen in the form. It is added
    back to the list when it is missing but the user is still allowed to use it
    (e.g. an admin acting across the tenant), so a validation redisplay can
    never silently drop the selection and leave the picker blank.
    """
    if services.is_admin(user):
        qs = Company.objects.filter(tenant=user.tenant)
    else:
        qs = Company.objects.filter(owner_user=user)
    if not selected_id:
        return qs
    companies = list(qs)
    if any(str(c.id) == str(selected_id) for c in companies):
        return companies
    extra = Company.objects.filter(id=selected_id).first()
    if extra is not None and services.company_belongs_to_user(extra, user):
        companies.append(extra)
    return companies


def _default_company_id(request, companies):
    """Company to preselect on a fresh form: the one the session is acting as,
    then the primary company, then the only company the user owns."""
    candidates = [
        getattr(getattr(request, "active_company", None), "id", None),
        getattr(request.user, "primary_company_id", None),
    ]
    ids = {c.id for c in companies}
    for candidate in candidates:
        if candidate in ids:
            return candidate
    return companies[0].id if len(companies) == 1 else None


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


# Images picked before a rejected submit are held here between the failed POST
# and the redisplay: a browser cannot refill a file input, so without a
# server-side copy the user has to pick every image again on each error.
_STASH_DIR = "listing_tmp"
_STASH_FIELDS = ("product_image", "certification_image")
_STASH_BASENAME_RE = re.compile(r"[0-9a-f]{32}(\.[a-z0-9]{1,9})?\Z")
_STASH_MAX_AGE = timedelta(hours=24)


def _prune_stash():
    """Drop stash files older than a day - a submit abandoned on the error page
    leaves its copy behind, and nothing else ever collects them."""
    try:
        _dirs, files = default_storage.listdir(_STASH_DIR)
    except (FileNotFoundError, OSError, NotImplementedError):
        return
    cutoff = timezone.now() - _STASH_MAX_AGE
    for name in files:
        path = f"{_STASH_DIR}/{name}"
        try:
            if default_storage.get_modified_time(path) < cutoff:
                default_storage.delete(path)
        except (OSError, ValueError, NotImplementedError):
            continue


def _stash_upload(uploaded):
    """Copy a just-uploaded image into the stash and return its storage name."""
    ext = os.path.splitext(uploaded.name)[1].lower()[:10]
    if not re.fullmatch(r"\.[a-z0-9]{1,9}", ext or ""):
        ext = ""
    _prune_stash()
    return default_storage.save(f"{_STASH_DIR}/{uuid.uuid4().hex}{ext}", uploaded)


def _stash_name(raw):
    """Validate a stash reference that came back from the form.

    The value round-trips through a hidden field, so it is user input: only our
    own uuid names directly inside the stash directory are accepted, which keeps
    a crafted value from reaching an arbitrary file.
    """
    name = (raw or "").strip()
    prefix = f"{_STASH_DIR}/"
    if not name.startswith(prefix):
        return ""
    basename = name[len(prefix):]
    if not _STASH_BASENAME_RE.fullmatch(basename):
        return ""
    return name if default_storage.exists(name) else ""


def _carry_uploads(request, values):
    """Preserve picked images across a validation redisplay.

    A new upload replaces whatever the previous failed submit stashed; with no
    new upload the earlier stash is carried forward, so the image survives any
    number of error rounds.
    """
    for field in _STASH_FIELDS:
        previous = _stash_name(request.POST.get(f"{field}_stashed"))
        uploaded = request.FILES.get(field)
        if uploaded:
            if previous:
                default_storage.delete(previous)
            values[f"{field}_stashed"] = _stash_upload(uploaded)
        else:
            values[f"{field}_stashed"] = previous
    return values


def _resolve_image(request, field):
    """The image to store: the file picked on this submit, else the one stashed
    by an earlier submit that failed validation."""
    uploaded = request.FILES.get(field)
    if uploaded:
        return _shorten_upload_name(uploaded)
    name = _stash_name(request.POST.get(f"{field}_stashed"))
    if not name:
        return None
    return File(default_storage.open(name), name=os.path.basename(name))


def _discard_stash(request):
    for field in _STASH_FIELDS:
        name = _stash_name(request.POST.get(f"{field}_stashed"))
        if name:
            default_storage.delete(name)


def _apply_images(request, listing):
    """Attach uploaded images. Product image only for a Product Offer."""
    fields, opened = [], []
    if listing.listing_type == Listing.OFFER:
        img = _resolve_image(request, "product_image")
        if img and listing.category_type == Listing.PRODUCT:
            listing.product_image = img
            fields.append("product_image")
            opened.append(img)
        cert = _resolve_image(request, "certification_image")
        if cert:
            listing.certification_image = cert
            fields.append("certification_image")
            opened.append(cert)
    if fields:
        listing.save(update_fields=fields)
    # The listing now owns its own copy, so the stash entry is done - including
    # a product image dropped because the category ended up Service.
    for handle in opened:
        handle.close()
    _discard_stash(request)


def _location_display(listing):
    """Full location line: "City, Region, Country" (country shown by name).

    Any missing part is simply dropped, so a listing with only a country still
    renders cleanly.
    """
    country = listing.country or ""
    parts = [
        listing.city or "",
        listing.region or "",
        COUNTRY_ENGLISH_NAMES.get(country, country),
    ]
    return ", ".join(p for p in parts if p)


def _form_context(user, listing_type, module_id="products_services", values=None, errors=None):
    module = next((m for m in module_registry.MODULE_REGISTRY if m["id"] == module_id), None)
    values = values or {}
    errors = errors or {}
    # The Keywords input is one comma-separated line, but the payload carries the
    # parsed list. Rendering the list writes "['steel', 'pipes']" into the field,
    # and the next submit parses THAT back - so every rejected attempt piled on
    # another layer of brackets and quotes. Join it back into the line here, once,
    # for every caller.
    if isinstance(values.get("keywords"), (list, tuple)):
        values["keywords"] = ", ".join(str(k) for k in values["keywords"])
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

    # A stashed image is shown back as the thumbnail, so the redisplay proves the
    # file is still attached even though the file input itself reads empty.
    for field in _STASH_FIELDS:
        stashed = values.get(f"{field}_stashed")
        values[f"{field}_stashed_url"] = default_storage.url(stashed) if stashed else ""

    return {
        "listing_type": listing_type,
        "is_offer": listing_type == Listing.OFFER,
        "companies": _owned_companies(user, values.get("owner_company")),
        "nace_display": nace_display,
        "category_choices": Listing.CATEGORY_CHOICES,
        "currency_choices": Listing.CURRENCY_CHOICES,
        # Both unit sets go to the page and the category picker swaps between
        # them, so switching Product <-> Service needs no round trip.
        "product_unit_choices": Listing.PRODUCT_UNIT_CHOICES,
        "service_unit_choices": Listing.SERVICE_UNIT_CHOICES,
        "visibility_choices": Listing.VISIBILITY_CHOICES,
        "module_id": module_id,
        "module_name": module["name"] if module else "Products & Services",
        # The registry entry itself, so the sidebar keeps this module's sub-tree
        # open on a validation redraw and on Edit, where there is no ?module=
        # in the query string to read it from.
        "module": module,
        "module_fields": module_fields,
        # Location dropdowns: (code, English name) pairs, sorted by name, plus
        # the country → subdivisions map indexed client-side when a country is
        # picked (mirrors the Company create modal).
        "country_choices": sorted(COUNTRY_ENGLISH_NAMES.items(), key=lambda kv: kv[1]),
        "country_states": COUNTRY_STATES,
        "values": values,
        "errors": errors,
        # Add Offer / Add Demand are separate sidebar entries, so the highlighted
        # one follows the type being created.
        "active_menu": "listings-add-offer" if listing_type == Listing.OFFER else "listings-add-demand",
    }


def _with_reaction_counts(qs):
    """Annotate total + unread reaction counts so My Offers / My Demands can
    surface reactions per listing (they are no longer a sidebar tab)."""
    return qs.annotate(
        reaction_count=Count("reactions", distinct=True),
        new_reaction_count=Count("reactions", filter=Q(reactions__status=ListingReaction.NEW), distinct=True),
    )


def _paginate(request, qs, per_page=10):
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(request.GET.get("page", 1))
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


# ---------------------------------------------------------------------------
# Module Registry - dashboard + landing (cookbook Section 19)
# ---------------------------------------------------------------------------
def _no_module_access_message(user, module):
    """The right refusal for a module the user can't open.

    A Business User on the Free plan is not forbidden, just not subscribed —
    tell them to upgrade instead of showing the generic role refusal. A module
    that simply hasn't shipped yet is nobody's fault at all, so it gets the same
    "coming soon" wording the cards and sidebar rows use rather than a refusal
    that reads like a permissions problem.
    """
    if module and not module_registry.module_is_live(module):
        return _("This module is coming soon.")
    if module and module_registry.module_locked_for_user(user, module):
        return _("Professional modules are available on paid plans only. "
                 "Upgrade your plan to unlock this module.")
    return _("You do not have access to this module.")


@login_required
def modules_dashboard(request):
    """Icon-card dashboard of all enabled professional modules (Section 19.4).

    Plan-locked modules stay on the grid but render as a locked card with an
    upgrade CTA, so a Free user sees what a paid plan unlocks.
    """
    modules = [
        dict(m, locked=module_registry.module_locked_for_user(request.user, m))
        for m in module_registry.visible_modules(request.user)
    ]
    return render(request, "listings/modules_dashboard.html", {
        "modules": modules,
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
        messages.error(request, _no_module_access_message(request.user, module))
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
        messages.error(request, _no_module_access_message(
            user, module_registry.get_module_by_id(module_id)))
        return redirect("modules:dashboard")

    if request.method == "POST":
        listing_type = request.POST.get("listing_type", listing_type)
        module_id = _resolve_module_id(request.POST.get("module_id"))
        if module_id is None or not module_registry.user_can_access_id(user, module_id):
            messages.error(request, _no_module_access_message(
                user, module_registry.get_module_by_id(module_id)))
            return redirect("modules:dashboard")
        payload = _build_payload(request, listing_type, module_id)
        _md, module_errors = _collect_module_data(request, module_id)
        serializer = ListingWriteSerializer(data=payload, context={"request": request})

        if not serializer.is_valid() or module_errors:
            errors = {**serializer.errors, **module_errors}
            messages.error(request, _("Please correct the errors below."))
            return render(request, "listings/listing_form.html",
                          _form_context(user, listing_type, module_id,
                                        _carry_uploads(request, payload), errors))

        company = serializer.validated_data["owner_company"]
        if not services.company_belongs_to_user(company, user):
            messages.error(request, _("You can only create listings for a company you own."))
            return render(request, "listings/listing_form.html",
                          _form_context(user, listing_type, module_id,
                                        _carry_uploads(request, payload),
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

    # Fresh form: preselect the company the user is acting as, so the picker
    # starts filled instead of on the "Select company" placeholder.
    values = {"owner_company": _default_company_id(request, _owned_companies(user))}
    return render(request, "listings/listing_form.html",
                  _form_context(user, listing_type, module_id, values))


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
        messages.error(request, _no_module_access_message(
            user, module_registry.get_module_by_id(listing.module_id)))
        return redirect("modules:dashboard")

    if request.method == "POST":
        payload = _build_payload(request, listing.listing_type, listing.module_id)
        _md, module_errors = _collect_module_data(request, listing.module_id)
        serializer = ListingWriteSerializer(listing, data=payload, partial=True, context={"request": request})
        if not serializer.is_valid() or module_errors:
            errors = {**serializer.errors, **module_errors}
            messages.error(request, _("Please correct the errors below."))
            ctx = _form_context(user, listing.listing_type, listing.module_id,
                                _carry_uploads(request, payload), errors)
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
def _own_listings_module(request):
    """Resolve the optional `?module=` scope for the "my listings" screens.

    The sidebar now nests these screens under a professional module, so each
    link carries the module it belongs to. Returns the module dict, or None
    when no (or an unknown) module was given — in which case the screen keeps
    its original, unscoped behaviour.

    Unlike `browse_listings`, an inaccessible module is *ignored* rather than
    refused: these screens only ever show the caller's OWN listings, so there
    is nothing to leak, and a Business User who drops to the Free plan must
    still be able to manage what they already published.
    """
    raw = request.GET.get("module")
    if not raw:
        return None
    module_id = _resolve_module_id(raw, default=None)
    return module_registry.get_module_by_id(module_id) if module_id else None


def _scope_own_listings(qs, module):
    return qs.filter(module_id=module["id"]) if module else qs


@login_required
def my_listings(request):
    """Combined My Listings - offers + demands together (cookbook Section 19.5).

    Optional ?type=offer|demand narrows the same screen without leaving it,
    and ?module=<slug> narrows it to one professional module.
    """
    module = _own_listings_module(request)
    qs = _with_reaction_counts(
        _scope_own_listings(
            Listing.objects.filter(owner_user=request.user), module
        ).select_related("owner_company").order_by("-created_at")
    )
    current_type = request.GET.get("type", "")
    if current_type in (Listing.OFFER, Listing.DEMAND):
        qs = qs.filter(listing_type=current_type)
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "combined": True, "current_type": current_type,
        "title": _("My Listings"), "active_menu": "listings-my-listings",
        "module": module,
    })


@login_required
def my_offers(request):
    module = _own_listings_module(request)
    qs = _with_reaction_counts(
        _scope_own_listings(
            Listing.objects.filter(owner_user=request.user, listing_type=Listing.OFFER),
            module,
        ).select_related("owner_company")
    )
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "listing_type": Listing.OFFER, "title": _("My Offers"),
        "active_menu": "listings-my-offers",
        "module": module,
    })


@login_required
def my_demands(request):
    module = _own_listings_module(request)
    qs = _with_reaction_counts(
        _scope_own_listings(
            Listing.objects.filter(owner_user=request.user, listing_type=Listing.DEMAND),
            module,
        ).select_related("owner_company")
    )
    return render(request, "listings/my_listings.html", {
        "page_obj": _paginate(request, qs), "listing_type": Listing.DEMAND, "title": _("My Demands"),
        "active_menu": "listings-my-demands",
        "module": module,
    })


@login_required
def my_reactions(request):
    qs = (ListingReaction.objects.filter(to_user=request.user)
          .select_related("listing", "from_user", "from_company"))
    return render(request, "listings/my_reactions.html", {
        "page_obj": _paginate(request, qs), "active_menu": "listings-my-offers",
        "status_choices": ListingReaction.STATUS_CHOICES,
    })


@login_required
def listing_reactions(request, listing_id):
    """Reactions received on ONE listing.

    Reactions are no longer a sidebar tab: the owner reaches them from the
    My Offers / My Demands row for the listing, or from the notification the
    reaction itself raised.
    """
    listing = get_object_or_404(Listing.objects.select_related("owner_company"), id=listing_id)
    if not services.is_listing_owner(listing, request.user) and not services.is_admin(request.user):
        messages.error(request, _("Permission denied."))
        return redirect("listings_web:browse")

    qs = (ListingReaction.objects.filter(listing=listing)
          .select_related("from_user", "from_company").order_by("-created_at"))
    back = "listings-my-offers" if listing.listing_type == Listing.OFFER else "listings-my-demands"
    return render(request, "listings/listing_reactions.html", {
        "listing": listing, "page_obj": _paginate(request, qs),
        "status_choices": ListingReaction.STATUS_CHOICES, "active_menu": back,
    })


@login_required
def reaction_set_status(request):
    """Owner advances a received reaction through new→read→replied→closed."""
    fallback = redirect("listings_web:my-offers")
    if request.method != "POST":
        return fallback
    reaction = get_object_or_404(ListingReaction, id=request.POST.get("reaction_id"))
    back = redirect("listings_web:listing-reactions", listing_id=reaction.listing_id)
    if reaction.to_user_id != request.user.id:
        messages.error(request, _("Permission denied."))
        return fallback
    new_status = request.POST.get("status")
    if new_status not in dict(ListingReaction.STATUS_CHOICES):
        messages.error(request, _("Invalid status."))
    else:
        reaction.status = new_status
        reaction.save(update_fields=["status", "updated_at"])
        messages.success(request, _("Reaction status updated."))
    return back


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
    # Module scope (Section 19.4): arriving from a professional module's landing
    # page keeps you inside that module. Without this the module tiles dropped
    # you into the unfiltered list, so Investments could report 0 listings and
    # then show every Products & Services offer on the platform.
    module = None
    if f.get("module"):
        module_id = _resolve_module_id(f["module"], default=None)
        # Same access rule as the module landing page (Section 19.6) — a module
        # you can't open isn't one you can browse by URL either.
        if module_id and not module_registry.user_can_access_id(user, module_id):
            messages.error(request, _no_module_access_message(
                user, module_registry.get_module_by_id(module_id)))
            return redirect("modules:dashboard")
        if module_id:
            module = module_registry.get_module_by_id(module_id)
            qs = qs.filter(module_id=module_id)
        # An unknown module is ignored rather than 404'd: the rest of the filter
        # bar still works, and the banner below simply doesn't render.
    if f.get("listing_type") in (Listing.OFFER, Listing.DEMAND):
        qs = qs.filter(listing_type=f["listing_type"])
    if f.get("category_type") in (Listing.PRODUCT, Listing.SERVICE):
        qs = qs.filter(category_type=f["category_type"])
    nace_display = ""
    if f.get("nace_isic_code"):
        nace_q, nace_display = services.nace_filter(f["nace_isic_code"])
        qs = qs.filter(nace_q)
    if f.get("country"):
        qs = qs.filter(services.country_filter(f["country"]))
    if f.get("keyword"):
        kw = f["keyword"]
        qs = qs.filter(
            Q(title__icontains=kw) | Q(description__icontains=kw) | Q(keywords__icontains=kw)
        )

    ctx = {
        "page_obj": _paginate(request, qs),
        "filters": f,
        "listing_type_choices": Listing.LISTING_TYPE_CHOICES,
        "category_choices": Listing.CATEGORY_CHOICES,
        "country_choices": sorted(COUNTRY_ENGLISH_NAMES.items(), key=lambda kv: kv[1]),
        # Normalised to an ISO code so the dropdown re-opens on the right entry
        # even when the URL carries the English name.
        "country_selected": services.country_code(f.get("country", "")),
        "nace_display": nace_display,
        "active_menu": "listings-browse",
        # Drives the "you are inside <module>" banner and keeps the module on
        # the filter-bar / Add-listing links so it survives a re-filter.
        "module": module,
    }
    # The filter bar fetches ?partial=1 and swaps just the results block, so the
    # page never reloads. Without JS the same URL renders the full page.
    if f.get("partial") == "1":
        return render(request, "listings/_browse_results.html", ctx)
    return render(request, "listings/browse.html", ctx)


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
        "location_display": _location_display(listing),
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
    from_company = services.acting_company(user, request)

    if listing.status != Listing.ACTIVE:
        messages.error(request, _("Reaction is allowed only for active listings."))
    elif services.is_listing_owner(listing, user):
        messages.error(request, _("You cannot react to your own listing."))
    elif not services.can_view_scope(user, listing.visibility_scope):
        messages.error(request, _("Permission denied."))
    elif from_company is None:
        # A reaction is company-to-company (from_company is NOT NULL), so a
        # user with no company at all can't send one. Say so instead of
        # crashing on the insert.
        messages.error(
            request,
            _("Add a company to your account before sending an expression of interest."),
        )
    else:
        default_msg = _("I am interested in this listing and would like to start communication through FONTESIN.")
        message = (request.POST.get("message") or "").strip() or default_msg
        reaction, created = ListingReaction.objects.get_or_create(
            listing=listing, from_user=user,
            defaults=dict(
                from_company=from_company,
                to_user=listing.owner_user,
                to_company=listing.owner_company, message=message, status=ListingReaction.NEW,
            ),
        )
        if created:
            from django.urls import reverse
            from accounts.utils.notifications import notify
            from accounts.utils.i18n_messages import Msg
            # Link straight to the listing's reactions page so the owner can
            # open and answer it from the notification tab.
            notify(recipient=listing.owner_user, sender=user,
                   title=Msg("New reaction to your listing"),
                   body=Msg("%(title)s received a new reaction.", title=listing.title),
                   link_url=reverse("listings_web:listing-reactions", args=[listing.id]),
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
    # ?module=<slug> narrows the grid to one professional module, so the sidebar
    # can hang an "All Listings" entry under each module instead of offering a
    # single undifferentiated list. Omitted (or unknown) = every module, which
    # is what this screen has always shown.
    module = None
    if f.get("module"):
        module_id = _resolve_module_id(f["module"], default=None)
        if module_id:
            module = module_registry.get_module_by_id(module_id)
            qs = qs.filter(module_id=module_id)
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
        "module": module,
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
    from accounts.utils.i18n_messages import Msg
    notify(recipient=listing.owner_user, sender=user,
           title=Msg("Your listing was suspended"),
           body=Msg("%(title)s was suspended. Reason: %(reason)s",
                    title=listing.title, reason=reason),
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
