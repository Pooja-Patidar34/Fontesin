"""Transform an InfoGroup-style company CSV so more fields land in typed
Company columns that the Company Details view renders.

Changes applied:
  1. Header renames (column -> Company field shown in the view):
       business_specialty   -> keywords          ("Keywords")
       company_year_started -> year_established   ("Year of Establishment")
       ein                  -> registration_id    ("Registration No.")
  2. New `entity_type` column ("Legal Form") derived from `business_type`,
     mapping InfoGroup codes to the Fontesin dropdown choice codes. The
     original `business_type` column is kept (it still feeds enrichment).

Usage:
    python scripts/transform_company_csv.py "<input.csv>" "<output.csv>"
"""
import csv
import sys

# old header -> new header
RENAMES = {
    "business_specialty": "keywords",
    "company_year_started": "year_established",
    "ein": "registration_id",
}

# business_type (InfoGroup, upper-cased) -> entity_type choice code (Legal Form).
# Anything not listed but non-empty falls back to "other".
ENTITY_TYPE_MAP = {
    "CORP": "corp",
    "INC": "inc",
    "LLC": "llc",
    "LLP": "llp",
    "LTD": "ltd",
    "SOLE": "sole_proprietorship",
    "PARTNER": "partnership",
    "NON-PROFIT": "non_profit",
    "NONPROFIT": "non_profit",
    "P ASSOC": "other",
    "PARTNERSHIP": "partnership",
}


def main(inp, outp):
    with open(inp, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        src_fields = reader.fieldnames or []
        out_fields = [RENAMES.get(c, c) for c in src_fields]
        if "entity_type" not in out_fields:
            if "business_type" in out_fields:
                out_fields.insert(out_fields.index("business_type") + 1, "entity_type")
            else:
                out_fields.append("entity_type")

        rows = []
        unmapped = {}
        for r in reader:
            nr = {RENAMES.get(k, k): v for k, v in r.items()}
            bt = (r.get("business_type") or "").strip().upper()
            if bt:
                et = ENTITY_TYPE_MAP.get(bt)
                if et is None:
                    unmapped[bt] = unmapped.get(bt, 0) + 1
                    et = "other"
                nr["entity_type"] = et
            else:
                nr["entity_type"] = ""
            rows.append(nr)

    with open(outp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {len(rows)} rows -> {outp}")
    if unmapped:
        print("business_type values mapped to 'other':", dict(sorted(unmapped.items())))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python transform_company_csv.py <input.csv> [output.csv]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "companies_transformed.csv")
