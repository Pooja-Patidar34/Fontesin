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

# Columns to add (or overwrite) with a constant value on every row.
CONSTANT_COLUMNS = {
    "certification_status": "certified",
}

# The edit-form Country dropdown uses ISO codes; normalize the free-text name.
COUNTRY_NAME_TO_CODE = {
    "united states": "US", "usa": "US", "u.s.": "US", "us": "US",
    "united states of america": "US",
}

# The edit-form State dropdown (COUNTRY_STATES["US"]) uses FULL state names;
# the InfoGroup data uses 2-letter abbreviations. Map abbr -> full name so the
# State dropdown can pre-select the value on edit.
US_STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
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
        for col in CONSTANT_COLUMNS:
            if col not in out_fields:
                out_fields.append(col)

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
            for col, val in CONSTANT_COLUMNS.items():
                nr[col] = val
            # Normalize country -> ISO code and US state abbr -> full name so the
            # edit-form Country/State dropdowns can pre-select them.
            country_raw = (nr.get("country") or "").strip()
            code = COUNTRY_NAME_TO_CODE.get(country_raw.lower(), country_raw)
            nr["country"] = code
            state_raw = (nr.get("state") or "").strip()
            if code == "US" and state_raw.upper() in US_STATE_ABBR:
                nr["state"] = US_STATE_ABBR[state_raw.upper()]
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
