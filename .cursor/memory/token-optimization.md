# Token Optimization

Guidelines to reduce AI token usage and avoid redundant repository work.

---

## How to Scope Prompts

1. State the **current phase** and **target file list** only.
2. Reference exemplars by path (e.g. "match `templates/auth/login.html`").
3. One module manifest per session (~5–15 files).
4. Never attach `companies.html` + `users.html` in the same session (~3400 lines combined).

---

## How to Avoid Repository-Wide Scans

| Instead of | Use |
|------------|-----|
| Full-repo semantic search | [repository-map.md](repository-map.md) module paths |
| Re-reading all templates | [do-not-revisit.md](do-not-revisit.md) skip list |
| Whole-repo `makemessages` | Per-phase extraction or `scripts/sync_phaseN_po.py` |
| Re-explaining architecture | [architecture-decisions.md](architecture-decisions.md) |
| New implementation plans | [current-phase.md](current-phase.md) + [implementation-patterns.md](implementation-patterns.md) |

**Phase grep gates** (not full-repo):
```bash
# Example Phase 7 end gate
rg "appConfirm\(" templates/dashboard/ --glob "!*join_requests*" ...
rg -L "{% trans %}" templates/profile/profile.html
```

---

## How to Use repository-map.md

1. Open [repository-map.md](repository-map.md).
2. Find the module for the current phase (e.g. Dashboard remainder).
3. Load **only** listed Templates, Views, Forms, JS paths.
4. Cross-check [do-not-revisit.md](do-not-revisit.md) — skip completed modules.

---

## How to Use current-phase.md

1. Read **Objective** and **Target Files** — this is the session manifest.
2. Respect **In Scope** / **Out of Scope** boundaries.
3. On completion, update exit criteria checkboxes and advance phase in memory files.

---

## How to Continue Without Re-Planning

1. Read [onboarding.md](onboarding.md) (mandatory start).
2. Execute [current-phase.md](current-phase.md) target files.
3. Apply patterns from [implementation-patterns.md](implementation-patterns.md).
4. Run `python manage.py check`.
5. Update `completed-work.md`, `current-phase.md`, `do-not-revisit.md`, `project-overview.md`.
6. **Do not** create new `.cursor/multilingual-*.md` plans.

---

## Standard Prompt Template (Future Phases)

Copy and fill for each session:

```
Continue FONTESIN i18n implementation.

START: Read .cursor/memory/onboarding.md and follow it.

Phase: [N] — [name from current-phase.md]
Objective: [from current-phase.md]

Target files ONLY:
- [path 1]
- [path 2]
- ...

Patterns: Follow .cursor/memory/implementation-patterns.md
Exemplar: [one completed similar file]

Do NOT:
- Scan or modify files in .cursor/memory/do-not-revisit.md
- Change architecture in .cursor/memory/architecture-decisions.md
- Create new planning documents

Exit criteria:
- [from current-phase.md]

After completion: Update .cursor/memory/completed-work.md, current-phase.md,
do-not-revisit.md, and project-overview.md.
```

---

## Estimated Savings

~60–70% token reduction vs. whole-codebase sessions by scoping to module manifests and grep gates.
