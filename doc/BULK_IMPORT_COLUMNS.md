# Bulk import CSV — column reference

The importer accepts any CSV that has at least these three columns:

- `name`
- `country`
- `state`

Everything else is optional. Columns are routed three ways depending on the name.

## 1. Typed `Company` columns

These map 1:1 to the `Company` table. Values are validated against length/type.

| CSV column | DB type | Notes |
|---|---|---|
| `name` | varchar(255) | **required**, globally unique (active rows) |
| `country` | varchar(100) | **required**, free-text |
| `state` | varchar(100) | **required**, free-text |
| `registration_id` | varchar(100) | globally unique when set |
| `classification` | choice | invalid value → NULL |
| `entity_type` | choice | invalid value → NULL |
| `address_line1` | varchar(255) | |
| `address_line2` | varchar(255) | |
| `house_number` | varchar(30) | |
| `district` | varchar(120) | |
| `region` | varchar(120) | |
| `city` | varchar(150) | |
| `postal_code` | varchar(20) | |
| `latitude` | numeric(10,8) | invalid → row rejected |
| `longitude` | numeric(11,8) | invalid → row rejected |
| `year_established` | integer | invalid → row rejected |
| `industry_code` | varchar(20) | **deprecated** — see "Industry classification" below. Still accepted as free text. |
| `keywords` | varchar(500) | truncated if too long |
| `employee_count_range` | choice | |
| `phone` | varchar(50) | truncated if too long |
| `phone_secondary` | varchar(50) | truncated if too long |
| `fax` | varchar(50) | truncated if too long |
| `website` | varchar(500) | truncated if too long |
| `contact_email` | varchar(254) | |
| `certification_status` | varchar(50) | defaults to `uncertified` |

## 2. Typed `CompanyEnrichment` columns

These map to `accounts_companyenrichment`. The importer creates one
enrichment row per **inserted** company (rows that were skipped as
duplicates do not create enrichment).

| CSV column(s) | DB column | Type |
|---|---|---|
| `naics` | `naics_code` | str(10) |
| `naics_desc` | `naics_description` | str(255) |
| `sic2code` / `sic4code` / `sic6code` | `sic2_code` / `sic4_code` / `sic6_code` | str(10) |
| `sic2desc` / `sic4desc` / `sic6desc` | `sic2_description` / `sic4_description` / `sic6_description` | str(255) |
| `sic_division` | `sic_division` | str(50) |
| `exact_sales_volume` *or* `company_exact_sales` | `exact_sales_volume` | numeric(18,2) |
| `sales_volume` *or* `company_sales` | `sales_range` | str(100) |
| `sales_code` *or* `company_sales_code` | `sales_code` | str(10) |
| `exact_number_of_employees` *or* `number_of_employees` | `exact_employee_count` | integer |
| `employee_range` *or* `employee_size` | `employee_range` | str(100) |
| `employee_code` *or* `company_emp_code` | `employee_code` | str(10) |
| `business_type` | `business_type` | str(100) |
| `location_type` | `location_type` | str(50) |
| `company_year_started` | `year_started` | integer |
| `company_month_started` | `month_started` | integer |
| `franchise` / `chain` / `home_office` | same | bool (Y/N, 1/0, true/false) |
| `MeanHousingCensusArea` | `mean_housing_census_area` | numeric(18,2) |
| `MedianIncomeCensusArea` | `median_income_census_area` | numeric(18,2) |
| `eBizScore` / `eBizDecile` / `eBizPercentile` | `ebiz_score` / `ebiz_decile` / `ebiz_percentile` | str(20) |
| `MonthlyTelcoSpend` / `MonthlyDataSpend` | `monthly_telco_spend` / `monthly_data_spend` | numeric(18,2) |
| `Lines` | `number_of_lines` | integer |
| `number_of_pcs` | `number_of_pcs` | integer |
| `manufacturing_ind` | `is_manufacturing` | bool |
| `subsidiary_ind` | `is_subsidiary` | bool |
| `foreign_company` | `is_foreign_company` | bool |
| `fortune_company` | `fortune_company` | bool |

## 3. Everything else → `Company.extra_data` (JSONB)

Any column the importer doesn't recognize goes into the `extra_data`
JSONB field on the company. Examples that show up in InfoGroup-style
exports:

```
birth_year, orig_title1, orig_title2, contact_telephone,
contact_zip4, contact_zip5, contact_state, contact_city,
contact_address2, contact_address1, gender, ethnicity,
suffix, surname, middle_name, first_name, prefix, contact_name,
NumberOfTenants, MTUID,
ra_*, owner_*, parent_*, prev_*, mail_addr_*, fka_name,
minority_desc_code, residence_address,
zip_centroid_long, zip_centroid_lat, site_status,
square_footage, medicare_provider_code, num_beds,
location_year_started, location_month_started,
store_number, num_units_in_chain, ein,
phone_delete_flag, phone_type1, phone_type2,
unpublished_telephone, business_specialty,
small, government, woman, minority,
state_where_entity_formed, public,
toll_free_number, telephone2 (note: telephone & telephone2 still go to
                              phone/phone_secondary if those columns are
                              ALSO absent — see below),
url, sic8desc, county_name, zip4,
primary_record, phoneable, mailable,
unit_, num, unit_type, postdir, addrsuffix,
streetname, predir, streetnum
```

### Querying `extra_data`

```sql
-- Find companies by EIN
SELECT id, name FROM accounts_company
WHERE extra_data->>'ein' = '12-3456789';

-- Companies with a non-empty SIC 8-digit description
SELECT id, name FROM accounts_company
WHERE extra_data ? 'sic8desc';
```

For high-volume querying, add a GIN index:
```sql
CREATE INDEX accounts_company_extra_data_gin ON accounts_company USING GIN (extra_data);
```

## Header aliases

A few CSV columns are accepted under multiple names because the source
file shape varies. The importer prefers the first non-empty value of
each alias group when populating the typed column.

| Preferred | Aliases also accepted |
|---|---|
| `exact_sales_volume` | `company_exact_sales` |
| `sales_volume` | `company_sales` |
| `sales_code` | `company_sales_code` |
| `exact_number_of_employees` | `number_of_employees` |
| `employee_range` | `employee_size` |
| `employee_code` | `company_emp_code` |

> **Note:** `telephone` / `telephone2` / `url` from InfoGroup-style exports
> are NOT auto-mapped to `phone` / `phone_secondary` / `website` today —
> they go to `extra_data`. If you want that mapping, ask and I'll add it.

## Industry classification (NACE / NAICS)

Migration `0031_industry_codes` introduced two typed FKs on `Company`
alongside the legacy free-text `industry_code` column:

- `Company.nace_code` → `accounts_nacecode` (canonical / default, EU NACE Rev.2)
- `Company.naics_code` → `accounts_naicscode` (parallel US lookup, NAICS 2022)

Both are populated by user pick from the autocomplete endpoints
`/api/industry-codes/nace/?q=…` and `/api/industry-codes/naics/?q=…`,
backed by lookup tables seeded via:

```
python manage.py seed_industry_codes
```

### Deprecation plan for `industry_code`

`Company.industry_code` (free text, varchar(20)) is the legacy field that
the existing forms, dashboard templates (it's literally labelled
"NACE / ISIC Code" in `certifications.html`), and bulk importer write to.
It's kept for now so nothing breaks while the picker rolls out. Drop it
in a focused follow-up once these call sites have migrated to `nace_code`:

- `accounts/forms/company_form.py` (field + `clean_industry_code`)
- `accounts/view/profile.py` (4 references)
- `accounts/view/company.py` (1 reference)
- `accounts/management/commands/import_companies.py` (4 references, including raw SQL)
- `templates/profile/profile.html`, `templates/dashboard/companies.html`, `templates/dashboard/certifications.html`
- `scripts/gen_test_csv.py`

### Namespace note: `Company.naics_code` vs. `CompanyEnrichment.naics_code`

Two different things share the name:

- `company.naics_code` → typed FK to `NaicsCode` (selected via picker)
- `company.enrichment.naics_code` → free-text string from CSV import (denormalized enrichment data, unchanged)

The enrichment row stays a denormalized snapshot of the upstream CSV;
the FK on `Company` is the canonical user-chosen classification.
