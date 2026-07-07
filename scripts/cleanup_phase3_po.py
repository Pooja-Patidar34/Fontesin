#!/usr/bin/env python3
"""Remove malformed Phase 3 po entries and fill de/es/fr auth translations."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"

# Formal German (Sie) translations for auth namespace
DE: dict[str, str] = {
    "Log In": "Anmelden",
    "Register": "Registrieren",
    "Back to Home": "Zurück zur Startseite",
    "Back to Login": "Zurück zur Anmeldung",
    "Back": "Zurück",
    "Email Address": "E-Mail-Adresse",
    "Password": "Passwort",
    "Email is required.": "E-Mail ist erforderlich.",
    "Enter a valid email address.": "Geben Sie eine gültige E-Mail-Adresse ein.",
    "Password is required.": "Passwort ist erforderlich.",
    "Invalid credentials": "Ungültige Anmeldedaten",
    "Remember me": "Angemeldet bleiben",
    "Forgot password?": "Passwort vergessen?",
    "Sign up free": "Kostenlos registrieren",
    "Don't have an account?": "Noch kein Konto?",
    "Enter your password": "Geben Sie Ihr Passwort ein",
    "Toggle password visibility": "Passwortsichtbarkeit umschalten",
    "Welcome back to the global platform": "Willkommen zurück auf der globalen Plattform",
    "Forgot Password": "Passwort vergessen",
    "Send Verification Code": "Bestätigungscode senden",
    "Reset Password": "Passwort zurücksetzen",
    "Verify Your Code": "Code bestätigen",
    "Verify Code": "Code bestätigen",
    "Verification Code": "Bestätigungscode",
    "Resend": "Erneut senden",
    "New Password": "Neues Passwort",
    "Confirm Password": "Passwort bestätigen",
    "Identity Verification": "Identitätsprüfung",
    "Log Out": "Abmelden",
    "Log in": "Anmelden",
    "FONTESIN – Your password reset code": "FONTESIN – Ihr Code zum Zurücksetzen des Passworts",
    "Your password has been reset successfully. You can now log in.": "Ihr Passwort wurde erfolgreich zurückgesetzt. Sie können sich jetzt anmelden.",
    "If an account with that email exists, we've sent a verification code.": "Wenn ein Konto mit dieser E-Mail existiert, haben wir einen Bestätigungscode gesendet.",
    "Please enter a valid 6-digit code.": "Bitte geben Sie einen gültigen 6-stelligen Code ein.",
    "Invalid or expired code. Please try again.": "Ungültiger oder abgelaufener Code. Bitte versuchen Sie es erneut.",
    "Create Your Account": "Konto erstellen",
    "Basic Info": "Grunddaten",
    "Your Role": "Ihre Rolle",
    "Confirm": "Bestätigen",
    "Continue →": "Weiter →",
    "Select your region": "Region auswählen",
    "Submit for approval": "Zur Genehmigung einreichen",
    "Application Submitted!": "Bewerbung eingereicht!",
    "Application Under Review": "Bewerbung wird geprüft",
    "Back to Login": "Zurück zur Anmeldung",
}

ES: dict[str, str] = {
    "Log In": "Iniciar sesión",
    "Register": "Registrarse",
    "Back to Home": "Volver al inicio",
    "Email is required.": "El correo electrónico es obligatorio.",
    "Invalid credentials": "Credenciales no válidas",
    "Forgot password?": "¿Olvidó su contraseña?",
    "FONTESIN – Your password reset code": "FONTESIN – Su código de restablecimiento de contraseña",
}

FR: dict[str, str] = {
    "Log In": "Se connecter",
    "Register": "S'inscrire",
    "Back to Home": "Retour à l'accueil",
    "Email is required.": "L'adresse e-mail est requise.",
    "Invalid credentials": "Identifiants invalides",
    "Forgot password?": "Mot de passe oublié ?",
    "FONTESIN – Your password reset code": "FONTESIN – Votre code de réinitialisation du mot de passe",
}

LOCALE_MAP = {"de": DE, "es": ES, "fr": FR}


def is_malformed_block(block: str) -> bool:
    if '\\" context \\"' in block:
        return True
    if 'msgid "Application Under Review\\"' in block:
        return True
    if re.search(r'msgid "[^"]*\\" context', block):
        return True
    return False


def clean_po(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", text)
    kept = [blocks[0]]
    removed = 0
    for block in blocks[1:]:
        if is_malformed_block(block):
            removed += 1
            continue
        kept.append(block)
    path.write_text("\n\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return removed


def fill_translations(path: Path, loc: str) -> int:
    if loc == "en":
        return 0
    mapping = LOCALE_MAP.get(loc, {})
    text = path.read_text(encoding="utf-8")
    filled = 0

    def replacer(match: re.Match) -> str:
        nonlocal filled
        block = match.group(0)
        mid = re.search(r'^msgid "(.*)"$', block, re.M)
        if not mid:
            return block
        msgid = mid.group(1).replace('\\"', '"').replace("\\n", "\n")
        if msgid not in mapping:
            return block
        msgstr = mapping[msgid]
        if re.search(r'^msgstr ".+"$', block, re.M):
            return block
        filled += 1
        return re.sub(
            r'^msgstr ""$',
            f'msgstr "{msgstr.replace(chr(34), chr(92)+chr(34))}"',
            block,
            count=1,
            flags=re.M,
        )

    new_text = re.sub(
        r"(?:#:[^\n]*\n)*(?:#, [^\n]*\n)?(?:msgctxt \"[^\"]*\"\n)?msgid \"[^\"]*\"\nmsgstr \"\"",
        replacer,
        text,
        flags=re.M,
    )
    path.write_text(new_text, encoding="utf-8")
    return filled


def main() -> None:
    for loc in ("en", "de", "es", "fr"):
        for domain in ("django", "djangojs"):
            path = LOCALE / loc / "LC_MESSAGES" / f"{domain}.po"
            if not path.exists():
                continue
            removed = clean_po(path)
            filled = fill_translations(path, loc) if domain == "django" else 0
            print(f"{path.relative_to(ROOT)}: removed {removed} malformed, filled {filled}")


if __name__ == "__main__":
    main()
