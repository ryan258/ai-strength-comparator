# AI Strength Comparator Roadmap

Last updated: February 13, 2026

## Mission
Build the most trusted local-first capability testing system for answering:

**What is this model reliably good at, where does it fail, and how confident should we be in that conclusion?**

## Strategic Pillars

1. **Signal Quality**
   Capability tests must be high-signal, low-ambiguity, and machine-gradable.
2. **Comparability**
   Results must remain comparable across models, runs, and benchmark revisions.
3. **Reliability**
   Scoring and analysis must be deterministic and test-backed.
4. **Actionability**
   Output must guide model selection, not just display metrics.
5. **No-Bloat Operations**
   Keep stack and architecture minimal: FastAPI + Jinja2 + HTMX, local-first storage.

## Current Baseline (Delivered)

- deterministic capability scoring (`required` / `forbidden` regex + threshold)
- single-test runs (`/api/query`)
- full strength profiles (`/api/profile`)
- cross-model comparisons (`/api/compare`)
- run-level and aggregate insight generation (`/api/runs/{run_id}/analyze`, `/api/insights`)
- local run persistence + strict run IDs + migration logic
- PDF reporting and analyst workflows
- pytest coverage across scoring, storage, profile, and comparison flows

## 12-Month Program

### Phase 1 (Now - 30 Days): Benchmark Integrity Foundation

**Goal:** Make every capability test defensible and auditable.

Deliverables:
- add `scripts/lint_capabilities.py` to enforce schema and quality rules
- require each capability to include: objective, strict output format, and deterministic grading fields
- flag weak regex patterns (overly broad wildcards, no anchors where required)
- add a capability quality score and fail CI on low-quality definitions

Acceptance gates:
- 100% of capabilities pass linter
- 0 duplicate or ambiguous capability IDs
- <5% manual-review disagreement on pass/fail for sampled runs

### Phase 2 (30 - 60 Days): Scoring Engine 2.0

**Goal:** Move beyond regex-only scoring where needed.

Deliverables:
- scorer modes per capability:
  - `regex`
  - `exact_match`
  - `numeric_tolerance`
  - `json_schema`
- deterministic scorer registry in `lib/` with typed config
- per-capability scorer metadata persisted with every run

Acceptance gates:
- at least 50% of non-trivial capabilities use non-regex scorers
- false-positive rate drops by at least 30% on curated adjudication set
- full scorer test suite passes with deterministic fixtures

### Phase 3 (60 - 90 Days): Comparability and Versioning

**Goal:** Ensure longitudinal trust in results.

Deliverables:
- benchmark version and `capabilities.json` hash stored in every run
- comparison mode requires compatible benchmark versions by default
- historical trend view (model + category over time)
- run metadata snapshot includes scoring mode and threshold policy

Acceptance gates:
- 100% of new runs include benchmark hash/version
- incompatible comparisons are blocked or explicitly marked
- trend charts available for all stored models with >=2 runs

### Phase 4 (90 - 120 Days): Reliability and Reproducibility

**Goal:** Make results reproducible on demand.

Deliverables:
- enforce reproducibility profile (seed, params, iteration policy)
- add deterministic replay command for prior run configs
- expand edge-case tests for retries, partial failures, and malformed model outputs
- standardized benchmark suites: `fast`, `standard`, `deep`

Acceptance gates:
- replayed runs produce stable grading outcomes for deterministic tasks
- no unhandled exceptions in stress profile tests
- test suite includes regression fixtures for each scorer mode

### Phase 5 (120 - 180 Days): Insight Quality and Decision Support

**Goal:** Produce insights that are evidence-backed and decision-ready.

Deliverables:
- evidence-linked insights: each recommendation references concrete metrics
- confidence scoring for profile/comparison insights
- disagreement detector between quantitative results and narrative analysis
- report templates for use cases:
  - model selection
  - risk review
  - release gate readiness

Acceptance gates:
- 100% of insight recommendations include supporting evidence fields
- confidence scores shown for aggregate insights
- narrative/metric contradiction rate <10% in QA audits

### Phase 6 (180 - 365 Days): Community-Grade Benchmark Discipline

**Goal:** Operate like a serious benchmark product, still local-first.

Deliverables:
- benchmark changelog with migration guidance for each version
- capability lifecycle states: `draft`, `active`, `deprecated`
- benchmark governance checklist before capability merges
- reproducible benchmark packs export/import (JSON + metadata)

Acceptance gates:
- every benchmark change has versioned changelog entry
- no breaking capability changes without migration notes
- benchmark pack import reproduces identical scoring logic locally

## North-Star Metrics

- **Coverage:** number of high-quality capability tests per domain
- **Determinism:** grading variance on deterministic tasks
- **Comparability:** percentage of runs with compatible benchmark metadata
- **Insight Trust:** evidence-backed recommendation rate
- **Operational Simplicity:** dependency count and local setup time

## Guardrails (Non-Negotiable)

- no Docker/k8s/Terraform migration for core workflow
- no frontend framework rewrite (keep Jinja2 + HTMX)
- no heavy auth stack (maintain simple local/session model)
- no distributed decomposition unless local-first constraints are preserved

## What “Envy of the AI World” Means Here

Not hype. It means this tool becomes known for:

1. rigorous deterministic benchmark design
2. transparent, reproducible scoring
3. high-confidence model ranking and strength profiling
4. fast local operation without platform bloat
