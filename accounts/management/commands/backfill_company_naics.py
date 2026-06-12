"""Link Company.naics_code (FK) from the imported CompanyEnrichment.naics_code
string.

The bulk CSV importer stores the NAICS *code* on CompanyEnrichment but never
links the NaicsCode FK on Company, so the edit-form NAICS picker loads empty
(it needs the FK). This command resolves each enrichment NAICS code to a
NaicsCode row and sets the FK.

Idempotent and safe to re-run. By default it only touches bulk-imported
companies; pass --source all to cover every company.

    python manage.py backfill_company_naics --dry-run   # preview
    python manage.py backfill_company_naics             # apply
"""
from django.core.management.base import BaseCommand

from accounts.models import Company, NaicsCode


class Command(BaseCommand):
    help = "Set Company.naics_code FK from CompanyEnrichment.naics_code."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="bulk_csv_import",
            help="Only companies whose enrichment.source matches this "
                 "(default: bulk_csv_import). Pass 'all' to ignore source.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **opts):
        # Preload the lookup once: {code: NaicsCode}. The table is small.
        code_map = {c.code: c for c in NaicsCode.objects.filter(is_active=True)}

        qs = Company.all_objects.filter(
            naics_code__isnull=True,
            enrichment__naics_code__isnull=False,
        ).select_related("enrichment")
        if opts["source"] != "all":
            qs = qs.filter(enrichment__source=opts["source"])

        to_update = []
        unmatched = {}
        for co in qs:
            raw = (co.enrichment.naics_code or "").strip()
            if not raw:
                continue
            nc = code_map.get(raw)
            if nc is None:
                unmatched[raw] = unmatched.get(raw, 0) + 1
                continue
            co.naics_code = nc
            to_update.append(co)

        if to_update and not opts["dry_run"]:
            Company.all_objects.bulk_update(to_update, ["naics_code"])

        verb = "would link" if opts["dry_run"] else "linked"
        self.stdout.write(self.style.SUCCESS(f"{verb} NAICS FK on {len(to_update)} companies"))
        if unmatched:
            total = sum(unmatched.values())
            self.stdout.write(
                f"{total} companies had a NAICS code not found in the NaicsCode table: "
                f"{dict(sorted(unmatched.items()))}"
            )
