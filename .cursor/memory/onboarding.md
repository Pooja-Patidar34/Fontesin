# Onboarding — FONTESIN Cursor Sessions

**Mandatory starting point for every new Cursor session.**

---

## Read Order

1. [project-overview.md](project-overview.md) — purpose, stack, phase status
2. [current-phase.md](current-phase.md) — active objective and target files
3. [repository-map.md](repository-map.md) — module paths (scope sessions here)
4. [implementation-patterns.md](implementation-patterns.md) — approved wrap patterns

**Optional when needed:**
- [architecture-decisions.md](architecture-decisions.md) — if touching locale/CI/API
- [do-not-revisit.md](do-not-revisit.md) — skip completed work
- [completed-work.md](completed-work.md) — phase history
- [token-optimization.md](token-optimization.md) — scoping and prompt template

---

## Continue Implementation

1. Work **only** on files listed in `current-phase.md`.
2. Copy patterns from `implementation-patterns.md` and completed exemplars.
3. Run `python manage.py check` after changes.
4. On phase completion, update memory files (not new plans).

---

## Do Not

- Recreate implementation plans (use `current-phase.md`)
- Rediscover architecture (use `architecture-decisions.md`)
- Scan completed modules (use `do-not-revisit.md`)
- Reindex the repository unnecessarily (use `repository-map.md`)
- Full-repo semantic search when a phase manifest exists
- Modify frozen infrastructure without explicit bug-fix ticket

---

## Legacy Reference (read-only)

Older docs retained for historical detail — **do not treat as active state:**

- `.cursor/i18n-project-context.md`
- `.cursor/multilingual-phased-implementation-plan.md`
- `.cursor/multilingual-architecture.md`
- `.cursor/multilingual-task-list.md`

**Active state lives in `.cursor/memory/`.**

---

## Current Action

**i18n v1 complete.** No active phase. For new strings, follow wrap → extract → fill → compile workflow in [completed-work.md](completed-work.md) Phase 9.
