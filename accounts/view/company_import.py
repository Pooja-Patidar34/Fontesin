"""
Platform-admin endpoints for bulk-importing companies from CSV.

Flow:
  POST /companies/import/upload/    -> save file, create job, spawn worker
  GET  /companies/import/<id>/status/   -> JSON progress
  GET  /companies/import/<id>/errors/   -> download errors.csv
  GET  /companies/import/sample.csv     -> downloadable header + example rows

Only superusers may access these endpoints. The target tenant is chosen
at upload time (single dropdown), not encoded in the CSV.
"""
import csv
import io
import os
import subprocess
import sys
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    JsonResponse,
)
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from accounts.models import CompanyImportJob, Tenant


IMPORTS_DIR = os.path.join(settings.BASE_DIR, "imports")
MANAGE_PY = os.path.join(settings.BASE_DIR, "manage.py")

# Mirrors CSV_FIELDS_ALL in the management command. Kept here so the sample
# CSV and the importer stay in lockstep without an import cycle.
SAMPLE_HEADER = [
    "name",
    "registration_id", "classification", "entity_type",
    "address_line1", "address_line2", "house_number", "district", "region",
    "city", "state", "postal_code", "country",
    "latitude", "longitude",
    "year_established", "industry_code", "keywords", "employee_count_range",
    "phone", "phone_secondary", "fax", "website", "contact_email",
    "certification_status",
]
SAMPLE_ROWS = [
    [
        "Acme Industries Ltd", "ACME-001", "it_services", "ltd",
        "221B Baker Street", "", "221B", "Westminster", "Greater London",
        "London", "England", "NW1 6XE", "United Kingdom",
        "51.52376500", "-0.15870600",
        "1985", "62015", "tech, software", "up_to_50",
        "+44-20-7946-0958", "", "", "https://acme.example.com", "hello@acme.example.com",
        "uncertified",
    ],
    [
        "Globex Corporation", "GLOBEX-77", "manufacturing", "corp",
        "1 Hacker Way", "", "1", "", "California",
        "Menlo Park", "CA", "94025", "United States",
        "37.48495300", "-122.14816800",
        "1989", "541512", "energy, consulting", "up_to_1000",
        "+1-650-555-0199", "", "", "https://globex.example.com", "info@globex.example.com",
        "uncertified",
    ],
    [
        "Acme Subsidiary GmbH", "ACME-DE-2", "finance", "gmbh",
        "Hauptstr. 1", "", "1", "Mitte", "Berlin",
        "Berlin", "Berlin", "10115", "Germany",
        "52.52000700", "13.40495400",
        "2010", "70220", "consulting", "up_to_10",
        "+49-30-1234-567", "", "", "https://de.acme.example.com", "de@acme.example.com",
        "uncertified",
    ],
]


def _require_superuser(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied()


def _count_data_rows(path):
    """Stream-count newlines, minus the header. Fast even for 10 GB files."""
    total = 0
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(8 * 1024 * 1024)
            if not buf:
                break
            total += buf.count(b"\n")
    return max(total - 1, 0)


def _import_error(code, error, message, status=400):
    """JSON error with stable machine code, legacy English ``error``, and localized ``message``."""
    return JsonResponse(
        {"code": code, "error": error, "message": message},
        status=status,
    )


@login_required
@require_POST
def company_import_upload(request):
    _require_superuser(request)

    uploaded = request.FILES.get("csv_file")
    if uploaded is None:
        return _import_error(
            "csv_file_required",
            "csv_file is required",
            _("A CSV file is required."),
        )

    if not uploaded.name.lower().endswith(".csv"):
        return _import_error(
            "invalid_file_type",
            "file must be a .csv",
            _("File must be a .csv."),
        )

    tenant_id = (request.POST.get("tenant_id") or "").strip()
    if not tenant_id:
        return _import_error(
            "tenant_id_required",
            "tenant_id is required",
            _("Target tenant is required."),
        )
    try:
        target_tenant = Tenant.all_objects.get(id=tenant_id)
    except (Tenant.DoesNotExist, ValueError):
        return _import_error(
            "unknown_tenant",
            "unknown tenant_id",
            _("Unknown tenant."),
        )

    os.makedirs(IMPORTS_DIR, mode=0o700, exist_ok=True)

    job_id = uuid.uuid4()
    dest_path = os.path.join(IMPORTS_DIR, f"{job_id}.csv")

    # Stream-write to disk so a 10 GB upload never lands in memory.
    with open(dest_path, "wb") as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)

    total_rows = _count_data_rows(dest_path)

    job = CompanyImportJob.objects.create(
        id=job_id,
        created_by=request.user,
        target_tenant=target_tenant,
        filename=uploaded.name[:255],
        file_path=dest_path,
        total_rows=total_rows,
    )

    # Detach the worker so it survives the gunicorn worker (or even nginx).
    # POSIX: start_new_session=True puts it in its own process group; the
    # parent's TERM/HUP won't propagate.
    # Windows: DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP do the equivalent.
    popen_kwargs = dict(
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        cwd=settings.BASE_DIR,
        close_fds=True,
    )
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, MANAGE_PY, "import_companies", str(job.id)],
        **popen_kwargs,
    )

    return JsonResponse({
        "job_id": str(job.id),
        "total_rows": job.total_rows,
        "state": job.state,
    }, status=202)


@login_required
@require_GET
def company_import_status(request, job_id):
    _require_superuser(request)
    try:
        job = CompanyImportJob.objects.get(id=job_id)
    except CompanyImportJob.DoesNotExist:
        raise Http404()

    has_errors = bool(
        job.failed_rows
        and job.error_log_path
        and os.path.exists(job.error_log_path)
    )
    return JsonResponse({
        "job_id": str(job.id),
        "state": job.state,
        "total_rows": job.total_rows,
        "processed_rows": job.processed_rows,
        "inserted_rows": job.inserted_rows,
        "skipped_duplicates": job.skipped_duplicates,
        "failed_rows": job.failed_rows,
        "has_errors": has_errors,
        "error_message": job.error_message,
    })


@login_required
@require_GET
def company_import_errors(request, job_id):
    _require_superuser(request)
    try:
        job = CompanyImportJob.objects.get(id=job_id)
    except CompanyImportJob.DoesNotExist:
        raise Http404()
    if not job.error_log_path or not os.path.exists(job.error_log_path):
        raise Http404()

    response = FileResponse(
        open(job.error_log_path, "rb"),
        content_type="text/csv",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="company-import-errors-{job.id}.csv"'
    )
    return response


@login_required
@require_GET
def company_import_sample(request):
    _require_superuser(request)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(SAMPLE_HEADER)
    for row in SAMPLE_ROWS:
        w.writerow(row)
    response = HttpResponse(buf.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="company-import-sample.csv"'
    )
    return response
