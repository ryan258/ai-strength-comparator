# Contributing

This project is intentionally small. Keep changes minimal, typed, and synchronized with docs.

## Scope

- Backend: FastAPI + Python
- UI: Jinja2 + HTMX
- Storage: local JSON files
- Scenario processing: trolley-only

## Documentation Source of Truth

- Quickstart + ops baseline: `README.md`
- Contributor/agent implementation guide: `CLAUDE.md`
- User-facing workflow guide: `HANDBOOK.md`
- Active roadmap and near-term milestones: `ROADMAP.md`
- Dataset/schema summary: `paradoxes.md`
- Historical snapshots (not source of truth): `n-plan.md`, `smells.md`

## Required Doc Sync Rules

Update docs in the same PR when changing any of the following:

- API route behavior or payload shape:
  - update `README.md` API section
  - update `CLAUDE.md` endpoint/schema sections
- Run storage format, migration logic, or run ID semantics:
  - update `README.md`, `CLAUDE.md`, and `HANDBOOK.md`
  - update `ROADMAP.md` if this changes planned follow-up work
- UI workflow or visible controls:
  - update `HANDBOOK.md`
- Paradox schema/count/type assumptions:
  - update `paradoxes.md`
- Project direction or engineering priorities:
  - update `ROADMAP.md`

## Definition of Done (Docs)

Before merging:

1. `README.md` matches current runtime behavior.
2. `HANDBOOK.md` describes only implemented UI/workflows.
3. `CLAUDE.md` matches actual architecture and constraints.
4. `ROADMAP.md` reflects current status (no stale “planned” claims for completed work).
5. Any historical docs are clearly marked archival if they are no longer current.

## Testing Note

Run `pytest` locally for baseline regression checks. If tests are skipped due to missing runtime deps, install from `requirements.txt` first.
