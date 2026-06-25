"""Canonical SaaS terminology matrix for FONTESIN (EN / FR / DE / ES).

Product tier names (FREE, BASIC, PRO, ENTERPRISE, GLOBAL) are never translated.
"""
from __future__ import annotations

# Business concept -> canonical term per locale (English is the msgid source language).
GLOSSARY: dict[str, dict[str, str]] = {
    "company": {"en": "Company", "fr": "Entreprise", "de": "Unternehmen", "es": "Empresa"},
    "tenant": {"en": "Tenant", "fr": "Locataire", "de": "Mieter", "es": "Inquilino"},
    "workspace": {"en": "Workspace", "fr": "Espace de travail", "de": "Arbeitsbereich", "es": "Espacio de trabajo"},
    "organization": {"en": "Organization", "fr": "Organisation", "de": "Organisation", "es": "Organización"},
    "user": {"en": "User", "fr": "Utilisateur", "de": "Benutzer", "es": "Usuario"},
    "member": {"en": "Member", "fr": "Membre", "de": "Mitglied", "es": "Miembro"},
    "role": {"en": "Role", "fr": "Rôle", "de": "Rolle", "es": "Rol"},
    "permission": {"en": "Permission", "fr": "Autorisation", "de": "Berechtigung", "es": "Permiso"},
    "dashboard": {"en": "Dashboard", "fr": "Tableau de bord", "de": "Dashboard", "es": "Panel"},
    "overview": {"en": "Overview", "fr": "Aperçu", "de": "Überblick", "es": "Descripción general"},
    "home": {"en": "Home", "fr": "Accueil", "de": "Startseite", "es": "Inicio"},
    "certification": {"en": "Certification", "fr": "Certification", "de": "Zertifizierung", "es": "Certificación"},
    "subscription": {"en": "Subscription", "fr": "Abonnement", "de": "Abonnement", "es": "Suscripción"},
    "plan": {"en": "Plan", "fr": "Forfait", "de": "Plan", "es": "Plan"},
    "notification": {"en": "Notification", "fr": "Notification", "de": "Benachrichtigung", "es": "Notificación"},
    "search": {"en": "Search", "fr": "Rechercher", "de": "Suchen", "es": "Buscar"},
    "filter": {"en": "Filter", "fr": "Filtre", "de": "Filter", "es": "Filtro"},
    "settings": {"en": "Settings", "fr": "Paramètres", "de": "Einstellungen", "es": "Configuración"},
    "profile": {"en": "Profile", "fr": "Profil", "de": "Profil", "es": "Perfil"},
    "active": {"en": "Active", "fr": "Actif", "de": "Aktiv", "es": "Activo"},
    "pending": {"en": "Pending", "fr": "En attente", "de": "Ausstehend", "es": "Pendiente"},
    "approved": {"en": "Approved", "fr": "Approuvé", "de": "Genehmigt", "es": "Aprobado"},
    "rejected": {"en": "Rejected", "fr": "Rejeté", "de": "Abgelehnt", "es": "Rechazado"},
    "save": {"en": "Save", "fr": "Enregistrer", "de": "Speichern", "es": "Guardar"},
    "delete": {"en": "Delete", "fr": "Supprimer", "de": "Löschen", "es": "Eliminar"},
    "remove": {"en": "Remove", "fr": "Retirer", "de": "Entfernen", "es": "Quitar"},
    "cancel": {"en": "Cancel", "fr": "Annuler", "de": "Abbrechen", "es": "Cancelar"},
    "close": {"en": "Close", "fr": "Fermer", "de": "Schließen", "es": "Cerrar"},
    "join_request": {
        "en": "Join Request",
        "fr": "Demande d'adhésion",
        "de": "Beitrittsanfrage",
        "es": "Solicitud de acceso",
    },
}

# Plural forms where grammar requires them (subscription billing UI).
PLURALS: dict[str, dict[str, str]] = {
    "plan": {"en": "Plans", "fr": "Forfaits", "de": "Pläne", "es": "Planes"},
    "subscription": {"en": "Subscriptions", "fr": "Abonnements", "de": "Abonnements", "es": "Suscripciones"},
    "user": {"en": "Users", "fr": "Utilisateurs", "de": "Benutzer", "es": "Usuarios"},
    "role": {"en": "Roles", "fr": "Rôles", "de": "Rollen", "es": "Roles"},
    "permission": {"en": "Permissions", "fr": "Autorisations", "de": "Berechtigungen", "es": "Permisos"},
}

# Contexts where "Plan" means subscription tier (not roadmap / strategy).
PLAN_SUBSCRIPTION_CONTEXTS = frozenset(
    {
        "billing",
        "dashboard",
        "sidebar",
        "website",
        "common",
        "nav",
        "pwa",
        "auth.pending_approval",
        "auth.register",
        "",
    }
)

# msgids that refer to subscription plans even without billing context.
PLAN_SUBSCRIPTION_MSGIDS = frozenset(
    {
        "Plan",
        "Plans",
        "Plan Details",
        "Plan History",
        "Plan Name",
        "Upgrade Plan",
        "Plan & Period",
        "No Active Plan",
        "Activate a Plan",
        "Deactivate Plan?",
        "Choose Plan",
        "Choose Your Plan",
        "Choose Your Membership Plan",
        "Upgrade Your Plan",
        "View Plans & Upgrade",
        "Plan Comparison",
        "Select %(plan_name)s Plan",
        "%(plan_name)s Plan",
        "%(plan_name)s Plan — Full Details",
        "Select {{ plan_name }} Plan",
        "{{ plan_name }} Plan",
        "{{ plan_name }} Plan — Full Details",
        "Your current plan: <strong>No Plan</strong>",
        "Pick an available plan to restore your paid features.",
    }
)

# msgids where "Plan" means roadmap / geography — do NOT use subscription term.
PLAN_STRATEGY_MSGIDS = frozenset(
    {
        "Planned Expansion",
        "Planned · Year 2",
        "Planned · Year 3",
        "Planned – Year",
        "Planned – Year 2",
        "Planned – Year 3",
        "Active & Planned Regions",
    }
)
