"""Routing helpers for certification requests.

When a Business User submits a company for certification, the request is
routed to a consultant based on locality. We prefer a consultant who already
manages companies in the same city, then fall back progressively to country
and finally any consultant.

Keeping the routing logic in one place means both the dashboard modal and the
profile-page form pick the same consultant without re-implementing the rules.
"""

from django.db.models import Count, Q

from accounts.models import User, Company


def find_consultant_for_company(company):
    """Pick a consultant who should review this company's certification.

    The function never raises — if no consultant exists in the system it
    returns None, and the request enters an unassigned state that admins (or
    any consultant via a future "claim" action) can pick up.

    Resolution order:
      1. Consultants who already manage at least one company in the same city.
      2. Consultants who manage at least one company in the same country.
      3. Any consultant.

    Within each tier we prefer the consultant with the fewest pending
    certification requests already on their queue so the workload stays
    roughly balanced.
    """
    consultants = User.objects.filter(role__code__iexact="consultant", is_active=True)
    if not consultants.exists():
        return None

    city = (company.city or "").strip()
    country = (company.country or "").strip()

    pending_count_q = Count(
        "consulting_companies",
        filter=Q(consulting_companies__certification_status="pending"),
    )
    consultants = consultants.annotate(pending_count=pending_count_q)

    # Tier 1: same city
    if city:
        city_consultants = consultants.filter(
            consulting_companies__city__iexact=city
        ).distinct().order_by("pending_count", "id")
        first = city_consultants.first()
        if first:
            return first

    # Tier 2: same country
    if country:
        country_consultants = consultants.filter(
            consulting_companies__country__iexact=country
        ).distinct().order_by("pending_count", "id")
        first = country_consultants.first()
        if first:
            return first

    # Tier 3: any consultant — lowest queue first
    return consultants.order_by("pending_count", "id").first()
