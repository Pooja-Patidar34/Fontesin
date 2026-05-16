"""
Stream a CSV of companies into accounts_company using Postgres COPY.

Invoked as a detached subprocess by the upload view:
    python manage.py import_companies <job_id>

Each row is split three ways:
  - Typed Company columns (name, country, state, phone, ...)
  - Typed CompanyEnrichment columns (naics, sic codes, employee/sales codes, ...)
  - Everything else lands in Company.extra_data (JSONB)

The job row tracks progress; bad rows are written to errors.csv next to the
input file. The input CSV is deleted on success.
"""
import csv
import io
import json
import os
import sys
import time
import traceback
import uuid
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from accounts.constants import (
    CompanyClassificationChoices,
    CompanyEntityTypeChoices,
    EmployeeCountRangeChoices,
)
from accounts.models import CompanyImportJob


BATCH_SIZE = 5000
STAGING_TABLE = "company_import_staging"
ENRICH_STAGING_TABLE = "company_enrichment_import_staging"

# Column order for the Company staging table — must match DDL and INSERT.
STAGING_COLUMNS = [
    "id", "tenant_id", "name", "registration_id", "classification", "entity_type",
    "address_line1", "address_line2", "house_number", "district", "region",
    "city", "state", "postal_code", "country",
    "latitude", "longitude",
    "year_established", "industry_code", "keywords", "employee_count_range",
    "phone", "phone_secondary", "fax", "website", "contact_email",
    "certification_status", "is_active", "is_deleted",
    "extra_data",
    "created_at", "updated_at",
]

# Column order for the CompanyEnrichment staging table.
ENRICH_STAGING_COLUMNS = [
    "id", "company_id",
    "naics_code", "naics_description",
    "sic2_code", "sic4_code", "sic6_code",
    "sic2_description", "sic4_description", "sic6_description",
    "sic_division",
    "exact_sales_volume", "sales_range", "sales_code",
    "exact_employee_count", "employee_range", "employee_code",
    "business_type", "location_type",
    "year_started", "month_started",
    "franchise", "chain", "home_office",
    "median_income_census_area", "mean_housing_census_area",
    "ebiz_score", "ebiz_decile", "ebiz_percentile",
    "monthly_telco_spend", "monthly_data_spend",
    "number_of_lines", "number_of_pcs",
    "is_manufacturing", "is_subsidiary", "is_foreign_company", "fortune_company",
    "source", "imported_at", "updated_at",
]

CSV_FIELDS_REQUIRED = ("name", "country", "state")
CSV_FIELDS_OPTIONAL = (
    "registration_id", "classification", "entity_type",
    "address_line1", "address_line2", "house_number", "district", "region",
    "city", "postal_code",
    "latitude", "longitude",
    "year_established", "industry_code", "keywords", "employee_count_range",
    "phone", "phone_secondary", "fax", "website", "contact_email",
    "certification_status",
)
CSV_FIELDS_ALL = CSV_FIELDS_REQUIRED + CSV_FIELDS_OPTIONAL

# CSV column -> (CompanyEnrichment column, type tag).
# "type tag" tells _build_enrichment_record how to coerce the value.
#  - "str" / ("str", max_len) — keep string, truncate if too long
#  - "int" — integer, None on failure
#  - ("dec", max_digits, decimal_places) — Decimal, None on failure
#  - "bool" — Y/N/1/0/true/false, None on failure
ENRICHMENT_FIELD_MAP = {
    "naics":                    ("naics_code",                ("str", 10)),
    "naics_desc":               ("naics_description",         ("str", 255)),
    "sic2code":                 ("sic2_code",                 ("str", 10)),
    "sic4code":                 ("sic4_code",                 ("str", 10)),
    "sic6code":                 ("sic6_code",                 ("str", 10)),
    "sic2desc":                 ("sic2_description",          ("str", 255)),
    "sic4desc":                 ("sic4_description",          ("str", 255)),
    "sic6desc":                 ("sic6_description",          ("str", 255)),
    "sic_division":             ("sic_division",              ("str", 50)),
    "exact_sales_volume":       ("exact_sales_volume",        ("dec", 18, 2)),
    "company_exact_sales":      ("exact_sales_volume",        ("dec", 18, 2)),  # alias
    "sales_volume":             ("sales_range",               ("str", 100)),
    "company_sales":            ("sales_range",               ("str", 100)),    # alias
    "sales_code":               ("sales_code",                ("str", 10)),
    "company_sales_code":       ("sales_code",                ("str", 10)),     # alias
    "exact_number_of_employees":("exact_employee_count",      "int"),
    "number_of_employees":      ("exact_employee_count",      "int"),           # alias
    "employee_range":           ("employee_range",            ("str", 100)),
    "employee_size":            ("employee_range",            ("str", 100)),    # alias
    "employee_code":            ("employee_code",             ("str", 10)),
    "company_emp_code":         ("employee_code",             ("str", 10)),     # alias
    "business_type":            ("business_type",             ("str", 100)),
    "location_type":            ("location_type",             ("str", 50)),
    "company_year_started":     ("year_started",              "int"),
    "company_month_started":    ("month_started",             "int"),
    "franchise":                ("franchise",                 "bool"),
    "chain":                    ("chain",                     "bool"),
    "home_office":              ("home_office",               "bool"),
    "MedianIncomeCensusArea":   ("median_income_census_area", ("dec", 18, 2)),
    "MeanHousingCensusArea":    ("mean_housing_census_area",  ("dec", 18, 2)),
    "eBizScore":                ("ebiz_score",                ("str", 20)),
    "eBizDecile":               ("ebiz_decile",               ("str", 20)),
    "eBizPercentile":           ("ebiz_percentile",           ("str", 20)),
    "MonthlyTelcoSpend":        ("monthly_telco_spend",       ("dec", 18, 2)),
    "MonthlyDataSpend":         ("monthly_data_spend",        ("dec", 18, 2)),
    "Lines":                    ("number_of_lines",           "int"),
    "number_of_pcs":            ("number_of_pcs",             "int"),
    "manufacturing_ind":        ("is_manufacturing",          "bool"),
    "subsidiary_ind":           ("is_subsidiary",             "bool"),
    "foreign_company":          ("is_foreign_company",        "bool"),
    "fortune_company":          ("fortune_company",           "bool"),
}

# CSV column names that we recognize and route somewhere typed. Anything not
# in this set goes into Company.extra_data verbatim.
KNOWN_CSV_FIELDS = set(CSV_FIELDS_ALL) | set(ENRICHMENT_FIELD_MAP.keys())


def _choice_set(choices_class):
    return {value for value, _label in choices_class.CHOICES}


def _coerce_decimal(raw, max_digits, decimal_places, permissive=False):
    if raw in (None, ""):
        return None
    try:
        d = Decimal(raw)
        quantized = d.quantize(Decimal(10) ** -decimal_places)
        int_digits = len(quantized.as_tuple().digits) - decimal_places
        if int_digits > (max_digits - decimal_places):
            raise InvalidOperation("integer part too large")
        return quantized
    except (InvalidOperation, ValueError):
        if permissive:
            return None
        raise ValueError(f"invalid decimal: {raw!r}")


def _coerce_int(raw, permissive=False):
    if raw in (None, ""):
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        if permissive:
            return None
        raise ValueError(f"invalid integer: {raw!r}")


_TRUE_TOKENS = {"y", "yes", "true", "t", "1"}
_FALSE_TOKENS = {"n", "no", "false", "f", "0"}


def _coerce_bool(raw):
    """Permissive boolean parser — returns None for missing/unrecognized.
    Handles Y/N (InfoGroup style), true/false, 1/0, t/f."""
    if raw in (None, ""):
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _TRUE_TOKENS:
        return True
    if s in _FALSE_TOKENS:
        return False
    return None


def _clean(s, max_len=None):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    if max_len is not None and len(s) > max_len:
        raise ValueError(f"value too long (>{max_len} chars)")
    return s


def _clean_truncate(s, max_len):
    """Like _clean but silently truncates instead of raising. Used for
    enrichment fields where we'd rather store a truncated value than skip."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    return s[:max_len]


def _csv_cell(value):
    """Format a single value for the COPY CSV stream."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "t" if value else "f"
    return str(value)


class RowError(Exception):
    """Raised when a CSV row is unrecoverable and should be logged + skipped."""


class Command(BaseCommand):
    help = "Import companies from a CSV file referenced by a CompanyImportJob row."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=str)

    def handle(self, *args, **options):
        job_id = options["job_id"]
        try:
            job = CompanyImportJob.objects.get(id=job_id)
        except CompanyImportJob.DoesNotExist:
            self.stderr.write(f"job {job_id} not found")
            sys.exit(2)

        if job.state not in (CompanyImportJob.STATE_QUEUED, CompanyImportJob.STATE_RUNNING):
            self.stderr.write(f"job {job_id} already in terminal state {job.state}")
            sys.exit(0)

        self._run(job)

    def _run(self, job):
        job.state = CompanyImportJob.STATE_RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["state", "started_at"])

        error_log_path = job.file_path + ".errors.csv"
        job.error_log_path = error_log_path
        job.save(update_fields=["error_log_path"])

        choice_sets = {
            "classification": _choice_set(CompanyClassificationChoices),
            "entity_type": _choice_set(CompanyEntityTypeChoices),
            "employee_count_range": _choice_set(EmployeeCountRangeChoices),
        }
        tenant_id = str(job.target_tenant_id)

        try:
            self._create_staging_tables()
            with open(error_log_path, "w", newline="", encoding="utf-8") as err_fh:
                err_writer = csv.writer(err_fh)
                err_writer.writerow(["row_number", "reason", "raw_line"])
                self._stream_rows(job, choice_sets, tenant_id, err_writer)
        except Exception:
            job.state = CompanyImportJob.STATE_FAILED
            job.error_message = traceback.format_exc()
            job.finished_at = timezone.now()
            job.save(update_fields=["state", "error_message", "finished_at"])
            raise
        else:
            job.state = CompanyImportJob.STATE_COMPLETED
            job.finished_at = timezone.now()
            job.save(update_fields=["state", "finished_at"])
            try:
                os.remove(job.file_path)
            except OSError:
                pass
        finally:
            self._drop_staging_tables()

    def _create_staging_tables(self):
        ddl = f"""
        DROP TABLE IF EXISTS {STAGING_TABLE};
        CREATE UNLOGGED TABLE {STAGING_TABLE} (
            id uuid,
            tenant_id uuid NOT NULL,
            name varchar(255) NOT NULL,
            registration_id varchar(100),
            classification varchar(50),
            entity_type varchar(30),
            address_line1 varchar(255),
            address_line2 varchar(255),
            house_number varchar(30),
            district varchar(120),
            region varchar(120),
            city varchar(150),
            state varchar(100),
            postal_code varchar(20),
            country varchar(100),
            latitude numeric(10,8),
            longitude numeric(11,8),
            year_established integer,
            industry_code varchar(20),
            keywords varchar(500),
            employee_count_range varchar(20),
            phone varchar(50),
            phone_secondary varchar(50),
            fax varchar(50),
            website varchar(500),
            contact_email varchar(254),
            certification_status varchar(50),
            is_active boolean,
            is_deleted boolean,
            extra_data jsonb,
            created_at timestamptz,
            updated_at timestamptz
        );

        DROP TABLE IF EXISTS {ENRICH_STAGING_TABLE};
        CREATE UNLOGGED TABLE {ENRICH_STAGING_TABLE} (
            id uuid,
            company_id uuid NOT NULL,
            naics_code varchar(10),
            naics_description varchar(255),
            sic2_code varchar(10),
            sic4_code varchar(10),
            sic6_code varchar(10),
            sic2_description varchar(255),
            sic4_description varchar(255),
            sic6_description varchar(255),
            sic_division varchar(50),
            exact_sales_volume numeric(18,2),
            sales_range varchar(100),
            sales_code varchar(10),
            exact_employee_count integer,
            employee_range varchar(100),
            employee_code varchar(10),
            business_type varchar(100),
            location_type varchar(50),
            year_started integer,
            month_started integer,
            franchise boolean,
            chain boolean,
            home_office boolean,
            median_income_census_area numeric(18,2),
            mean_housing_census_area numeric(18,2),
            ebiz_score varchar(20),
            ebiz_decile varchar(20),
            ebiz_percentile varchar(20),
            monthly_telco_spend numeric(18,2),
            monthly_data_spend numeric(18,2),
            number_of_lines integer,
            number_of_pcs integer,
            is_manufacturing boolean,
            is_subsidiary boolean,
            is_foreign_company boolean,
            fortune_company boolean,
            source varchar(100),
            imported_at timestamptz,
            updated_at timestamptz
        );
        """
        with connection.cursor() as cur:
            cur.execute(ddl)

    def _drop_staging_tables(self):
        with connection.cursor() as cur:
            cur.execute(
                f"DROP TABLE IF EXISTS {STAGING_TABLE}; "
                f"DROP TABLE IF EXISTS {ENRICH_STAGING_TABLE};"
            )

    def _stream_rows(self, job, choice_sets, tenant_id, err_writer):
        with open(job.file_path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in CSV_FIELDS_REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise RuntimeError(f"CSV missing required column(s): {', '.join(missing)}")

            # company_batch: list of company-column tuples
            # enrich_batch:  list of enrichment-column tuples (1:1 with company_batch)
            company_batch = []
            enrich_batch = []
            last_progress_save = time.monotonic()

            for row_number, row in enumerate(reader, start=2):
                job.processed_rows += 1
                try:
                    company_rec, enrich_rec = self._build_records(row, choice_sets, tenant_id)
                    company_batch.append(company_rec)
                    enrich_batch.append(enrich_rec)
                except RowError as e:
                    job.failed_rows += 1
                    err_writer.writerow([row_number, str(e), self._raw_line(row)])

                if len(company_batch) >= BATCH_SIZE:
                    self._flush_batch(job, company_batch, enrich_batch)
                    company_batch = []
                    enrich_batch = []

                now = time.monotonic()
                if now - last_progress_save > 2.0:
                    job.save(update_fields=[
                        "processed_rows", "inserted_rows",
                        "skipped_duplicates", "failed_rows",
                    ])
                    last_progress_save = now

            if company_batch:
                self._flush_batch(job, company_batch, enrich_batch)

            job.save(update_fields=[
                "processed_rows", "inserted_rows",
                "skipped_duplicates", "failed_rows",
            ])

    @staticmethod
    def _raw_line(row):
        return ",".join(f"{k}={v!r}" for k, v in row.items() if v)

    def _build_records(self, row, choice_sets, tenant_id):
        """Return (company_tuple, enrichment_tuple). Both share the same id
        (Company.id == Enrichment.company_id) so we can match them up after
        the Company INSERT ... ON CONFLICT DO NOTHING RETURNING."""
        name = _clean(row.get("name"), max_len=255)
        if not name:
            raise RowError("missing name")
        country = _clean(row.get("country"), max_len=100)
        if not country:
            raise RowError("missing country")
        state = _clean(row.get("state"), max_len=100)
        if not state:
            raise RowError("missing state")

        try:
            classification = self._coerce_choice(row.get("classification"), choice_sets["classification"])
            entity_type = self._coerce_choice(row.get("entity_type"), choice_sets["entity_type"])
            employee_count_range = self._coerce_choice(
                row.get("employee_count_range"), choice_sets["employee_count_range"]
            )
            latitude = _coerce_decimal(_clean(row.get("latitude")), 10, 8)
            longitude = _coerce_decimal(_clean(row.get("longitude")), 11, 8)
            year_established = _coerce_int(_clean(row.get("year_established")))
        except ValueError as e:
            raise RowError(str(e))

        # Everything not in the known typed maps → JSONB blob.
        extra = {}
        for k, v in row.items():
            if not k or k in KNOWN_CSV_FIELDS:
                continue
            if v in (None, ""):
                continue
            extra[k] = v.strip() if isinstance(v, str) else v
        extra_data_json = json.dumps(extra, ensure_ascii=False) if extra else None

        company_id = str(uuid.uuid4())
        now = timezone.now().isoformat()

        company_rec = [
            company_id,
            tenant_id,
            name,
            _clean(row.get("registration_id"), max_len=100),
            classification,
            entity_type,
            _clean(row.get("address_line1"), max_len=255),
            _clean(row.get("address_line2"), max_len=255),
            _clean(row.get("house_number"), max_len=30),
            _clean(row.get("district"), max_len=120),
            _clean(row.get("region"), max_len=120),
            _clean(row.get("city"), max_len=150),
            state,
            _clean(row.get("postal_code"), max_len=20),
            country,
            latitude,
            longitude,
            year_established,
            _clean(row.get("industry_code"), max_len=20),
            _clean_truncate(row.get("keywords"), 500),
            employee_count_range,
            _clean_truncate(row.get("phone"), 50),
            _clean_truncate(row.get("phone_secondary"), 50),
            _clean_truncate(row.get("fax"), 50),
            _clean_truncate(row.get("website"), 500),
            _clean(row.get("contact_email"), max_len=254),
            _clean(row.get("certification_status"), max_len=50) or "uncertified",
            True,    # is_active
            False,   # is_deleted
            extra_data_json,
            now,     # created_at
            now,     # updated_at
        ]

        enrich_rec = self._build_enrichment_record(row, company_id, now)
        return company_rec, enrich_rec

    def _build_enrichment_record(self, row, company_id, now):
        # Initialize all enrichment columns to None, then fill from CSV.
        values = {col: None for col in ENRICH_STAGING_COLUMNS}
        values["id"] = str(uuid.uuid4())
        values["company_id"] = company_id
        values["source"] = "bulk_csv_import"
        values["imported_at"] = now
        values["updated_at"] = now

        for csv_col, (model_col, type_tag) in ENRICHMENT_FIELD_MAP.items():
            raw = row.get(csv_col)
            if raw is None or str(raw).strip() == "":
                continue
            try:
                values[model_col] = self._coerce_by_tag(raw, type_tag)
            except ValueError:
                # permissive: drop bad value rather than reject the row
                pass

        return [values[col] for col in ENRICH_STAGING_COLUMNS]

    @staticmethod
    def _coerce_by_tag(raw, type_tag):
        if type_tag == "int":
            return _coerce_int(raw, permissive=True)
        if type_tag == "bool":
            return _coerce_bool(raw)
        if isinstance(type_tag, tuple):
            kind = type_tag[0]
            if kind == "str":
                return _clean_truncate(raw, type_tag[1])
            if kind == "dec":
                return _coerce_decimal(raw, type_tag[1], type_tag[2], permissive=True)
        if type_tag == "str":
            return _clean(raw)
        return None

    @staticmethod
    def _coerce_choice(raw, valid_set):
        value = _clean(raw)
        if value is None:
            return None
        return value if value in valid_set else None

    def _flush_batch(self, job, company_batch, enrich_batch):
        """Two-stage flush:
          1) COPY+INSERT companies (with ON CONFLICT DO NOTHING). RETURNING gives
             us the actual inserted IDs. The rest are duplicates.
          2) COPY+INSERT enrichments — but only for the IDs that actually got
             inserted in step 1. Duplicate-skipped companies leave their
             enrichment staging rows untouched (effectively discarded)."""
        # --- Stage 1: companies ---
        co_buf = io.StringIO()
        writer = csv.writer(co_buf, quoting=csv.QUOTE_MINIMAL)
        for rec in company_batch:
            writer.writerow([_csv_cell(v) for v in rec])
        co_buf.seek(0)
        co_cols = ", ".join(STAGING_COLUMNS)

        # --- Stage 2: enrichments ---
        en_buf = io.StringIO()
        writer = csv.writer(en_buf, quoting=csv.QUOTE_MINIMAL)
        for rec in enrich_batch:
            writer.writerow([_csv_cell(v) for v in rec])
        en_buf.seek(0)
        en_cols = ", ".join(ENRICH_STAGING_COLUMNS)

        with transaction.atomic():
            with connection.cursor() as cur:
                # Stage 1
                cur.execute(f"TRUNCATE {STAGING_TABLE}; TRUNCATE {ENRICH_STAGING_TABLE};")
                cur.copy_expert(
                    f"COPY {STAGING_TABLE} ({co_cols}) FROM STDIN WITH CSV NULL ''",
                    co_buf,
                )
                cur.copy_expert(
                    f"COPY {ENRICH_STAGING_TABLE} ({en_cols}) FROM STDIN WITH CSV NULL ''",
                    en_buf,
                )

                # Insert companies, capture which ones actually landed.
                cur.execute(f"""
                    INSERT INTO accounts_company ({co_cols})
                    SELECT {co_cols} FROM {STAGING_TABLE}
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """)
                inserted_ids = [r[0] for r in cur.fetchall()]
                inserted = len(inserted_ids)

                # Insert enrichments only for the inserted companies.
                if inserted_ids:
                    en_insert_cols = ", ".join(c for c in ENRICH_STAGING_COLUMNS if c != "id")
                    cur.execute(
                        f"""
                        INSERT INTO accounts_companyenrichment (id, {en_insert_cols})
                        SELECT id, {en_insert_cols}
                        FROM {ENRICH_STAGING_TABLE}
                        WHERE company_id = ANY(%s)
                        """,
                        [inserted_ids],
                    )

        job.inserted_rows += inserted
        job.skipped_duplicates += (len(company_batch) - inserted)
