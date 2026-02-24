from django.core.management.base import BaseCommand
from django.db import transaction
import pandas as pd
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import date
from django.utils.text import slugify

from accounts.models import (
    Tenant,
    Company,
    CompanyEnrichment,
    User,
    UserCompany,
)

XLS_PATH = "/home/satish/Downloads/1 - US COMPANY DATABASE SAMPLE.xlsx"
DEFAULT_PASSWORD = "test123"


# --------------------------------------------------
# SAFE HELPERS
# --------------------------------------------------
LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "corp", "corporation",
    "company", "co", "plc", "group", "holdings"
}


def is_invalid(val):
    return (
        val is None
        or (isinstance(val, float) and pd.isna(val))
        or str(val).strip().lower() in {"nan", "", "none"}
    )


def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z\s]", " ", name)
    words = [w for w in name.split() if w not in LEGAL_SUFFIXES]
    return " ".join(words).strip()


def tenant_key_from_company(name: str) -> str:
    normalized = normalize_name(name)
    if not normalized:
        return "unknown"
    return " ".join(normalized.split()[:2])


def parse_decimal(val):
    if is_invalid(val):
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    val = str(val)
    if "to" in val.lower():
        return None
    val = re.sub(r"[^\d.]", "", val)
    try:
        return Decimal(val)
    except (InvalidOperation, ValueError):
        return None


def parse_int(val):
    if is_invalid(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_range(val):
    if is_invalid(val):
        return None
    val = str(val).strip()
    return val if "to" in val.lower() else None


# --------------------------------------------------
# COMMAND
# --------------------------------------------------
class Command(BaseCommand):
    help = "FULL CLEAN + SYSTEMATIC XLS IMPORT (tenants, companies, enrichment, users)"

    @transaction.atomic
    def handle(self, *args, **options):

        if not os.path.exists(XLS_PATH):
            raise FileNotFoundError(XLS_PATH)

        self.stdout.write("🧹 Cleaning old data...")

        # DELETE IN SAFE ORDER
        UserCompany.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        CompanyEnrichment.objects.all().delete()
        Company.objects.all().delete()
        Tenant.objects.exclude(name__iexact="Global Tenant").delete()

        self.stdout.write("📊 Reading XLS...")
        df = pd.read_excel(XLS_PATH)

        tenant_cache = {}
        company_count = 0

        for _, row in df.iterrows():

            company_name = row.get("company_name")
            if is_invalid(company_name):
                continue

            # -----------------------------
            # TENANT (DERIVED)
            # -----------------------------
            tenant_key = tenant_key_from_company(company_name)
            tenant = tenant_cache.get(tenant_key)

            if not tenant:
                tenant, _ = Tenant.objects.get_or_create(
                    name=tenant_key.title()
                )
                tenant_cache[tenant_key] = tenant

            # -----------------------------
            # COMPANY
            # -----------------------------
            company, created = Company.objects.get_or_create(
                tenant=tenant,
                name=str(company_name).strip(),
                defaults={
                    "address_line1": row.get("address1"),
                    "address_line2": row.get("address2"),
                    "city": row.get("city"),
                    "state": row.get("state"),
                    "postal_code": (
                        str(row.get("zip5"))
                        if not is_invalid(row.get("zip5")) else None
                    ),
                    "country": "USA",
                    "latitude": parse_decimal(row.get("latitude")),
                    "longitude": parse_decimal(row.get("longitude")),
                    "phone": row.get("telephone"),
                    "website": row.get("website"),
                    "is_active": True,
                }
            )

            if created:
                company_count += 1

            # -----------------------------
            # ENRICHMENT
            # -----------------------------
            sales_val = row.get("sales_volume")
            emp_val = row.get("employee_size")

            CompanyEnrichment.objects.get_or_create(
                company=company,
                defaults={
                    "naics_code": row.get("naics_code"),
                    "naics_description": row.get("naics_description"),
                    "sic4_code": row.get("sic_code"),
                    "sic4_description": row.get("sic_description"),

                    "exact_sales_volume": parse_decimal(sales_val),
                    "sales_range": parse_range(sales_val),

                    "exact_employee_count": parse_int(emp_val),
                    "employee_range": parse_range(emp_val),

                    "year_started": parse_int(row.get("year_started")),
                    "business_type": row.get("business_type"),
                    "location_type": row.get("location_type"),
                    "source": "US Company Database XLS",
                }
            )

            # -----------------------------
            # USER (PLACEHOLDER EMPLOYEE)
            # -----------------------------
            email = f"{slugify(company.name)}@example.com"

            user, created_user = User.objects.get_or_create(
                email=email,
                defaults={
                    "tenant": tenant,
                    "primary_company": company,
                    "first_name": "Primary",
                    "last_name": "Contact",
                    "phone": row.get("contact_telephone"),
                    "birth_date": (
                        date(int(row.get("birth_year")), 1, 1)
                        if not is_invalid(row.get("birth_year")) else None
                    ),
                    "is_active": True,
                }
            )

            if created_user:
                user.set_password(DEFAULT_PASSWORD)
                user.save()

            UserCompany.objects.get_or_create(
                user=user,
                company=company,
                defaults={"is_primary": True}
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ CLEAN IMPORT COMPLETE — {company_count} companies created"
            )
        )