"""Removing a franchise from its holder (spec §9.2 wind-down).

The Platform Admin must be able to take a franchise away from any user or
company, at any level, in any status. Removal is a wind-down of a *subtree*, not
a single row: `Tenant.parent` is PROTECT'd and removal is a soft delete, so
clearing only the target node leaves its sub-franchises alive, still ACTIVE, and
pointing at a row the rest of the app filters out — their territories stay
blocked and their holders keep rights granted by a franchise that no longer
exists.

Everything that activation set up is therefore reversed for the whole subtree in
one transaction: status, consultant rosters, the applications that produced the
nodes, any request still routed to a removed node, and the holders' franchise
role.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.constants import (
    ConsultantAssignmentStatus,
    FranchiseApplicationStatus,
    FranchiseUnitStatus,
)
from accounts.models import (
    AuditLog,
    ConsultantAssignment,
    FranchiseApplication,
    Role,
    Tenant,
)

# Recorded on the applications closed by a removal so the applicant sees why an
# APPROVED request suddenly reads CANCELLED.
REMOVED_BY_ADMIN_NOTE = _("This franchise was removed by the Platform Admin.")


def collect_subtree(node):
    """`node` plus every live descendant, deepest level first.

    Deepest-first keeps the wind-down readable in the audit trail (a child is
    always terminated before its parent) and matches how the tree is displayed.
    """
    ids = node.get_descendant_ids(include_self=True)
    nodes = list(
        Tenant.objects.filter(id__in=ids, franchise_level__isnull=False)
        .select_related("owner_user", "owner_company", "parent")
    )
    depth = {}

    def node_depth(item):
        if item.id in depth:
            return depth[item.id]
        parent = item.parent
        depth[item.id] = 0 if parent is None or parent.id not in ids else node_depth(parent) + 1
        return depth[item.id]

    nodes.sort(key=node_depth, reverse=True)
    return nodes


def _reset_owner_role(owner):
    """Return a legacy `franchise`-role holder to Business User once they hold
    no franchise at all.

    Activation no longer touches the role (see accounts.utils.franchise_access),
    so for anything activated from Jul 2026 on there is nothing to reset and
    this is a no-op. It still runs for accounts promoted by the old flow:
    leaving the franchise role in place after their last node is gone strands
    them — the sidebar hides "Request a Franchise" (the non-holder entry point)
    but shows no franchise management either, so they could never re-apply. A
    consultant or coordinator who happened to also hold a franchise keeps their
    own role.
    """
    if owner is None:
        return False
    still_holds = Tenant.objects.filter(
        owner_user=owner, franchise_level__isnull=False
    ).exists()  # ActiveManager already excludes the rows just soft-deleted
    if still_holds:
        return False
    role_code = (owner.role.code or "").lower() if owner.role else ""
    if role_code != "franchise":
        return False
    business_role = Role.objects.filter(code__iexact="business_user").first()
    if not business_role:
        return False
    owner.role = business_role
    owner.save(update_fields=["role", "updated_at"])
    return True


@transaction.atomic
def remove_franchise(node, *, actor=None, reason="", ip_address=None, notify=True):
    """Remove `node` and its sub-franchises from their holders.

    Returns a summary dict: the removed nodes (deepest first), how many
    consultant assignments were terminated, how many applications were closed,
    and which owners were returned to Business User.
    """
    now = timezone.now()
    nodes = collect_subtree(node)
    node_ids = [n.id for n in nodes]

    # 1. Wind the units down. TERMINATED (not just is_deleted) is what frees the
    #    territory and stops the node counting as a live unit on the rare path
    #    that reads `all_objects`.
    Tenant.all_objects.filter(id__in=node_ids).update(
        franchise_status=FranchiseUnitStatus.TERMINATED,
        terminated_at=now,
        is_active=False,
        is_deleted=True,
        updated_at=now,
    )

    # 2. Nobody consults for a franchise that no longer exists — this also
    #    revokes a Micro owner's self-assignment, which is what carries their
    #    certify / sell-plans rights.
    assignments_closed = (
        ConsultantAssignment.objects.filter(franchise_node_id__in=node_ids)
        .exclude(status=ConsultantAssignmentStatus.TERMINATED)
        .update(status=ConsultantAssignmentStatus.TERMINATED, updated_at=now)
    )

    # 3. The application that produced each node still reads APPROVED in the
    #    applicant's "My Requests"; move it to CANCELLED with the reason.
    applications_closed = FranchiseApplication.objects.filter(
        created_franchise_id__in=node_ids,
        application_status=FranchiseApplicationStatus.APPROVED,
    ).update(
        application_status=FranchiseApplicationStatus.CANCELLED,
        board_note=str(REMOVED_BY_ADMIN_NOTE),
        updated_at=now,
    )

    # 4. A sub-franchise request routed to a removed node can never be reviewed
    #    (its reviewer is gone), so close it too instead of leaving the applicant
    #    waiting forever.
    orphaned_requests_closed = FranchiseApplication.objects.filter(
        parent_franchise_id__in=node_ids,
        application_status__in=list(FranchiseApplicationStatus.OPEN),
    ).update(
        application_status=FranchiseApplicationStatus.CANCELLED,
        board_note=str(REMOVED_BY_ADMIN_NOTE),
        updated_at=now,
    )

    # 5. Return each holder to Business User if this was their last franchise.
    owners_reset = []
    seen_owner_ids = set()
    for item in nodes:
        owner = item.owner_user
        if owner is None or owner.id in seen_owner_ids:
            continue
        seen_owner_ids.add(owner.id)
        if _reset_owner_role(owner):
            owners_reset.append(owner)

    # 6. Audit every removed node, attributing the cascade to the target.
    for item in nodes:
        try:
            AuditLog.objects.create(
                tenant=item,
                actor=actor if actor and actor.is_authenticated else None,
                action="franchise.removed",
                entity_type="franchise_node",
                entity_id=str(item.id),
                metadata={
                    "name": item.name,
                    "level": item.franchise_level,
                    "owner_email": item.owner_user.email if item.owner_user else "",
                    "owner_company": item.owner_company.name if item.owner_company else "",
                    "reason": reason,
                    "removed_with": str(node.id) if item.id != node.id else "",
                },
                ip_address=ip_address,
            )
        except Exception:
            # Auditing must never block the removal itself.
            pass

    if notify:
        try:
            from accounts.utils.notifications import notify_franchise_removed

            for item in nodes:
                notify_franchise_removed(
                    item, removed_by=actor, reason=reason,
                    cascaded=item.id != node.id,
                )
        except Exception:
            pass

    return {
        "nodes": nodes,
        "removed_count": len(nodes),
        "descendant_count": len(nodes) - 1,
        "assignments_closed": assignments_closed,
        "applications_closed": applications_closed,
        "orphaned_requests_closed": orphaned_requests_closed,
        "owners_reset": owners_reset,
    }
