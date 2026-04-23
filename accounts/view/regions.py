import json
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

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