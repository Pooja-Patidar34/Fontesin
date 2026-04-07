from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
import json

from accounts.models import Tenant, Company, User
from billing.models import Subscription, Invoice, CommercialPlan
from billing.utils import get_user_plan, get_active_subscription, has_plan_feature


@login_required
def dashboard(request):
    user = request.user

    context = {}
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    if user.is_superuser:
        # ── Tenant metrics ──
        context.update({
            "total_tenants": Tenant.objects.count(),
            "active_tenants": Tenant.objects.filter(is_active=True).count(),
            "inactive_tenants": Tenant.objects.filter(is_active=False).count(),
        })

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

        # ── Subscription metrics ──
        active_subs = Subscription.objects.filter(status="active").count()
        new_subs_week = Subscription.objects.filter(status="active", updated_at__gte=week_ago).count()
        context.update({
            "active_subscriptions": active_subs,
            "new_subs_week": new_subs_week,
        })

        # ── Revenue metrics ──
        monthly_revenue = Invoice.objects.filter(
            status="paid", paid_at__gte=month_ago
        ).aggregate(total=Sum("amount"))["total"] or 0
        prev_month_start = month_ago - timedelta(days=30)
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

        # ── Invoice metrics ──
        pending_invoices = Invoice.objects.filter(status="pending").count()
        overdue_invoices = Invoice.objects.filter(status="pending", due_date__lt=now).count()
        context.update({
            "pending_invoices": pending_invoices,
            "overdue_invoices": overdue_invoices,
        })

        # ── Pending approvals ──
        pending_approvals = Subscription.objects.filter(status="created").count()
        context["pending_approvals"] = pending_approvals

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

        # ── Revenue trend (last 6 months) ──
        revenue_labels = []
        revenue_data = []
        for i in range(5, -1, -1):
            m_start = (now - timedelta(days=30 * i)).replace(day=1)
            if i > 0:
                m_end = (now - timedelta(days=30 * (i - 1))).replace(day=1)
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

        # ── Recent companies ──
        recent_companies = (
            Company.objects
            .select_related("tenant")
            .order_by("-created_at")[:5]
        )
        # Attach plan info to recent companies
        for company in recent_companies:
            owner = User.objects.filter(primary_company=company).first()
            if owner:
                sub = Subscription.objects.filter(
                    user=owner, status__in=["active", "trial", "created"]
                ).select_related("plan").first()
                company.plan_name = sub.plan.code.upper() if sub else None
            else:
                company.plan_name = None
        context["recent_companies"] = recent_companies

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
        for s in Subscription.objects.filter(status="active").order_by("-updated_at")[:3]:
            recent_activity.append({
                "time": s.updated_at,
                "title": "Payment confirmed",
                "desc": f"{s.plan.name} subscription – {s.user.email}" if s.user else s.plan.name,
                "color": "#16a34a",
            })

        # Overdue invoices
        for inv in Invoice.objects.filter(status="pending", due_date__lt=now).order_by("-due_date")[:2]:
            u = inv.subscription.user
            recent_activity.append({
                "time": inv.due_date,
                "title": "Invoice overdue",
                "desc": f"{u.email if u else 'Unknown'} – ${inv.amount} pending",
                "color": "#d97706",
            })

        recent_activity.sort(key=lambda x: x["time"], reverse=True)
        context["recent_activity"] = recent_activity[:6]

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

    elif user.role and user.role.name == "tenant_admin":
        tenant = user.tenant

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

    else:
        # Regular user - show tenant-scoped data + plan features
        tenant = user.tenant
        plan = get_user_plan(user)
        subscription = get_active_subscription(user)

        context.update({
            # Tenant-scoped metrics (same data as tenant_admin)
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

            # Plan info
            "user_plan": plan,
            "subscription": subscription,
            "has_company_registry": has_plan_feature(user, "company_registry"),
            "has_advanced_analytics": has_plan_feature(user, "advanced_analytics"),
            "has_api_access": has_plan_feature(user, "api_access"),
            "has_data_export": has_plan_feature(user, "data_export"),
            "has_franchise_management": has_plan_feature(user, "franchise_management"),
        })

    # Role label for welcome banner
    if user.is_superuser:
        context["role_label"] = "Platform Admin"
    elif user.role:
        context["role_label"] = user.role.name.replace("_", " ").title()
    else:
        context["role_label"] = "User"

    context["active_menu"] = "dashboard"
    return render(request, "dashboard/index.html", context)
