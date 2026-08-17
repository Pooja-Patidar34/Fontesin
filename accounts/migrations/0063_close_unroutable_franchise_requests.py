"""Close sub-franchise requests that no active franchise can parent.

These rows are the residue of a rule that has since changed: a National /
Regional / Micro request for a territory with no active franchise above it used
to be accepted as a demand signal and routed to the Platform Admin. It can never
be granted — the approval path has nothing to attach the node to and refuses with
"No active franchise covers this territory yet" — so each one sits in the Pending
queue forever while its applicant reads SUBMITTED and waits. Requests like this
are now refused at submit time (accounts.view.franchise.franchise_request_submit),
which stops new ones but leaves the existing rows stuck.

They are REJECTED rather than deleted, with a board_note saying why: the applicant
keeps the row in My Requests and can see the reason, and because REJECTED is not
an open status the company's franchise slot is released — so they can request the
Master Franchise the territory actually needs.

Deliberately no notifications: a migration must not fan out email while the
schema is being applied, and the reason travels with the row.
"""
from django.db import migrations
from django.utils import timezone


# Depth per tier — a parent must sit strictly above its child (accounts.constants
# .FranchiseLevel.RANK). Inlined: a migration must not depend on app code that is
# free to change after this ran.
RANK = {"MASTER": 1, "NATIONAL": 2, "REGIONAL": 3, "MICRO": 4}
OPEN_STATUSES = ["SUBMITTED", "PENDING_REVIEW"]
ACTIVE = "ACTIVE"

NOTE = (
    "Closed automatically: no active franchise covers this territory, so there is "
    "nothing for a sub-franchise to sit under. A Master Franchise for this country "
    "has to exist and be active first — you can request that instead."
)


def _canonical(level, country, region, city, local_area):
    """Reduce a territory to the fields its level actually occupies.

    Mirrors accounts.utils.territory.canonical_territory: a Master is a whole
    country, a National / Regional a state, a Micro a city. A field below the
    level's granularity is informational and must not affect containment.
    """
    country = (country or "").strip().upper()
    region = (region or "").strip().lower()
    city = (city or "").strip().lower()
    local_area = (local_area or "").strip().lower()
    if level == "MASTER":
        return country, "", "", ""
    if level in ("NATIONAL", "REGIONAL"):
        return country, region, "", ""
    return country, region, city, local_area


def _covers(candidate, request_territory, request_rank):
    """True when `candidate` (an active node) can parent the requested territory.

    Same rule as accounts.view.franchise.resolve_parent_node: the candidate sits
    strictly higher in the tree, and every territory field it names matches. A
    field the candidate leaves blank places no constraint at that depth, so a
    Master that names only a country covers everything inside it.
    """
    cand_rank = RANK.get(candidate.franchise_level, 0)
    if cand_rank == 0 or cand_rank >= request_rank:
        return False
    cand = _canonical(
        candidate.franchise_level, candidate.territory_country,
        candidate.territory_region, candidate.territory_city,
        candidate.territory_local_area,
    )
    for cand_field, req_field in zip(cand, request_territory):
        if cand_field and cand_field != req_field:
            return False
    return True


def close_unroutable_requests(apps, schema_editor):
    Tenant = apps.get_model("accounts", "Tenant")
    FranchiseApplication = apps.get_model("accounts", "FranchiseApplication")

    # The historical model carries a plain manager, not the soft-delete one, so
    # removed nodes have to be excluded by hand — a deleted franchise parents
    # nothing.
    active_nodes = list(
        Tenant.objects.filter(
            franchise_level__isnull=False, franchise_status=ACTIVE, is_deleted=False,
        )
    )

    stuck = []
    for application in FranchiseApplication.objects.filter(
        application_status__in=OPEN_STATUSES,
    ).exclude(requested_level="MASTER"):
        rank = RANK.get(application.requested_level, 0)
        if rank == 0:
            continue
        territory = _canonical(
            application.requested_level, application.requested_country,
            application.requested_region, application.requested_city,
            application.requested_local_area,
        )
        if any(_covers(node, territory, rank) for node in active_nodes):
            continue  # a real parent exists; this request is approvable
        stuck.append(application)

    now = timezone.now()
    for application in stuck:
        application.application_status = "REJECTED"
        application.rejected_at = now
        # No rejected_by: the platform closed it, not a person.
        application.board_note = (
            f"{application.board_note}\n\n{NOTE}".strip()
            if application.board_note else NOTE
        )
        application.save(update_fields=[
            "application_status", "rejected_at", "board_note", "updated_at",
        ])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0062_company_certification_requested_at"),
    ]

    operations = [
        # Irreversible by nature: the previous status of each row isn't recorded,
        # and re-opening requests that cannot be approved would recreate the bug.
        migrations.RunPython(close_unroutable_requests, migrations.RunPython.noop),
    ]
