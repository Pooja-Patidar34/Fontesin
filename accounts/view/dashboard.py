import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import json

from accounts.models import Tenant, Company, User
from billing.models import Subscription, Invoice, CommercialPlan
from billing.utils import (
    get_user_plan,
    get_active_subscription,
    has_plan_feature,
    get_deactivated_paid_plan,
)

logger = logging.getLogger("technical")


@login_required
def dashboard(request):
    user = request.user

    # NOTE: The earlier blocking gate that redirected business users with a
    # pending paid Subscription (status="created") to auth/pending_approval.html
    # was removed. The product flow now lets users into the dashboard with
    # their current active plan (Free, by default) while a paid upgrade is
    # awaiting admin approval; the pending request is surfaced as a "Pending
    # Approval" card on the profile page instead. select_plan auto-creates a
    # Free active sub when a fresh signup picks a paid plan, so every user
    # who reaches the dashboard has at least Free-tier access. Feature gates
    # downstream resolve against the *active* sub (see get_active_subscription
    # in billing/utils.py — it deliberately excludes "created" rows).

    context = {}
    now = timezone.now()
    month_ago = now - relativedelta(months=1)
    week_ago = now - timedelta(days=7)

    if user.is_superuser:
        try:
            # ── Tenant metrics ──
            context.update({
                "total_tenants": Tenant.objects.count(),
                "active_tenants": Tenant.objects.filter(is_active=True).count(),
                "inactive_tenants": Tenant.objects.filter(is_active=False).count(),
            })
        except Exception as e:
            logger.error("Dashboard: tenant metrics failed: %s", e)

        try:
            # ── Company metrics ──
            total_companies = Company.objects.count()
            active_companies = Company.objects.filter(is_active=True).count()
            new_companies_month = Company.objects.filter(created_at__gte=month_ago).count()
            context.update({
                "total_companies": total_companies,
                "active_companies": active_companies,
                "inactive_companies": Company.objects.filter(is_active=False).count(),
                "new_companies_month": new_companies_month,
            })
        except Exception as e:
            logger.error("Dashboard: company metrics failed: %s", e)

        try:
            # ── User metrics ──
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            new_users_month = User.objects.filter(created_at__gte=month_ago).count()
            context.update({
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": User.objects.filter(is_active=False).count(),
                "new_users_month": new_users_month,
            })
        except Exception as e:
            logger.error("Dashboard: user metrics failed: %s", e)

        try:
            # ── Subscription metrics ──
            active_subs = Subscription.objects.filter(status="active").count()
            new_subs_week = Subscription.objects.filter(status="active", updated_at__gte=week_ago).count()
            context.update({
                "active_subscriptions": active_subs,
                "new_subs_week": new_subs_week,
            })
        except Exception as e:
            logger.error("Dashboard: subscription metrics failed: %s", e)

        try:
            # ── Revenue metrics ──
            monthly_revenue = Invoice.objects.filter(
                status="paid", paid_at__gte=month_ago
            ).aggregate(total=Sum("amount"))["total"] or 0
            prev_month_start = month_ago - relativedelta(months=1)
            prev_monthly_revenue = Invoice.objects.filter(
                status="paid", paid_at__gte=prev_month_start, paid_at__lt=month_ago
            ).aggregate(total=Sum("amount"))["total"] or 0
            if prev_monthly_revenue > 0:
                revenue_change = round(((monthly_revenue - prev_monthly_revenue) / prev_monthly_revenue) * 100, 1)
            else:
                revenue_change = 0
            context.update({
                "monthly_revenue": monthly_revenue,
                "revenue_change": revenue_change,
            })
        except Exception as e:
            logger.error("Dashboard: revenue metrics failed: %s", e)

        try:
            # ── Invoice metrics ──
            pending_invoices = Invoice.objects.filter(status="pending").count()
            overdue_invoices = Invoice.objects.filter(status="pending", due_date__lt=now).count()
            context.update({
                "pending_invoices": pending_invoices,
                "overdue_invoices": overdue_invoices,
            })
        except Exception as e:
            logger.error("Dashboard: invoice metrics failed: %s", e)

        try:
            # ── Pending approvals ──
            pending_approvals = Subscription.objects.filter(status="created").count()
            context["pending_approvals"] = pending_approvals
        except Exception as e:
            logger.error("Dashboard: pending approvals failed: %s", e)

        try:
            # ── Subscription plan distribution (for donut chart) ──
            plan_dist = (
                Subscription.objects
                .filter(status__in=["active", "trial", "created"])
                .values("plan__name", "plan__code")
                .annotate(count=Count("id"))
                .order_by("plan__code")
            )
            plan_labels = [p["plan__name"] for p in plan_dist]
            plan_counts = [p["count"] for p in plan_dist]
            context["plan_labels_json"] = json.dumps(plan_labels)
            context["plan_counts_json"] = json.dumps(plan_counts)
        except Exception as e:
            logger.error("Dashboard: plan distribution failed: %s", e)

        try:
            # ── Revenue trend (last 6 months) ──
            revenue_labels = []
            revenue_data = []
            for i in range(5, -1, -1):
                m_start = (now - relativedelta(months=i)).replace(day=1)
                if i > 0:
                    m_end = (now - relativedelta(months=i - 1)).replace(day=1)
                else:
                    m_end = now
                label = m_start.strftime("%b")
                total = Invoice.objects.filter(
                    status="paid", paid_at__gte=m_start, paid_at__lt=m_end
                ).aggregate(t=Sum("amount"))["t"] or 0
                revenue_labels.append(label)
                revenue_data.append(float(total))
            context["revenue_labels_json"] = json.dumps(revenue_labels)
            context["revenue_data_json"] = json.dumps(revenue_data)
        except Exception as e:
            logger.error("Dashboard: revenue trend failed: %s", e)

        try:
            # ── Recent companies ──
            recent_companies = list(
                Company.objects
                .select_related("tenant")
                .order_by("-created_at")[:5]
            )
            # Prefetch owners and subscriptions in bulk to avoid N+1 queries
            company_ids = [c.id for c in recent_companies]
            owners = User.objects.filter(primary_company_id__in=company_ids)
            owner_by_company = {u.primary_company_id: u for u in owners}

            owner_ids = [u.id for u in owners]
            subs = (
                Subscription.objects
                .filter(user_id__in=owner_ids, status__in=["active", "trial", "created"])
                .select_related("plan")
            )
            sub_by_user = {s.user_id: s for s in subs}

            for company in recent_companies:
                owner = owner_by_company.get(company.id)
                if owner:
                    sub = sub_by_user.get(owner.id)
                    company.plan_name = sub.plan.code.upper() if sub else None
                else:
                    company.plan_name = None
            context["recent_companies"] = recent_companies
        except Exception as e:
            logger.error("Dashboard: recent companies failed: %s", e)

        try:
            # ── Recent activity ──
            recent_activity = []

            # Recent company registrations
            for c in Company.objects.order_by("-created_at")[:3]:
                recent_activity.append({
                    "time": c.created_at,
                    "title": "New company registered",
                    "desc": f"{c.name} joined the platform",
                    "color": "#16a34a",
                })

            # Recent payment approvals
            for s in Subscription.objects.filter(status="active").select_related("plan", "user").order_by("-updated_at")[:3]:
                recent_activity.append({
                    "time": s.updated_at,
                    "title": "Payment confirmed",
                    "desc": f"{s.plan.name} subscription – {s.user.email}" if s.user else s.plan.name,
                    "color": "#16a34a",
                })

            # Overdue invoices
            for inv in Invoice.objects.filter(status="pending", due_date__lt=now).select_related("subscription__user").order_by("-due_date")[:2]:
                u = inv.subscription.user
                recent_activity.append({
                    "time": inv.due_date,
                    "title": "Invoice overdue",
                    "desc": f"{u.email if u else 'Unknown'} – ${inv.amount} pending",
                    "color": "#d97706",
                })

            recent_activity.sort(key=lambda x: x["time"], reverse=True)
            context["recent_activity"] = recent_activity[:6]
        except Exception as e:
            logger.error("Dashboard: recent activity failed: %s", e)

        try:
            # ── Regional performance (companies by country) ──
            region_data = (
                Company.objects
                .exclude(country__isnull=True)
                .exclude(country="")
                .values("country")
                .annotate(count=Count("id"))
                .order_by("-count")[:7]
            )
            region_labels = [r["country"] for r in region_data]
            region_counts = [r["count"] for r in region_data]
            context["region_labels_json"] = json.dumps(region_labels)
            context["region_counts_json"] = json.dumps(region_counts)
        except Exception as e:
            logger.error("Dashboard: regional performance failed: %s", e)

        try:
            # ── Industry breakdown ──
            industry_data = (
                User.objects
                .exclude(primary_industry__isnull=True)
                .exclude(primary_industry="")
                .values("primary_industry")
                .annotate(count=Count("id"))
                .order_by("-count")[:7]
            )
            industry_labels = [i["primary_industry"] for i in industry_data]
            industry_counts = [i["count"] for i in industry_data]
            context["industry_labels_json"] = json.dumps(industry_labels)
            context["industry_counts_json"] = json.dumps(industry_counts)
        except Exception as e:
            logger.error("Dashboard: industry breakdown failed: %s", e)

        try:
            # ── Active regions count ──
            active_regions = (
                Company.objects
                .exclude(country__isnull=True)
                .exclude(country="")
                .values("country")
                .distinct()
                .count()
            )
            context["active_regions"] = active_regions
        except Exception as e:
            logger.error("Dashboard: active regions failed: %s", e)

    elif user.role and user.role.name == "tenant_admin":
        tenant = user.tenant
        try:
            context.update({
                "total_companies": Company.objects.filter(tenant=tenant).count(),
                "active_companies": Company.objects.filter(
                    tenant=tenant, is_active=True
                ).count(),
                "inactive_companies": Company.objects.filter(
                    tenant=tenant, is_active=False
                ).count(),
                "total_users": User.objects.filter(tenant=tenant).count(),
                "active_users": User.objects.filter(
                    tenant=tenant, is_active=True
                ).count(),
                "inactive_users": User.objects.filter(
                    tenant=tenant, is_active=False
                ).count(),
            })
        except Exception as e:
            logger.error("Dashboard: tenant_admin metrics failed: %s", e)

    else:
        # Regular user - show counts scoped to the companies they're linked to,
        # matching what the Company Database / Users list pages now show.
        tenant = user.tenant
        try:
            subscription = get_active_subscription(user)
            plan = get_user_plan(user, subscription=subscription)
            deactivated_plan = get_deactivated_paid_plan(user, subscription=subscription)
            if deactivated_plan:
                messages.warning(
                    request,
                    f"Your {deactivated_plan.name} plan was deactivated by the admin. "
                    "You have been moved to the Free plan. "
                    "Please activate another plan to continue.",
                )

            from django.db.models import Q
            linked_companies = Company.objects.filter(
                Q(consultant=user)
                | Q(owner_user=user)
                | Q(primary_users=user)
            ).distinct()
            linked_company_ids = list(linked_companies.values_list("id", flat=True))
            users_of_linked_companies = User.objects.filter(
                Q(primary_company_id__in=linked_company_ids)
                | Q(usercompany__company_id__in=linked_company_ids)
            ).distinct() if linked_company_ids else User.objects.none()

            context.update({
                "total_companies": linked_companies.count(),
                "active_companies": linked_companies.filter(is_active=True).count(),
                "inactive_companies": linked_companies.filter(is_active=False).count(),
                "total_users": users_of_linked_companies.count(),
                "active_users": users_of_linked_companies.filter(is_active=True).count(),
                "inactive_users": users_of_linked_companies.filter(is_active=False).count(),

                # Plan info
                "user_plan": plan,
                "subscription": subscription,
                "deactivated_plan": deactivated_plan,
                "has_company_registry": has_plan_feature(user, "company_registry"),
                "has_advanced_analytics": has_plan_feature(user, "advanced_analytics"),
                "has_api_access": has_plan_feature(user, "api_access"),
                "has_data_export": has_plan_feature(user, "data_export"),
                "has_franchise_management": has_plan_feature(user, "franchise_management"),
            })
        except Exception as e:
            logger.error("Dashboard: regular user metrics failed: %s", e)

    # Role label for welcome banner
    if user.is_superuser:
        context["role_label"] = "Platform Admin"
    elif user.role:
        context["role_label"] = user.role.name.replace("_", " ").title()
    else:
        context["role_label"] = "User"

    context["active_menu"] = "dashboard"
    return render(request, "dashboard/index.html", context)
