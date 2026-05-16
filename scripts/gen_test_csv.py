"""
Generate a synthetic CSV for load-testing the bulk company importer.

    python scripts/gen_test_csv.py --rows 1000000 --out /tmp/1m.csv

Each row gets a unique company name (so nothing collides with itself).
Run twice with the same output path to test duplicate handling.
The target tenant is chosen at upload time in the UI, not in the CSV.
"""
import argparse
import csv
import os
import random
import sys
import uuid


HEADER = [
    "name",
    "registration_id", "classification", "entity_type",
    "address_line1", "address_line2", "house_number", "district", "region",
    "city", "state", "postal_code", "country",
    "latitude", "longitude",
    "year_established", "industry_code", "keywords", "employee_count_range",
    "phone", "phone_secondary", "fax", "website", "contact_email",
    "certification_status",
]

CLASSIFICATIONS = ["manufacturing", "it_services", "healthcare", "finance", "retail", "education", "marketing", "industry"]
ENTITY_TYPES = ["inc", "llc", "ltd", "pvt_ltd", "llp", "corp", "gmbh", "ag", "sa", "sarl", "bv", "sole_proprietorship", "partnership", "non_profit", "other"]
EMPLOYEE_RANGES = ["up_to_10", "up_to_50", "up_to_100", "up_to_1000", "over_1000"]
COUNTRIES = ["United States", "United Kingdom", "Germany", "Czech Republic", "United Arab Emirates"]
CITIES = ["London", "Berlin", "Prague", "Dubai", "New York", "Menlo Park", "Manchester", "Munich"]


def make_row(i):
    name = f"TestCo {i:08d} {uuid.uuid4().hex[:6]}"
    return [
        name,
        f"REG-{i:08d}",
        random.choice(CLASSIFICATIONS),
        random.choice(ENTITY_TYPES),
        f"{random.randint(1,999)} Test Street",
        "",
        str(random.randint(1, 999)),
        "",
        "",
        random.choice(CITIES),
        "",
        f"{random.randint(10000, 99999)}",
        random.choice(COUNTRIES),
        f"{random.uniform(-90, 90):.8f}",
        f"{random.uniform(-180, 180):.8f}",
        str(random.randint(1900, 2024)),
        f"{random.randint(10000, 99999)}",
        "test, synthetic",
        random.choice(EMPLOYEE_RANGES),
        f"+1-555-{random.randint(1000, 9999)}",
        "",
        "",
        f"https://test-{i}.example.com",
        f"contact-{i}@example.com",
        "uncertified",
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, required=True, help="number of data rows to generate")
    p.add_argument("--out", required=True, help="output CSV path")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for i in range(args.rows):
            w.writerow(make_row(i))
            if (i + 1) % 100000 == 0:
                print(f"  wrote {i + 1:,} rows", file=sys.stderr)

    size_mb = os.path.getsize(args.out) / (1024 * 1024)
    print(f"Done: {args.rows:,} rows, {size_mb:.1f} MB -> {args.out}")


if __name__ == "__main__":
    main()
