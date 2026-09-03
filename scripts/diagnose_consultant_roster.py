"""Why doesn't a franchise holder see their sub-franchises' consultants?

Run against the environment showing the problem:

    python manage.py shell < scripts/diagnose_consultant_roster.py

Set HOLDER_EMAIL below to the account you are logged in as. Read-only: it
prints, it never writes.

There are two independent reasons the roster comes up short, and they need
different fixes, so this reports on each separately:

  1. TREE      — the sub-franchise nodes are not actually children of the
                 holder's node. Visibility walks Tenant.parent, so a node with
                 the wrong (or a missing) parent is not a descendant and no code
                 change will surface it. This is a DATA fix.
  2. TENANT    — the consultants are found by the subtree walk but dropped by
                 the tenant filter, because they registered in a different
                 tenant from the holder. This is the CODE fix (Sep 2026).
"""
HOLDER_EMAIL = "REPLACE_ME@example.com"

from accounts.constants import ConsultantAssignmentStatus
from accounts.models import ConsultantAssignment, Tenant, User
from accounts.utils.franchise_access import LIVE_STATUSES, owned_franchise_nodes
from accounts.view.franchise import visible_node_ids

holder = User.objects.filter(email__iexact=HOLDER_EMAIL).first()
if holder is None:
    print(f"!! No user with email {HOLDER_EMAIL!r}")
    raise SystemExit

print(f"Holder: {holder.email}  tenant={holder.tenant_id}")

owned = list(owned_franchise_nodes(holder, LIVE_STATUSES))
print(f"\nOwned nodes (scoped to the acting company): {len(owned)}")
for n in owned:
    print(f"  - {n.name} [{n.franchise_level}] status={n.franchise_status} "
          f"parent={n.parent_id} owner_company={n.owner_company_id}")

if not owned:
    print("\n!! No owned nodes resolved. If the holder owns a franchise bought by")
    print("   ANOTHER of their companies, switch to that company first — the")
    print("   roster is scoped to the company you are acting as.")
    raise SystemExit

visible = visible_node_ids(holder)
print(f"\nVisible subtree: {len(visible)} node(s)")
for n in Tenant.objects.filter(id__in=visible).order_by("franchise_level", "name"):
    own = " (owned)" if n.owner_user_id == holder.id else ""
    print(f"  - {n.name} [{n.franchise_level}]{own}")

# ---- 1. TREE ------------------------------------------------------------
# Every live franchise node NOT in the subtree. If the sub-franchises the
# holder expects to see are listed here, their parent link is the problem.
outside = (
    Tenant.objects.filter(franchise_level__isnull=False)
    .exclude(id__in=visible)
    .order_by("franchise_level", "name")
)
print(f"\n[1] TREE — live franchise nodes OUTSIDE the subtree: {outside.count()}")
for n in outside:
    print(f"  - {n.name} [{n.franchise_level}] parent={n.parent_id} "
          f"territory={n.territory_country}/{n.territory_region}/{n.territory_city}")
print("    ^ if the missing Regional/Micro are here, fix their `parent`, not the code.")

# ---- 2. TENANT ----------------------------------------------------------
# Consultants the subtree DOES reach, and whether the tenant filter drops them.
assignments = (
    ConsultantAssignment.objects
    .filter(franchise_node_id__in=visible, status=ConsultantAssignmentStatus.ACTIVE)
    .select_related("consultant_user", "franchise_node")
    .order_by("franchise_node__name")
)
print(f"\n[2] TENANT — active assignments inside the subtree: {assignments.count()}")
dropped = 0
for a in assignments:
    c = a.consultant_user
    same = c.tenant_id == holder.tenant_id
    if not same:
        dropped += 1
    print(f"  - {c.email:<40} under {a.franchise_node.name:<28} "
          f"tenant={'same' if same else 'DIFFERENT -> dropped by the old code'}")

print(f"\nSummary: {assignments.count()} consultant(s) in the subtree, "
      f"{dropped} hidden by the tenant filter.")
if dropped:
    print("  -> the code fix (dropping the tenant pin) surfaces these on deploy.")
if outside.exists():
    print("  -> check the TREE list above for mis-parented sub-franchises.")
