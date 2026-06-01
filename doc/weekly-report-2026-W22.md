# Weekly Report — Week of May 25–30, 2026 (W22)

**Project:** Fontesin Backend (Django)
**Author:** satish_1097
**Branch:** main
**Period:** Mon 2026-05-25 → Sat 2026-05-30

## At a glance

| Metric | Value |
|---|---|
| Commits | 10 |
| Files changed | 58 |
| Lines added | +3,421 |
| Lines removed | −791 |
| Backend (accounts / FontEsin / billing) | +1,507 / −215 across 27 files |
| Templates | 30 files |
| DB migrations | 4 (0035–0038) |

## Highlights

### 1. Business User → Coordinator upgrade workflow (new feature)
End-to-end request/approval flow shipped:
- New `CoordinatorRequest` model (migration `0035`) with status (pending/approved/declined), target region, motivation, and decline reason.
- New view `accounts/view/coordinator_request.py` (+193) — a Business User submits from their profile; every active Super Admin can Approve or Decline. On approval the user's role flips to Coordinator (primary-company link preserved); on decline the reason is surfaced back to the user.
- New admin dashboard `templates/dashboard/coordinator_requests.html` (+277).
- Notification kinds added: `coordinator_request`, `coordinator_approved`, `coordinator_declined` (notifications utils +194).

### 2. Identity verification enforcement (Veriff / KYC)
- New `RequireIdentityVerificationMiddleware` (+135) bounces any signed-in but unverified user to `/verify/` until Veriff returns `approved` — closing the back-button gap that let new users skip verification and reach plan selection / dashboard.
- New `User` fields `verification_status` + `veriff_session_id` (migration `0036`), with a **grandfather migration** marking all pre-existing accounts as approved so the new gate doesn't lock out current users.
- Runs ahead of plan-selection enforcement: verify → choose plan → dashboard.

### 3. Plan enforcement & data backfill
- `require_plan.py` middleware (+11) for Business User plan gating.
- Migration `0038` backfills Business Users' primary company linkage.
- Migration `0037` adds a "new user" notification kind.

### 4. Regions
- New `accounts/view/regions.py` (+52) and `templates/regions/coming_soon.html` (+78).
- Region landing pages refactored: US, DE, CZ, AE, JP, plus `worldmap.html`.

### 5. UI overhaul
Large template work across the dashboard:
- `users.html` (+544) — major rework.
- `companies.html` (+246), `plans.html` (+140), new `_commissions_panel.html` partial (+149) with `commissions.html` simplified.
- `base.html` navigation (+190), `consultant_users.html`, `partnerships.html`, `_company_row.html`.

### 6. Billing / invoicing
- Invoice template and `billing/views.py` updates (+39); `website/invoice.html` refresh.

## Commit log

| Date | Hash | Message |
|---|---|---|
| 05-30 | f9d7a6d | all bugs fixed |
| 05-27 | 8b12ba4 | UI changes |
| 05-26 | f8d7735 | invoice updated |
| 05-26 | 0d10fb3 | new added |
| 05-26 | ac56626 | pop up fixed |
| 05-26 | 0062da2 | new certification fixes |
| 05-25 | 0baf04d | added new bugs fixed |
| 05-25 | 1df3120 | new changes |
| 05-25 | 4b57c9d | gitignore |
| 05-25 | 99227d0 | new fixes |

## Notes / follow-ups
- Commit messages this week were terse ("all bugs fixed", "new changes") — substance above was reconstructed from the actual diffs. Consider more descriptive messages for traceability.
- New middleware ordering (verification → plan) and the grandfather migration are deploy-sensitive; confirm migration order on production rollout.
