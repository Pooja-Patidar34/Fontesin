"""Seed a four-level franchise tree with consultants assigned at every level.

Built to demonstrate downward visibility (spec §7.1): log in as any holder and
both Consultant tabs should show that holder's own consultants PLUS every
consultant assigned beneath them, and nothing from the level above.

    python manage.py seed_franchise_demo
    python manage.py seed_franchise_demo --remove      # delete everything it made

Idempotent: re-running updates the existing rows instead of creating duplicates.
Every object it touches is prefixed `demo-` / `@demo.fontesin` so `--remove`
can find them again and nothing else in the database is affected.

The tree follows FranchiseLevel.RANK — Master > National > Regional > Micro —
because a child node must rank strictly deeper than its parent.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.constants import (
    ConsultantAssignmentStatus,
    ConsultantType,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import (
    Company, ConsultantAssignment, Role, Tenant, User,
)

PASSWORD = "Demo@12345"
EMAIL_DOMAIN = "demo.fontesin"
SLUG_PREFIX = "demo-franchise-"

# level, slug suffix, display name, territory (country, region, city)
TREE = [
    (FranchiseLevel.MASTER,   "master",   "Demo Master Franchise",   ("AO", "", "")),
    (FranchiseLevel.NATIONAL, "national", "Demo National Franchise", ("AO", "", "")),
    (FranchiseLevel.REGIONAL, "regional", "Demo Regional Franchise", ("AO", "Huila", "")),
    (FranchiseLevel.MICRO,    "micro",    "Demo Micro Franchise",    ("AO", "Huila", "Lubango")),
]


class Command(BaseCommand):
    help = "Seed a demo franchise hierarchy with consultants assigned at each level."

    def add_arguments(self, parser):
        parser.add_argument(
            "--remove", action="store_true",
            help="Delete every object this command creates, then exit.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["remove"]:
            return self._remove()

        tenant = self._base_tenant()
        holder_role = self._role("business_user", "Business User")
        consultant_role = self._role("consultant", "Consultant")

        parent = None
        rows = []
        for level, suffix, display, territory in TREE:
            holder = self._holder(
                f"{suffix}.owner@{EMAIL_DOMAIN}", display, tenant, holder_role,
            )
            node = self._node(display, suffix, level, holder, parent, territory)
            consultant = self._consultant(
                f"{suffix}.consultant@{EMAIL_DOMAIN}", suffix, tenant,
                consultant_role, node,
            )
            rows.append((level, holder, consultant, node))
            parent = node

        self._report(rows)

    # -- builders ---------------------------------------------------------

    def _base_tenant(self):
        """The tenant the demo ACCOUNTS live in.

        Deliberately NOT one of the franchise nodes: a franchise node is also a
        Tenant row, but a user's `tenant` is where they registered. Holders and
        consultants sharing this one mirrors production, where everybody
        registers into the platform tenant.
        """
        tenant, _ = Tenant.objects.get_or_create(
            slug=f"{SLUG_PREFIX}base",
            defaults={"name": "Demo Franchise Base"},
        )
        return tenant

    def _role(self, code, name):
        role = Role.objects.filter(code__iexact=code).first()
        if role is None:
            role = Role.objects.create(code=code, name=name, tier_level=1)
        return role

    def _holder(self, email, display, tenant, role):
        """A Business User who owns a franchise node.

        Buying a franchise is additive — the role stays `business_user` and the
        franchise rights come from the node they own. Verified and approved so
        the onboarding middleware lets the dashboard load, and given a company
        because RequireCompanyForBusinessUserMiddleware bounces a company-less
        Business User to the company form.
        """
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email, password=PASSWORD, tenant=tenant, role=role,
            )
        user.first_name = display.replace("Demo ", "").replace(" Franchise", "")
        user.last_name = "Owner"
        user.is_active = True
        user.role = role
        user.tenant = tenant
        user.application_status = "approved"
        user.verification_status = "approved"
        user.set_password(PASSWORD)
        user.save()

        company, _ = Company.objects.get_or_create(
            name=f"{display} Co",
            defaults={"tenant": tenant, "owner_user": user},
        )
        if company.owner_user_id != user.id:
            company.owner_user = user
            company.save(update_fields=["owner_user"])
        return user

    def _node(self, display, suffix, level, holder, parent, territory):
        """One franchise node, parented to the level above it.

        `parent` is what downward visibility walks (Tenant.get_descendant_ids),
        so a node with the wrong parent is invisible to its ancestors no matter
        what its territory says.
        """
        country, region, city = territory
        node, _ = Tenant.objects.get_or_create(
            slug=f"{SLUG_PREFIX}{suffix}", defaults={"name": display},
        )
        node.name = display
        node.franchise_level = level
        node.franchise_status = FranchiseUnitStatus.ACTIVE
        node.owner_user = holder
        node.parent = parent
        node.territory_country = country
        node.territory_region = region
        node.territory_city = city
        node.save()
        return node

    def _consultant(self, email, suffix, tenant, role, node):
        """A consultant, actively assigned to `node`.

        Assignment — not the consultant's own country or tenant — is what puts
        somebody on a franchise's roster.
        """
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email, password=PASSWORD, tenant=tenant, role=role,
            )
        user.first_name = suffix.capitalize()
        user.last_name = "Consultant"
        user.is_active = True
        user.role = role
        user.tenant = tenant
        user.application_status = "approved"
        user.verification_status = "approved"
        user.set_password(PASSWORD)
        user.save()

        assignment = ConsultantAssignment.objects.filter(
            consultant_user=user, franchise_node=node,
        ).first()
        if assignment is None:
            assignment = ConsultantAssignment(
                consultant_user=user, franchise_node=node,
            )
        assignment.status = ConsultantAssignmentStatus.ACTIVE
        assignment.consultant_type = ConsultantType.STANDARD_CONSULTANT
        assignment.territory_country = node.territory_country
        assignment.territory_region = node.territory_region
        assignment.territory_city = node.territory_city
        assignment.assigned_at = timezone.now()
        assignment.save()
        return user

    # -- output -----------------------------------------------------------

    def _report(self, rows):
        w = self.stdout.write
        w("")
        w(self.style.SUCCESS("Demo franchise tree ready (Master > National > Regional > Micro)"))
        w("")
        w(f"  Password for every account below: {PASSWORD}")
        w("")
        w("  Log in as a holder, then open either tab under User Overview -> Users:")
        w("    * Consultants          - the people in your subtree")
        w("    * Consultant Assignment - the assignments, with the assign form")
        w("")

        expected = {
            FranchiseLevel.MASTER: 4,
            FranchiseLevel.NATIONAL: 3,
            FranchiseLevel.REGIONAL: 2,
            FranchiseLevel.MICRO: 1,
        }
        w("  HOLDER LOGIN                              SHOULD SEE")
        w("  " + "-" * 68)
        for level, holder, _consultant, _node in rows:
            count = expected[level]
            names = [s for _l, s, _d, _t in TREE]
            start = names.index(_node.slug.replace(SLUG_PREFIX, ""))
            visible = ", ".join(names[start:])
            w(f"  {holder.email:<40}  {count} ({visible})")
        w("")
        w("  Consultant accounts (one per level):")
        for _level, _holder, consultant, node in rows:
            w(f"    {consultant.email:<40}  assigned to {node.name}")
        w("")
        w("  A Micro owner sees only their own consultant - nothing from the")
        w("  levels above. That upward blindness is the point of the test.")
        w("")
        w("  Remove it all again with: python manage.py seed_franchise_demo --remove")
        w("")

    # -- teardown ---------------------------------------------------------

    def _remove(self):
        nodes = Tenant.objects.filter(slug__startswith=SLUG_PREFIX)
        users = User.objects.filter(email__iendswith=f"@{EMAIL_DOMAIN}")

        assignments = ConsultantAssignment.objects.filter(consultant_user__in=users)
        counts = (assignments.count(), users.count(), nodes.count())

        assignments.delete()
        Company.objects.filter(owner_user__in=users).delete()
        users.delete()
        # Hard-delete the nodes: Tenant.objects is a soft-delete manager, so a
        # plain .delete() would leave the rows (and their unique slugs) behind
        # and the next seed run would collide with them.
        Tenant.all_objects.filter(slug__startswith=SLUG_PREFIX).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Removed {counts[0]} assignment(s), {counts[1]} user(s), {counts[2]} node(s)."
        ))
