import json
import logging

from accounts.models import UserRole, Company, CompanyConnection, CompanyJoinRequest, Notification, User

logger = logging.getLogger("technical")


def admin_context(request):
    is_tenant_admin = False
    sidebar_company_count = 0
    plan_features_json = "{}"
    is_free_plan = False
    is_basic_plan = False
    is_pro_plan = False
    is_global_plan = False
    is_basic_business_user = False
    is_pro_business_user = False
    is_global_business_user = False
    is_paid_business_user = False
    sidebar_modules = []
    pending_partnership_count = 0
    pending_join_request_count = 0
    owns_any_company = False
    show_partnership_upgrade_banner = False
    pending_certification_count = 0
    new_commission_count = 0
    pending_coordinator_request_count = 0
    pending_application_count = 0
    pending_consultant_request_count = 0
    pending_franchise_application_count = 0
    pending_child_franchise_request_count = 0
    has_pending_coordinator_request = False
    bu_certification_status = ""
    bu_certification_consultant_name = ""
    bu_certification_company_name = ""
    unread_message_count = 0
    recent_notifications = []
    unread_contact_message_count = 0
    pending_invoice_count = 0
    has_pending_paid_upgrade = False
    active_company = None
    active_company_name = ""
    active_company_certified = False
    active_plan_needs_renewal = False
    active_plan_code = ""
    owned_company_count = 0
    can_switch_company = False
    is_micro_owner = False
    owns_micro = False
    is_active_franchise_owner = False
    can_add_subfranchise = False

    if request.user.is_authenticated:
        # Resolve the acting company ONCE. Four helpers below each resolved it
        # independently (plan lookup, notification scoping, pending upgrade, the
        # switcher block), and resolve_active_company costs 1-2 queries whenever
        # ActiveCompanyMiddleware hasn't cached it on the user — i.e. every path
        # the middleware skips. Kept in its own local because the exported
        # `active_company` stays role-gated below.
        from billing.utils import resolve_active_company
        acting_company = (
            getattr(request, "active_company", None)
            or resolve_active_company(request.user)
        )

        if not request.user.is_superuser:
            try:
                user_role = UserRole.objects.select_related("role").get(user=request.user)
                is_tenant_admin = user_role.role.name == "tenant_admin"
            except UserRole.DoesNotExist:
                pass

        # Company count for sidebar badge
        if request.user.is_superuser:
            sidebar_company_count = Company.objects.count()
        elif hasattr(request.user, 'tenant') and request.user.tenant:
            sidebar_company_count = Company.objects.filter(tenant=request.user.tenant).count()

        # Professional modules for the consolidated sidebar tree. The registry
        # is the single source of truth for which modules exist, who may see
        # them (role) and which need a paid plan, so the menu is generated from
        # it — a module added to MODULE_REGISTRY later appears here with no
        # template change. `locked` marks a module the user's ROLE allows but
        # their PLAN does not: it renders as an upgrade link instead of an
        # expandable sub-tree, because every screen underneath would refuse it.
        from listings.module_registry import (
            module_locked_for_user as _module_locked_for_user,
            visible_modules as _visible_modules,
        )
        sidebar_modules = [
            {
                "id": m["id"],
                "name": m["name"],
                "slug": m["slug"],
                "icon": m["icon"],
                "status": m["status"],
                "locked": _module_locked_for_user(request.user, m),
            }
            for m in _visible_modules(request.user)
        ]

        # Plan-feature flags for sidebar gating (superusers get everything).
        from billing.utils import get_user_plan
        if request.user.is_superuser:
            plan_features_json = json.dumps({"__superuser__": True})
        else:
            plan = get_user_plan(request.user, company=acting_company)
            comparison = (plan.comparison if plan and plan.comparison else {}) or {}
            features = {k: bool(v) for k, v in comparison.items()}
            plan_features_json = json.dumps(features)
            is_free_plan = bool(plan and plan.code == "free")
            is_basic_plan = bool(plan and plan.code == "basic")
            is_pro_plan = bool(plan and plan.code == "pro")
            is_global_plan = bool(plan and plan.code == "global")

            role_code = ""
            if request.user.role and request.user.role.code:
                role_code = request.user.role.code.lower()
            is_business_user = role_code == "business_user"
            # A Micro-Franchise owner is also a consultant (spec §9.1.2): they
            # get the certify / commissions sidebar entries too. `owns_micro`
            # (active OR suspended) keeps those tabs VISIBLE while suspended — the
            # page then shows a "suspended" message on access.
            from accounts.utils.permissions import is_micro_franchise_owner, owns_micro_franchise
            is_micro_owner = is_micro_franchise_owner(request.user)
            owns_micro = owns_micro_franchise(request.user)
            # True once the account owns a franchise node that has been ACTIVATED
            # (ACTIVE, or SUSPENDED = activated then paused — keeps historical
            # access per §6.2). Drives the "Franchises" list tab so it appears only
            # after activation, not for a franchise-role account with no live node.
            # Keyed on ownership, not on the role: buying a franchise no longer
            # rewrites the account's role, so a Business User who holds a
            # franchise keeps every business-user tab AND gets the franchise
            # section. "Add Sub-Franchise" additionally requires a node that CAN
            # have children — a non-Micro level (spec §8.2).
            from accounts.utils.franchise_access import (
                can_add_subfranchise as _can_add_sub,
                is_franchise_holder as _is_holder,
            )
            is_active_franchise_owner = _is_holder(request.user)
            can_add_subfranchise = _can_add_sub(request.user)
            is_basic_business_user = is_basic_plan and is_business_user
            is_pro_business_user = is_pro_plan and is_business_user
            is_global_business_user = is_global_plan and is_business_user
            is_paid_business_user = (
                is_basic_business_user or is_pro_business_user or is_global_business_user
            )

            # Pending incoming partnership requests on companies this user
            # owns. We surface the count site-wide so a banner can prompt
            # Free-plan users to upgrade — partnership_action requires a
            # paid plan, so without an upgrade these requests are stuck.
            owned_company_ids = Company.objects.filter(
                owner_user=request.user
            ).values_list("id", flat=True)
            if owned_company_ids:
                owned_company_ids = list(owned_company_ids)
                owns_any_company = True
                pending_partnership_count = CompanyConnection.objects.filter(
                    company_id__in=owned_company_ids,
                    status=CompanyConnection.STATUS_PENDING,
                ).count()
                # Pending join requests on companies this user owns — drives the
                # red badge on the "Join Requests" sidebar tab.
                pending_join_request_count = CompanyJoinRequest.objects.filter(
                    company_id__in=owned_company_ids,
                    status=CompanyJoinRequest.STATUS_PENDING,
                ).count()
                # Show the upgrade banner only for users who can't act on the
                # request right now: free plan, no plan at all, and no other
                # path to approve. Paid plans see the requests on the
                # Partnerships page directly.
                if pending_partnership_count and is_business_user and not is_paid_business_user:
                    show_partnership_upgrade_banner = True

            # Consultants see a sidebar badge with the number of pending
            # certification requests visible to them: unclaimed requests
            # (broadcast to all consultants) plus any they have claimed.
            # Use all_objects so pending rows that are still is_active=False
            # are still counted.
            if role_code == "consultant" or is_micro_owner:
                from django.db.models import Q as _Q
                pending_certification_count = Company.objects.filter(
                    certification_status="pending"
                ).filter(
                    _Q(consultant__isnull=True) | _Q(consultant=request.user)
                ).exclude(
                    # A certifier can't certify their own company — don't count it.
                    owner_user=request.user
                ).count()

                # Red counter on the "My Commissions" tab — number of the
                # consultant's commissions still pending payout. Rises when a
                # new commission is generated and falls as the admin marks them
                # paid, so it tracks live commission activity.
                try:
                    from billing.models import ConsultantCommission
                    new_commission_count = ConsultantCommission.objects.filter(
                        consultant=request.user, status="pending"
                    ).count()
                except Exception:
                    new_commission_count = 0

            # Business users see the status of their primary company's
            # certification request (used by a banner that says "Your company
            # was certified by [Consultant]" / "pending review"). Only the
            # primary company carries this state — secondary linkages don't.
            #
            # The banner is gated to the *creator* of the company (owner_user
            # == request.user). When a business user merely JOINS an
            # already-existing company, the certification belongs to the
            # original creator and showing "Your company was certified by …"
            # is misleading — the joining user didn't file the request and
            # shouldn't be told they did.
            if is_business_user:
                # Reflect the ACTIVE company's certification status — the one
                # selected in the company switcher — so the banner matches the
                # Certifications page and My Companies rather than jumping to
                # whichever owned company was most recently decided. Joined
                # companies are excluded: the certification belongs to the
                # company's creator, so the banner is gated to owner_user ==
                # request.user.
                active_company = acting_company
                if (
                    active_company
                    and active_company.owner_user_id == request.user.id
                    and active_company.certification_status
                    in ("pending", "certified", "rejected")
                ):
                    bu_certification_status = active_company.certification_status or ""
                    bu_certification_company_name = active_company.name
                    if active_company.certified_by:
                        bu_certification_consultant_name = (
                            f"{active_company.certified_by.first_name} "
                            f"{active_company.certified_by.last_name}"
                        ).strip() or active_company.certified_by.email

                    # "Certified" is a one-off success announcement, not a
                    # standing state like "pending". It is derived from
                    # Company.certification_status, which never clears, so
                    # before this the banner reappeared on every single page
                    # load for the rest of the company's life. Show it once —
                    # the first render after the consultant's decision — then
                    # suppress it.
                    #
                    # The marker is keyed by certified_at, so a company that is
                    # later re-certified announces itself again. "pending" and
                    # "rejected" are untouched: both describe an ongoing
                    # situation the user still has to act on.
                    session = getattr(request, "session", None)
                    if bu_certification_status == "certified" and session is not None:
                        stamp = (
                            active_company.certified_at.isoformat()
                            if active_company.certified_at
                            else "unstamped"
                        )
                        seen = session.get("bu_cert_banner_seen") or {}
                        if seen.get(str(active_company.pk)) == stamp:
                            bu_certification_status = ""
                            bu_certification_company_name = ""
                            bu_certification_consultant_name = ""
                        else:
                            seen[str(active_company.pk)] = stamp
                            session["bu_cert_banner_seen"] = seen

        # Superusers get the global pending count so admins can step in.
        if request.user.is_superuser:
            pending_certification_count = Company.objects.filter(
                certification_status="pending"
            ).count()
            # Red counter on the admin "Commissions" tab — all commission
            # requests still pending payout across every consultant. Rises when
            # a new commission is generated and falls as the admin marks them
            # paid, so the admin can see at a glance when one needs action.
            try:
                from billing.models import ConsultantCommission
                new_commission_count = ConsultantCommission.objects.filter(
                    status="pending"
                ).count()
            except Exception:
                new_commission_count = 0

        # Pending Coordinator role requests — Super Admin sidebar badge,
        # plus a flag for the BU profile page to suppress the "Become a
        # Coordinator" button while their previous request is still pending.
        try:
            from accounts.models import CoordinatorRequest
            if request.user.is_superuser:
                pending_coordinator_request_count = CoordinatorRequest.objects.filter(
                    status=CoordinatorRequest.STATUS_PENDING
                ).count()
            else:
                has_pending_coordinator_request = CoordinatorRequest.objects.filter(
                    user=request.user, status=CoordinatorRequest.STATUS_PENDING
                ).exists()
        except Exception:
            pass

        # Pending registration applications, counted per queue. Each badge must
        # count exactly the roles its own page lists, or the sidebar reports work
        # that isn't there — or worse, stays silent about work that is. The role
        # split is imported rather than restated: an earlier hardcoded copy here
        # left out consultants entirely, so a waiting consultant produced no
        # badge at all while sitting locked out of the app (Sep 2026).
        if request.user.is_superuser:
            try:
                from django.db.models import Q as _Q
                from accounts.view.application_review import QUEUE_BY_ROLE
                from FontEsin.middleware.require_application_approval import (
                    GATED_ROLE_CODES,
                )

                def _submitted(role_codes):
                    if not role_codes:
                        return 0
                    role_q = _Q()
                    for code in role_codes:
                        role_q |= _Q(role__code__iexact=code)
                    return User.objects.filter(
                        role_q, application_status="submitted",
                    ).count()

                # Coordinator sign-ups now sit in the Coordinator Requests queue
                # alongside the upgrade requests, so they join that badge.
                pending_coordinator_request_count += _submitted(["coordinator"])
                pending_consultant_request_count = _submitted(["consultant"])
                # Whatever has no queue of its own stays on the general list.
                pending_application_count = _submitted([
                    c for c in GATED_ROLE_CODES if c not in QUEUE_BY_ROLE
                ])
            except Exception:
                pending_application_count = 0

            # Pending franchise applications (request → approve → activate) —
            # Super Admin sidebar badge for the Franchise Requests queue.
            try:
                from accounts.view.franchise import pending_franchise_application_count as _pfac
                pending_franchise_application_count = _pfac(request.user)
            except Exception:
                pending_franchise_application_count = 0

        # Sub-franchise requests routed to this user as the direct-parent
        # operational reviewer (spec §4.2) — franchise-holder sidebar badge.
        if not request.user.is_superuser:
            try:
                from accounts.view.franchise import pending_child_request_count as _pcrc
                pending_child_franchise_request_count = _pcrc(request.user)
            except Exception:
                pending_child_franchise_request_count = 0

        # Unread in-app messages — every account type sees this badge. For
        # business users it's scoped to the active company (+ account-level)
        # so the badge matches the company-scoped inbox.
        try:
            from accounts.utils.notifications import scope_notifications_qs
            unread_message_count = scope_notifications_qs(
                Notification.objects.filter(recipient=request.user, is_read=False),
                request.user,
                active_company=acting_company,
            ).count()
            # The bell dropdown lists UNREAD notifications only. It used to show
            # the 8 most recent regardless of read state, so notifications the
            # user had already opened kept reappearing under a bell whose badge
            # said zero. The full history stays one click away in the inbox
            # ("View all notifications").
            recent_notifications = list(
                scope_notifications_qs(
                    Notification.objects.filter(recipient=request.user, is_read=False),
                    request.user,
                    active_company=acting_company,
                ).order_by("-created_at")[:8]
            )
        except Exception:
            unread_message_count = 0
            recent_notifications = []

        # Unread website contact-form messages — drives the red badge on the
        # superuser-only "Messages" sidebar tab.
        if request.user.is_superuser:
            try:
                from accounts.models import ContactMessage
                unread_contact_message_count = ContactMessage.objects.filter(
                    is_read=False
                ).count()
            except Exception:
                unread_contact_message_count = 0

        # Whether this user has a paid-plan upgrade awaiting admin approval
        # (a Subscription in "created" state). While pending, the user is on
        # temporary Free access and partnership "Connect" actions are locked
        # until approval — the template greys out the Connect button and
        # company_connect rejects the request server-side.
        try:
            # Plans are company-scoped, so a pending upgrade only locks the
            # ACTIVE company — a pending request on another owned company must
            # not gate this session. get_pending_subscription resolves the
            # active company (falling back to a legacy user-level pending sub).
            from billing.utils import get_pending_subscription
            has_pending_paid_upgrade = get_pending_subscription(
                request.user, company=acting_company
            ) is not None
        except Exception:
            logger.exception(
                "has_pending_paid_upgrade lookup failed for user %s",
                getattr(request.user, "pk", None),
            )
            has_pending_paid_upgrade = False

        # Pending payment approvals — drives the red badge on the superuser's
        # "Invoices" sidebar tab. A "new" invoice is a subscription awaiting
        # admin approval (status="created"); this mirrors the on-page pending
        # count in billing.views.payment_list. Only the Super Admin approves
        # payments, so the count is scoped to superusers.
        if request.user.is_superuser:
            try:
                from billing.models import Subscription
                pending_invoice_count = Subscription.objects.filter(
                    status="created"
                ).count()
            except Exception:
                pending_invoice_count = 0

        # Active-company context for the top-bar company switcher. Plans are
        # company-scoped, so a Business User who owns several companies can
        # switch which one governs their session; the switcher only shows when
        # there's more than one to pick from.
        if not request.user.is_superuser:
            _role_code = ""
            if request.user.role and request.user.role.code:
                _role_code = request.user.role.code.lower()
            if _role_code == "business_user":
                owned_company_count = Company.objects.filter(
                    owner_user=request.user
                ).count()
                can_switch_company = owned_company_count > 1
                try:
                    from billing.utils import get_active_subscription
                    # Resolved once at the top of this block (middleware cache
                    # first, direct resolve as the non-request fallback).
                    active_company = acting_company
                    if active_company:
                        active_company_name = active_company.name
                        active_company_certified = (
                            (active_company.certification_status or "").lower() == "certified"
                        )
                        # Renewal prompt: the active company's PAID plan has
                        # ended (or ends within 30 days). The consultant asks
                        # the company to renew; paying again starts a fresh term
                        # and re-pays the certifying consultant.
                        from django.utils import timezone as _tz
                        from datetime import timedelta as _td
                        _sub = get_active_subscription(request.user, company=active_company)
                        if _sub and _sub.plan_id:
                            active_plan_code = (_sub.plan.code or "").lower()
                            if active_plan_code not in ("", "free") and _sub.end_date:
                                active_plan_needs_renewal = _sub.end_date <= _tz.now() + _td(days=30)
                except Exception:
                    logger.exception(
                        "active-company header context failed for user %s",
                        getattr(request.user, "pk", None),
                    )
                    active_company = None

    # Business-user role check, independent of plan. Computed here rather than
    # in the branch above so it is defined for superusers and anonymous
    # visitors too.
    is_business_user_role = (
        request.user.is_authenticated and not request.user.is_superuser
        and request.user.role is not None
        and (request.user.role.code or "").lower() == "business_user"
    )

    return {
        "is_tenant_admin": is_tenant_admin,
        "sidebar_company_count": sidebar_company_count,
        "plan_features_json": plan_features_json,
        "is_free_plan": is_free_plan,
        "is_basic_plan": is_basic_plan,
        "is_pro_plan": is_pro_plan,
        "is_global_plan": is_global_plan,
        "is_basic_business_user": is_basic_business_user,
        "is_pro_business_user": is_pro_business_user,
        "is_global_business_user": is_global_business_user,
        "is_paid_business_user": is_paid_business_user,
        # Professional modules the sidebar tree renders, each flagged `locked`
        # when the user's role allows it but their plan does not.
        # See listings.module_registry.
        "sidebar_modules": sidebar_modules,
        # Back-compat alias for existing template gates that haven't been swapped over.
        "is_basic_or_pro_business_user": is_paid_business_user,
        # True for any BU regardless of plan (free / basic / pro / global).
        # Used to gate features like Connect that are now available on free.
        "is_business_user": is_business_user_role,
        # The Free plan's Company Database is a NAME-ONLY directory of the
        # user's own town: the Industry and Location columns are dropped from
        # both the header and every row (details are what the paid tiers buy).
        # `is_free_plan` alone isn't enough — it's also true for non-business
        # roles, whose table keeps its normal columns.
        "free_plan_names_only": is_free_plan and is_business_user_role,
        "pending_partnership_count": pending_partnership_count,
        "pending_join_request_count": pending_join_request_count,
        "owns_any_company": owns_any_company,
        "show_partnership_upgrade_banner": show_partnership_upgrade_banner,
        "pending_certification_count": pending_certification_count,
        "new_commission_count": new_commission_count,
        # A Micro-Franchise owner is also a consultant (spec §9.1.2) — drives the
        # Certifications / Commissions sidebar entries for them.
        "is_micro_franchise_owner": is_micro_owner,
        # Owns a Micro node in any live state (active/suspended) — keeps the
        # Certifications / Commissions tabs visible even while suspended.
        "owns_micro_franchise": owns_micro,
        # True when the account owns an activated franchise node — gates the
        # "Franchises" list tab so it shows only after activation (spec §6.2).
        "is_active_franchise_owner": is_active_franchise_owner,
        # True when the owner has a non-Micro active node — gates "Add
        # Sub-Franchise" (a Micro can't have children, spec §8.2).
        "can_add_subfranchise": can_add_subfranchise,
        "pending_coordinator_request_count": pending_coordinator_request_count,
        "pending_consultant_request_count": pending_consultant_request_count,
        "pending_application_count": pending_application_count,
        "pending_franchise_application_count": pending_franchise_application_count,
        "pending_child_franchise_request_count": pending_child_franchise_request_count,
        "has_pending_coordinator_request": has_pending_coordinator_request,
        # Sum of every superuser request queue — drives the red counter on
        # the sidebar "Requests" parent so admins see one aggregated total
        # while the dropdown still shows per-queue counts when expanded.
        # New queues (franchise / partner / etc.) just add themselves here.
        "pending_requests_total": (
            pending_coordinator_request_count
            + pending_consultant_request_count
            + pending_application_count
            + pending_franchise_application_count
        ),
        "bu_certification_status": bu_certification_status,
        "bu_certification_consultant_name": bu_certification_consultant_name,
        "bu_certification_company_name": bu_certification_company_name,
        "unread_message_count": unread_message_count,
        "recent_notifications": recent_notifications,
        "unread_contact_message_count": unread_contact_message_count,
        "pending_invoice_count": pending_invoice_count,
        # Company switcher (Business Users with multiple companies).
        "active_company": active_company,
        "active_company_name": active_company_name,
        # Whether the active company is certified — gates the "select a paid
        # plan" CTA (paid plans are unavailable until a consultant certifies).
        "active_company_certified": active_company_certified,
        # Active company's paid plan has ended / ends within 30 days — surfaces
        # a "Renew" CTA. Renewing re-pays the certifying consultant.
        "active_plan_needs_renewal": active_plan_needs_renewal,
        "active_plan_code": active_plan_code,
        "owned_company_count": owned_company_count,
        "can_switch_company": can_switch_company,
    }
