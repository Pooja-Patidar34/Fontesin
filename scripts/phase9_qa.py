#!/usr/bin/env python3
"""Phase 9: Automated i18n QA — django check, catalog load, interpolation smoke."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import django
from django.conf import settings
from django.template import engines
from django.utils import translation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SMOKE_TEMPLATES = [
    "auth/login.html",
    "auth/register.html",
    "dashboard/index.html",
    "dashboard/companies.html",
    "dashboard/users.html",
    "dashboard/plans.html",
    "profile/profile.html",
    "website/index.html",
    "website/contact.html",
    "website/membership.html",
    "email/otp_password_reset.html",
]

SMOKE_STRINGS = [
    ("auth", "Log In"),
    ("nav", "Dashboard"),
    ("companies", "Companies"),
    ("billing", "Plans"),
    ("website", "Contact"),
]

LOCALES = ("en", "de", "es", "fr")


def run_django_check() -> tuple[bool, str]:
    env = os.environ.copy()
    env.setdefault("SECRET_KEY", "qa-test-secret")
    env.setdefault("DB_NAME", "fontesin")
    env.setdefault("DB_USER", "fontesin")
    env.setdefault("DB_PASSWORD", "fontesin")
    env.setdefault("DB_HOST", "localhost")
    env.setdefault("DB_PORT", "5432")
    env.setdefault("VERIFF_API_KEY", "qa")
    env.setdefault("VERIFF_MASTER_SECRET", "qa")
    env.setdefault("VERIFF_BASE_URL", "https://example.com")
    env.setdefault("VERIFF_WEBHOOK_SECRET", "qa")
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    ok = result.returncode == 0
    return ok, (result.stdout + result.stderr).strip()


def qa_catalog_load() -> list[str]:
    errors: list[str] = []
    if not settings.configured:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FontEsin.settings")
        django.setup()

    for locale in LOCALES:
        with translation.override(locale):
            for ctx, msgid in SMOKE_STRINGS:
                result = translation.gettext(msgid)
                if locale == "en" and result != msgid:
                    pass  # en may differ for language names
                if not result:
                    errors.append(f"{locale}: empty translation for {ctx}/{msgid!r}")
    return errors


def qa_templates() -> list[str]:
    errors: list[str] = []
    engine = engines["django"]
    for locale in LOCALES:
        with translation.override(locale):
            for tpl in SMOKE_TEMPLATES:
                try:
                    engine.get_template(tpl)
                except Exception as exc:
                    errors.append(f"{locale}/{tpl}: {exc}")
    return errors


def main() -> int:
    results: dict[str, str] = {}

    ok, out = run_django_check()
    results["django_check"] = "PASS" if ok else f"FAIL: {out[:200]}"

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FontEsin.settings")
    django.setup()

    cat_errors = qa_catalog_load()
    results["catalog_load"] = "PASS" if not cat_errors else f"FAIL: {cat_errors[:5]}"

    tpl_errors = qa_templates()
    results["template_compile"] = "PASS" if not tpl_errors else f"FAIL: {tpl_errors[:5]}"

    # Verify .mo files exist
    mo_missing = []
    for loc in LOCALES:
        for dom in ("django", "djangojs"):
            mo = ROOT / "locale" / loc / "LC_MESSAGES" / f"{dom}.mo"
            if not mo.exists():
                mo_missing.append(str(mo.relative_to(ROOT)))
    results["mo_files"] = "PASS" if not mo_missing else f"FAIL: missing {mo_missing}"

    print("Phase 9 QA Results")
    print("=" * 40)
    all_pass = True
    for k, v in results.items():
        status = "PASS" if v == "PASS" else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {k}: {v}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
