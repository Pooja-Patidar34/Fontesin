#!/usr/bin/env python3
"""Extract Phase 3 auth strings and build phase3_auth_translations.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Machine translations for de/es/fr (formal tone for de)
MT = {
    "de": {
        "Email is required.": "E-Mail ist erforderlich.",
        "Enter a valid email address.": "Geben Sie eine gültige E-Mail-Adresse ein.",
        "Password is required.": "Passwort ist erforderlich.",
        "Invalid credentials": "Ungültige Anmeldedaten",
        "Log In": "Anmelden",
        "Register": "Registrieren",
        "Forgot password?": "Passwort vergessen?",
        "FONTESIN – Your password reset code": "FONTESIN – Ihr Code zum Zurücksetzen des Passworts",
    },
    "es": {
        "Email is required.": "El correo electrónico es obligatorio.",
        "Enter a valid email address.": "Introduzca una dirección de correo válida.",
        "Password is required.": "La contraseña es obligatoria.",
        "Invalid credentials": "Credenciales no válidas",
        "Log In": "Iniciar sesión",
        "Register": "Registrarse",
        "Forgot password?": "¿Olvidó su contraseña?",
        "FONTESIN – Your password reset code": "FONTESIN – Su código de restablecimiento de contraseña",
    },
    "fr": {
        "Email is required.": "L'adresse e-mail est requise.",
        "Enter a valid email address.": "Saisissez une adresse e-mail valide.",
        "Password is required.": "Le mot de passe est requis.",
        "Invalid credentials": "Identifiants invalides",
        "Log In": "Se connecter",
        "Register": "S'inscrire",
        "Forgot password?": "Mot de passe oublié ?",
        "FONTESIN – Your password reset code": "FONTESIN – Votre code de réinitialisation du mot de passe",
    },
}


def mt(msgid: str) -> dict[str, str]:
    return {loc: MT.get(loc, {}).get(msgid, "") for loc in ("de", "es", "fr")}


def add(items: list, msgid: str, context: str | None = None, refs: list[str] | None = None, **kw):
    items.append({
        "msgid": msgid,
        "context": context,
        "references": refs or [],
        "translations": kw.get("translations") or mt(msgid),
    })


def extract_templates() -> list[dict]:
    items: list[dict] = []
    pat_trans = re.compile(
        r"""\{%\s*trans\s+["'](.+?)["']\s+context\s+["']([^'"]+)["']\s*%\}""",
        re.S,
    )
    for path in sorted((ROOT / "templates" / "auth").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        ref = str(path.relative_to(ROOT)).replace("\\", "/")
        for m in pat_trans.finditer(text):
            add(items, m.group(1), context=m.group(2), refs=[ref])
    # blocktrans trimmed (single-line msgids only)
    pat_block = re.compile(
        r"""\{%\s*blocktrans(?:\s+[^%]+)?\s*%\}\s*(.+?)\s*\{%\s*endblocktrans\s*%\}""",
        re.S,
    )
    for path in sorted((ROOT / "templates" / "auth").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        ref = str(path.relative_to(ROOT)).replace("\\", "/")
        for m in pat_block.finditer(text):
            raw = re.sub(r"<[^>]+>", "", m.group(1))
            raw = re.sub(r"\{\{[^}]+\}\}", "%(var)s", raw)
            raw = re.sub(r"\s+", " ", raw).strip()
            if raw and len(raw) < 300:
                ctx_m = re.search(r'context\s+["\']([^"\']+)["\']', m.group(0))
                add(items, raw, context=ctx_m.group(1) if ctx_m else None, refs=[ref])
    return items


def extract_email_templates() -> list[dict]:
    items: list[dict] = []
    for path in (ROOT / "templates" / "email").glob("*"):
        text = path.read_text(encoding="utf-8")
        ref = str(path.relative_to(ROOT)).replace("\\", "/")
        for m in re.finditer(
            r"""\{%\s*trans\s+['"](.+?)['"]\s+context\s+['"]([^'"]+)['"]\s*%\}""", text
        ):
            add(items, m.group(1), context=m.group(2), refs=[ref])
    return items


def extract_auth_py() -> list[dict]:
    items: list[dict] = []
    text = (ROOT / "accounts" / "view" / "auth.py").read_text(encoding="utf-8")
    ref = "accounts/view/auth.py"
    for m in re.finditer(r'''_\(\s*["'](.+?)["']\s*\)''', text):
        add(items, m.group(1), refs=[ref])
    for m in re.finditer(r'''_\(\s*["'](.+?)["']\s*\)\s*%''', text):
        add(items, m.group(1), refs=[ref])
    add(items, "If an account with that email exists, we've sent a verification code.", refs=[ref])
    return items


def extract_mailer() -> list[dict]:
    items: list[dict] = []
    text = (ROOT / "accounts" / "utils" / "mailer.py").read_text(encoding="utf-8")
    ref = "accounts/utils/mailer.py"
    for m in re.finditer(r'''_\(\s*["'](.+?)["']\s*\)''', text):
        add(items, m.group(1), refs=[ref])
    return items


def extract_djangojs() -> list[dict]:
    items: list[dict] = []
    text = (ROOT / "FontEsin" / "static" / "js" / "djangojs-catalog.js").read_text(encoding="utf-8")
    ref = "FontEsin/static/js/djangojs-catalog.js"
    for m in re.finditer(r"""gettext\(['"](.+?)['"]\)""", text):
        msgid = m.group(1)
        if "verify_otp" in msgid or "Resend" in msgid:
            pass
        add(items, msgid, refs=[ref])
    # verify_otp template-injected strings
    votp = ROOT / "templates" / "auth" / "verify_otp.html"
    if votp.exists():
        t = votp.read_text(encoding="utf-8")
        for m in re.finditer(r'RESEND_\w+\s*=\s*"\{% filter escapejs %\}\{% trans [\'"](.+?)[\'"]', t):
            add(items, m.group(1), context="auth.verify_otp", refs=[str(votp.relative_to(ROOT))])
    return items


def dedupe(items: list[dict]) -> list[dict]:
    seen: set[tuple[str | None, str]] = set()
    out: list[dict] = []
    for item in items:
        key = (item.get("context"), item["msgid"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main() -> None:
    django_items = dedupe(
        extract_templates()
        + extract_email_templates()
        + extract_auth_py()
        + extract_mailer()
    )
    djangojs_items = dedupe(extract_djangojs())
    out = {"django": django_items, "djangojs": djangojs_items}
    path = Path(__file__).with_name("phase3_auth_translations.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(django_items)} django + {len(djangojs_items)} djangojs entries to {path.name}")


if __name__ == "__main__":
    main()
