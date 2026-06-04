import json

from accounts.models import UserRole, Company, CompanyConnection, CompanyJoinRequest, Notification, User


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
    pending_partnership_count = 0
    pending_join_request_count = 0
    owns_any_company = False
    show_partnership_upgrade_banner = False
    pending_certification_count = 0
    new_commission_count = 0
    pending_coordinator_request_count = 0
    pending_application_count = 0
    has_pending_coordinator_request = False
    bu_certification_status = ""
    bu_certification_consultant_name = ""
    unread_message_count = 0
    unread_contact_message_count = 0
    pending_invoice_count = 0
    has_pending_paid_upgrade = False

    if request.user.is_authenticated:
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

        # Plan-feature flags for sidebar gating (superusers get everything).
        from billing.utils import get_user_plan
        if request.user.is_superuser:
            plan_features_json = json.dumps({"__superuser__": True})
        else:
            plan = get_user_plan(request.user)
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
            if role_code == "consultant":
                from django.db.models import Q as _Q
                pending_certification_count = Company.all_objects.filter(
                    certification_status="pending"
                ).filter(
                    _Q(consultant__isnull=True) | _Q(consultant=request.user)
                ).exclude(
                    # A consultant can't certify their own company — don't count it.
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
            if is_business_user and getattr(request.user, "primary_company_id", None):
                primary = Company.all_objects.filter(
                    id=request.user.primary_company_id
                ).select_related("certified_by").first()
                if primary and primary.owner_user_id == request.user.id:
                    bu_certification_status = primary.certification_status or ""
                    if primary.certified_by:
                        bu_certification_consultant_name = (
                            f"{primary.certified_by.first_name} "
                            f"{primary.certified_by.last_name}"
                        ).strip() or primary.certified_by.email

        # Superusers get the global pending count so admins can step in.
        if request.user.is_superuser:
            pending_certification_count = Company.all_objects.filter(
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

        # Pending coordinator / franchise account applications — Super Admin
        # sidebar badge for the Applications queue.
        if request.user.is_superuser:
            try:
                from django.db.models import Q as _Q
                pending_application_count = User.objects.filter(
                    _Q(role__code__iexact="coordinator") | _Q(role__code__iexact="franchise"),
                    application_status="submitted",
                ).count()
            except Exception:
                pending_application_count = 0

        # Unread in-app messages — every account type sees this badge.
        try:
            unread_message_count = Notification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
        except Exception:
            unread_message_count = 0

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
            from billing.models import Subscription
            has_pending_paid_upgrade = Subscription.objects.filter(
                user=request.user, status="created"
            ).exists()
        except Exception:
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
        # Back-compat alias for existing template gates that haven't been swapped over.
        "is_basic_or_pro_business_user": is_paid_business_user,
        # True for any BU regardless of plan (free / basic / pro / global).
        # Used to gate features like Connect that are now available on free.
        "is_business_user": (
            request.user.is_authenticated and not request.user.is_superuser
            and request.user.role is not None
            and (request.user.role.code or "").lower() == "business_user"
        ),
        "pending_partnership_count": pending_partnership_count,
        "pending_join_request_count": pending_join_request_count,
        "owns_any_company": owns_any_company,
        "show_partnership_upgrade_banner": show_partnership_upgrade_banner,
        "pending_certification_count": pending_certification_count,
        "new_commission_count": new_commission_count,
        "pending_coordinator_request_count": pending_coordinator_request_count,
        "pending_application_count": pending_application_count,
        "has_pending_coordinator_request": has_pending_coordinator_request,
        # Sum of every superuser request queue — drives the red counter on
        # the sidebar "Requests" parent so admins see one aggregated total
        # while the dropdown still shows per-queue counts when expanded.
        # New queues (franchise / partner / etc.) just add themselves here.
        "pending_requests_total": pending_coordinator_request_count + pending_application_count,
        "bu_certification_status": bu_certification_status,
        "bu_certification_consultant_name": bu_certification_consultant_name,
        "unread_message_count": unread_message_count,
        "unread_contact_message_count": unread_contact_message_count,
        "pending_invoice_count": pending_invoice_count,
    }
