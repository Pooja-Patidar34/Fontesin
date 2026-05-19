# Industry code reference data

The `seed_industry_codes` management command reads two CSV files from this
directory. Drop the files in place (filenames are case-sensitive on Linux) and
run:

```
python manage.py seed_industry_codes
```

## Expected files

### `naics_2022.csv`

Source: U.S. Census Bureau (https://www.census.gov/naics/) — the
"2022 NAICS Codes listed numerically (2-Digit through 6-Digit)" download,
saved as CSV.

Delimiter: `,`
Encoding: UTF-8
Header row required.

Columns used:

| Column                  | Purpose                       |
| ----------------------- | ----------------------------- |
| `2022 NAICS US   Code`  | the code (2–6 digits or `XX-YY` range for top-level sectors, e.g. `31-33`) |
| `2022 NAICS US Title`   | short title; trailing `T` (sub-total marker) is stripped |
| `Description`           | long description (optional)   |

### `nace_rev2.csv`

Source: Eurostat NACE Rev.2 official classification.

Delimiter: `;`
Encoding: UTF-8
Header row required.

Columns used:

| Column          | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `Ebene`         | hierarchy level (1=Section … 4=Class, 5/6=detail)|
| `EDV-Code`      | machine-readable code without spaces (e.g. `A0111`) — used as the canonical `code` |
| `Code`          | display code with spaces (e.g. `A 01.11`)        |
| `Titel/Erläuterungstext` | title for top-level rows, description text for sub-rows; the loader keeps the first non-empty row per code as the title |

## Parent inference

Both loaders run in two passes:

1. Insert every row with `parent=None`.
2. Resolve `parent` from the code prefix:
   - **NAICS**: 6-digit → 5-digit → 4-digit → 3-digit → 2-digit. The `31-33`, `44-45`, `48-49` ranges are top-level sectors with no parent.
   - **NACE**: code prefix on the structured code (e.g. `A0111` → parent `A011` → `A01` → `A`). Hierarchy is fully expressed by prefix length.

## Idempotency

The loader uses `update_or_create(code=...)`, so re-running it updates titles
and descriptions in place without creating duplicates.
