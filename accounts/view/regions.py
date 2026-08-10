import json
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.translation import pgettext_lazy

from accounts.models import User


def region_us(request):
    return render(request, 'regions/region-us.html')

def region_de(request):
    return render(request, 'regions/region-de.html')

def region_cz(request):
    return render(request, 'regions/region-cz.html')

def region_ae(request):
    return render(request, 'regions/region-ae.html')

def region_jp(request):
    return render(request, 'regions/region-jp.html')


# Roll-out status badges. Lazy so the module-level table below stays a plain
# dict while the label still resolves in the viewer's language at render time —
# these are shown on the world map and on every "coming soon" country page.
STATUS_ACTIVE_Y1 = pgettext_lazy("website", "Active · Year 1")
STATUS_PLANNED_Y2 = pgettext_lazy("website", "Planned · Year 2")
STATUS_PLANNED_Y3 = pgettext_lazy("website", "Planned · Year 3")
STATUS_PLANNED_Y4 = pgettext_lazy("website", "Planned · Year 4")
STATUS_COMING_SOON = pgettext_lazy("website", "Coming soon")


# Country profiles that don't have full per-country templates yet land on
# the same "Coming soon" page, which carries enough info (name, flag,
# planned roll-out year) to set expectations.
COMING_SOON_REGIONS = {
    # Active markets (Year 1) shown on the world map without a full template yet.
    "gb": {"name": "United Kingdom", "flag": "🇬🇧", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "fr": {"name": "France",         "flag": "🇫🇷", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "nl": {"name": "Netherlands",    "flag": "🇳🇱", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "pl": {"name": "Poland",         "flag": "🇵🇱", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "at": {"name": "Austria",        "flag": "🇦🇹", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "ch": {"name": "Switzerland",    "flag": "🇨🇭", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "se": {"name": "Sweden",         "flag": "🇸🇪", "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    # Planned expansion markets.
    "sg": {"name": "Singapore",      "flag": "🇸🇬", "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "ca": {"name": "Canada",         "flag": "🇨🇦", "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "au": {"name": "Australia",      "flag": "🇦🇺", "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "br": {"name": "Brazil",         "flag": "🇧🇷", "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "in": {"name": "India",          "flag": "🇮🇳", "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "mx": {"name": "Mexico",         "flag": "🇲🇽", "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "kr": {"name": "South Korea",    "flag": "🇰🇷", "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "za": {"name": "South Africa",   "flag": "🇿🇦", "status": STATUS_PLANNED_Y4, "status_class": "status-badge--planned"},
}


# Basic, verifiable country facts for the data-driven region profile page.
# Keyed by lowercase ISO code. Holds only facts we can state reliably (capital,
# region, official language(s), currency, rollout status) — no fabricated
# economic statistics. The five markets with bespoke, data-rich templates
# (us/de/cz/ae/jp) keep their own pages and are intentionally NOT listed here;
# everything else on the world map renders through region_profile.html so a
# click lands on a real country page instead of the "coming soon" placeholder.
REGION_PROFILES = {
    # ---- Active markets (Year 1) ----
    "gb": {"name": "United Kingdom", "flag": "🇬🇧", "capital": "London",   "area": "Europe",
           "language": "English", "currency": "GBP – Pound Sterling",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "fr": {"name": "France", "flag": "🇫🇷", "capital": "Paris", "area": "Europe",
           "language": "French", "currency": "EUR – Euro",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "nl": {"name": "Netherlands", "flag": "🇳🇱", "capital": "Amsterdam", "area": "Europe",
           "language": "Dutch", "currency": "EUR – Euro",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "pl": {"name": "Poland", "flag": "🇵🇱", "capital": "Warsaw", "area": "Europe",
           "language": "Polish", "currency": "PLN – Polish Złoty",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "at": {"name": "Austria", "flag": "🇦🇹", "capital": "Vienna", "area": "Europe",
           "language": "German", "currency": "EUR – Euro",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "ch": {"name": "Switzerland", "flag": "🇨🇭", "capital": "Bern", "area": "Europe",
           "language": "German, French, Italian, Romansh", "currency": "CHF – Swiss Franc",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    "se": {"name": "Sweden", "flag": "🇸🇪", "capital": "Stockholm", "area": "Europe",
           "language": "Swedish", "currency": "SEK – Swedish Krona",
           "status": STATUS_ACTIVE_Y1, "status_class": "status-badge--active"},
    # ---- Planned expansion markets ----
    "sg": {"name": "Singapore", "flag": "🇸🇬", "capital": "Singapore", "area": "Asia",
           "language": "English, Malay, Mandarin, Tamil", "currency": "SGD – Singapore Dollar",
           "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "ca": {"name": "Canada", "flag": "🇨🇦", "capital": "Ottawa", "area": "North America",
           "language": "English, French", "currency": "CAD – Canadian Dollar",
           "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "au": {"name": "Australia", "flag": "🇦🇺", "capital": "Canberra", "area": "Oceania",
           "language": "English", "currency": "AUD – Australian Dollar",
           "status": STATUS_PLANNED_Y2, "status_class": "status-badge--planned"},
    "br": {"name": "Brazil", "flag": "🇧🇷", "capital": "Brasília", "area": "South America",
           "language": "Portuguese", "currency": "BRL – Brazilian Real",
           "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "in": {"name": "India", "flag": "🇮🇳", "capital": "New Delhi", "area": "Asia",
           "language": "Hindi, English", "currency": "INR – Indian Rupee",
           "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "mx": {"name": "Mexico", "flag": "🇲🇽", "capital": "Mexico City", "area": "North America",
           "language": "Spanish", "currency": "MXN – Mexican Peso",
           "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "kr": {"name": "South Korea", "flag": "🇰🇷", "capital": "Seoul", "area": "Asia",
           "language": "Korean", "currency": "KRW – South Korean Won",
           "status": STATUS_PLANNED_Y3, "status_class": "status-badge--planned"},
    "za": {"name": "South Africa", "flag": "🇿🇦", "capital": "Pretoria", "area": "Africa",
           "language": "English, Afrikaans, Zulu (11 official)", "currency": "ZAR – South African Rand",
           "status": STATUS_PLANNED_Y4, "status_class": "status-badge--planned"},
}


def region_detail(request, code):
    """Data-driven basic country profile for any curated map country that
    doesn't have a bespoke template. Renders name, flag, ISO, capital, region,
    language, currency, and rollout status from REGION_PROFILES. Falls back to
    the lightweight "coming soon" card for ISO codes we haven't curated, so a
    click on the world map always lands on a real page (never a 404)."""
    key = (code or "").lower()
    profile = REGION_PROFILES.get(key)
    if not profile:
        return region_coming_soon(request, code)
    return render(request, "regions/region_profile.html", {
        "p": profile,
        "code": key.upper(),
    })


def region_coming_soon(request, code):
    """Lightweight placeholder for regions that don't yet have a full
    per-country template. Renders the country name, flag, and planned
    roll-out so visitors get expectation-setting instead of a 404.

    Any country code resolves: curated entries above carry a tailored
    status/flag; anything else falls back to a generic "coming soon" card
    named from the ISO code (so clicking any country on the world map always
    lands on a real page, never a 404)."""
    key = (code or "").lower()
    info = COMING_SOON_REGIONS.get(key)
    if not info:
        # Generic fallback for any country not explicitly curated. Use the
        # CountryChoices label for a friendly name when the code is known.
        from accounts.constants import CountryChoices
        label = dict(CountryChoices.CHOICES).get((code or "").upper())
        info = {
            "name": label or (code or "").upper(),
            "flag": "🌐",
            "status": STATUS_COMING_SOON,
            "status_class": "status-badge--planned",
        }
    return render(request, "regions/coming_soon.html", {
        "country": info,
        "code": (code or "").upper(),
    })


# Maps the target_region labels from templates/auth/apply.html:773-805 to
# approximate [lat, lng] so Leaflet can drop a marker. Unknown values fall
# back to a generic "Other" pin so the consultant still appears on the map.
REGION_COORDS = {
    "Czech Republic": [49.8175, 15.4730],
    "Germany": [51.1657, 10.4515],
    "Austria": [47.5162, 14.5501],
    "Switzerland": [46.8182, 8.2275],
    "Poland": [51.9194, 19.1451],
    "France": [46.2276, 2.2137],
    "United Kingdom": [55.3781, -3.4360],
    "Benelux (Belgium, Netherlands, Luxembourg)": [50.8503, 4.3517],
    "Scandinavia": [60.1282, 18.6435],
    "Other European country": [54.5260, 15.2551],
    "UAE": [23.4241, 53.8478],
    "Saudi Arabia": [23.8859, 45.0792],
    "Other MENA country": [26.8206, 30.8025],
    "Japan": [36.2048, 138.2529],
    "South Korea": [35.9078, 127.7669],
    "Australia": [-25.2744, 133.7751],
    "Other APAC country": [1.3521, 103.8198],
    "United States": [37.0902, -95.7129],
    "Canada": [56.1304, -106.3468],
    "Brazil": [-14.2350, -51.9253],
    "Mexico": [23.6345, -102.5528],
    "Other Americas country": [-8.7832, -55.4915],
}


@login_required
def regions_map_view(request):
    """Coordinator/superuser view that plots every consultant in the tenant on a
    world map using the target_region they chose during the apply flow."""
    user = request.user
    role_code = (user.role.code or "").upper() if user.role else ""
    if not (user.is_superuser or role_code == "COORDINATOR"):
        raise PermissionDenied()

    consultants = User.objects.filter(
        role__code__iexact="CONSULTANT",
        is_deleted=False,
    ).select_related("role", "primary_company", "tenant")

    if not user.is_superuser:
        consultants = consultants.filter(tenant=user.tenant)

    consultants = consultants.order_by("first_name", "last_name")

    grouped = defaultdict(list)
    for c in consultants:
        label = (c.target_region or "").strip() or "Unspecified"
        grouped[label].append(c)

    regions = []
    for label, members in sorted(grouped.items(), key=lambda kv: kv[0].lower()):
        coords = REGION_COORDS.get(label)
        regions.append({
            "label": label,
            "coords": coords,
            "count": len(members),
            "consultants": [
                {
                    "id": str(m.id),
                    "name": f"{m.first_name} {m.last_name}".strip() or m.email,
                    "email": m.email,
                    "company": m.primary_company.name if m.primary_company else "",
                    "city": m.city or "",
                    "country": m.country or "",
                }
                for m in members
            ],
        })

    map_points = [
        {"label": r["label"], "coords": r["coords"], "count": r["count"],
         "consultants": [c["name"] for c in r["consultants"]]}
        for r in regions if r["coords"]
    ]

    context = {
        "active_menu": "regions",
        "regions": regions,
        "total_consultants": consultants.count(),
        "map_points_json": json.dumps(map_points),
    }
    return render(request, "dashboard/regions_map.html", context)