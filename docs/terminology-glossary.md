# FONTESIN Terminology Glossary

Canonical UI terms for all supported locales. Product tier names (**FREE**, **BASIC**, **PRO**, **ENTERPRISE**, **GLOBAL**) are never translated.

Maintenance scripts:

- `scripts/terminology_glossary.py` — source-of-truth matrix
- `scripts/terminology_standardize.py` — applies canonical terms to `.po` catalogs
- `scripts/terminology_audit.py` — detects remaining inconsistencies

---

## Core business concepts

| Concept | English | French | German | Spanish |
|---------|---------|--------|--------|---------|
| Company | Company | Entreprise | Unternehmen | Empresa |
| Tenant | Tenant | Locataire | Mieter | Inquilino |
| Workspace | Workspace | Espace de travail | Arbeitsbereich | Espacio de trabajo |
| Organization | Organization | Organisation | Organisation | Organización |
| User | User | Utilisateur | Benutzer | Usuario |
| Users | Users | Utilisateurs | Benutzer | Usuarios |
| Member | Member | Membre | Mitglied | Miembro |
| Role | Role | Rôle | Rolle | Rol |
| Roles | Roles | Rôles | Rollen | Roles |
| Permission | Permission | Autorisation | Berechtigung | Permiso |
| Permissions | Permissions | Autorisations | Berechtigungen | Permisos |
| Dashboard | Dashboard | Tableau de bord | Dashboard | Panel |
| Overview | Overview | Aperçu | Überblick | Descripción general |
| Home | Home | Accueil | Startseite | Inicio |
| Certification | Certification | Certification | Zertifizierung | Certificación |
| Subscription | Subscription | Abonnement | Abonnement | Suscripción |
| Subscriptions | Subscriptions | Abonnements | Abonnements | Suscripciones |
| Plan (subscription tier) | Plan | **Forfait** | Plan | Plan |
| Plans (subscription tiers) | Plans | **Forfaits** | Pläne | Planes |
| Notification | Notification | Notification | Benachrichtigung | Notificación |
| Search | Search | Rechercher | Suchen | Buscar |
| Filter | Filter | Filtre | Filter | Filtro |
| Settings | Settings | Paramètres | Einstellungen | Configuración |
| Profile | Profile | Profil | Profil | Perfil |
| Join request | Join Request | Demande d'adhésion | Beitrittsanfrage | Solicitud de acceso |

## Status labels

| Concept | English | French | German | Spanish |
|---------|---------|--------|--------|---------|
| Active | Active | Actif | Aktiv | Activo |
| Pending | Pending | En attente | Ausstehend | Pendiente |
| Approved | Approved | Approuvé | Genehmigt | Aprobado |
| Rejected | Rejected | Rejeté | Abgelehnt | Rechazado |

## Actions (distinct verbs)

| Concept | English | French | German | Spanish |
|---------|---------|--------|--------|---------|
| Save | Save | Enregistrer | Speichern | Guardar |
| Delete | Delete | Supprimer | Löschen | Eliminar |
| Remove | Remove | Retirer | Entfernen | Quitar |
| Cancel | Cancel | Annuler | Abbrechen | Cancelar |
| Close | Close | Fermer | Schließen | Cerrar |

---

## Context separation

These English words have **different** translations depending on meaning:

| English | Context | French | German | Spanish |
|---------|---------|--------|--------|---------|
| Plan | Subscription / billing | Forfait | Plan | Plan |
| Planned | Roadmap / geography | Prévu | Geplant | Planificado |
| Apply | Submit application | Postuler | Bewerben | Solicitar |
| Apply | Apply filter | Appliquer | Anwenden | Aplicar |

---

## Inconsistencies resolved

### French — Plan / Forfait / Abonnement / régime

| Before | After | Scope |
|--------|-------|-------|
| Sidebar **Forfaits**, table **Plan**, title **Historique du régime** | **Forfait** everywhere for subscription tier | billing, dashboard, djangojs |
| **Plan de mise à niveau** | **Mettre à niveau le forfait** | common, billing |
| Body text *le plan*, *ce plan* | *le forfait*, *ce forfait* | all FR catalogs |
| **Abonnement** | unchanged — used for active subscription relationship | billing, sidebar |

### German — Firma vs Unternehmen

| Before | After |
|--------|-------|
| **Firma**, **Firmendetails**, **Firmennamen** | **Unternehmen**, **Unternehmensdetails**, **Unternehmensnamen** |
| **Armaturenbrett** | **Dashboard** |
| **Stornieren** (cancel dialog) | **Abbrechen** |
| **Grunddaten** / **Grundlegende Informationen** | **Grundinformationen** |

### Spanish — Compañía, mistranslations

| Before | After |
|--------|-------|
| **Compañía** | **Empresa** |
| **Ahorrar** (Save) | **Guardar** |
| **Cerca** (Close) | **Cerrar** |
| **Role** (untranslated) | **Rol** |
| **Eliminar** (Remove filter) | **Quitar** |

### French / German / Spanish — navigation

| Before | After |
|--------|-------|
| FR **Maison** | **Accueil** |
| DE **Heim** | **Startseite** |
| ES **Hogar** | **Inicio** |
| FR **Demandes de participation** | **Demandes d'adhésion** |

---

## Product-owner confirmation recommended

| Topic | Question |
|-------|----------|
| **Tenant vs Workspace** | UI uses "Tenant" in admin contexts and "Workspace" in none yet — confirm if both stay or one is deprecated. |
| **Overview vs Dashboard** | Sidebar has both items; confirm they remain separate concepts. |
| **FR Permission menu** | "Autorisations" used for Permissions — confirm vs "Droits d'accès". |
| **DE subscription plan** | Canonical term is **Plan** (common in DE SaaS) — confirm vs **Tarif**. |
| **Legal register IDs** | DE "Firmenhausnummer" → **Handelsregisternummer** — confirm for UK Companies House context. |
| **Member vs User** | Distinct terms kept: company **Member** ≠ platform **User**. |

---

## Files modified

- `locale/fr/LC_MESSAGES/django.po`
- `locale/fr/LC_MESSAGES/djangojs.po`
- `locale/de/LC_MESSAGES/django.po`
- `locale/de/LC_MESSAGES/djangojs.po`
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/djangojs.po`
- `scripts/terminology_glossary.py` (new)
- `scripts/terminology_standardize.py` (expanded)
- `scripts/compile_locales.py` (new)
- `docs/terminology-glossary.md` (this file)
