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


# InfoGroup data uses NAICS 2017 codes; the NaicsCode lookup is seeded with
# NAICS 2022. These are the 2017->2022 reclassifications seen in the import,
# so the FK can still be linked to the current-edition code.
NAICS_2017_TO_2022 = {
    "315240": "315250",  # Women's/Girls'/Infants' Cut & Sew Apparel Mfg
    "448120": "458110",  # Women's Clothing Stores -> Clothing Retailers
    "453220": "459420",  # Gift, Novelty, and Souvenir Stores -> Retailers
    "453310": "459510",  # Used Merchandise Stores -> Retailers
    "453998": "459990",  # All Other Misc Store Retailers -> Retailers
    "515112": "516110",  # Radio Stations -> Radio Broadcasting Stations
    "519190": "519290",  # All Other Information Services
    "523930": "523940",  # Investment Advice -> Portfolio Mgmt & Investment Advice
    "541712": "541715",  # R&D Physical/Eng/Life Sciences (except Biotech)
}


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
                # Fall back to the 2017->2022 reclassification, then look up again.
                mapped = NAICS_2017_TO_2022.get(raw)
                nc = code_map.get(mapped) if mapped else None
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
