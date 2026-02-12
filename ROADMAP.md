# AI Ethics Comparator Roadmap

Last updated: February 6, 2026

## Current State

The project is operating as a local-first FastAPI + HTMX modular monolith with:

- app-factory startup initialization (`main.py`)
- typed validation at HTTP boundaries (`lib/validation.py`)
- strict run ID enforcement (`<base>-NNN`)
- startup migration for legacy run IDs (`lib/storage.py`)
- trolley-only scenario execution (2-4 options)
- analysis modal + safe error rendering path
- PDF export for stored runs
- minimal pytest suite for startup/run-id/error-safety guarantees

## Recently Completed

- migrated route/service wiring to startup-time dependency initialization
- centralized strict run ID validation around `STRICT_RUN_ID_PATTERN`
- added legacy-ID migration into startup lifecycle
- added escaped analysis error partial (`templates/partials/analysis_error.html`)
- added baseline tests:
  - `tests/test_startup.py`
  - `tests/test_run_id_validation.py`
  - `tests/test_run_id_migration.py`
  - `tests/test_analysis_error_render.py`

## Next Milestones

### Milestone 1: Run ID Hardening

- tighten regex semantics if needed (for example, lowercase-only base or stricter separators)
- add explicit migration policy for any new regex change
- add tests for accepted/rejected edge cases and migration idempotency

### Milestone 2: Test Reliability

- ensure test dependencies are consistently installed in dev workflow
- reduce skip-based behavior in CI/dev by standardizing test environment
- extend coverage for:
  - query execution error mapping
  - insight persistence behavior
  - paradox loading failure path

### Milestone 3: Storage and Lifecycle Hygiene

- decide retention/cleanup policy for migrated legacy files
- document migration observability (what gets logged, what is skipped)
- add optional admin utility for migration audit/reporting

### Milestone 4: Analysis Robustness

- tighten structured insight schema validation
- improve fallback behavior when analyst output is malformed JSON
- add deterministic tests for structured insight parsing branches

### Milestone 5: Documentation Discipline

- keep `README.md` as source-of-truth quickstart
- keep `HANDBOOK.md` user-facing and implementation-accurate
- mark historical planning/review docs as archival snapshots

## Non-Goals (Current)

- no Docker/k8s/Terraform migration
- no React or frontend build pipeline
- no heavy auth infrastructure
- no distributed services split

## Success Criteria

The near-term roadmap is successful when:

1. run ID policy changes are migration-safe and fully tested
2. pytest runs are deterministic in standard dev setup
3. docs and implementation remain synchronized without contradictory claims
