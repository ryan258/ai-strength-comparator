# AI Strength Comparator Roadmap

Last updated: February 12, 2026

## Current Focus
The project now targets deterministic capability benchmarking and model strength profiling.

Core delivered baseline:

- local-first FastAPI + HTMX benchmark runner
- deterministic per-capability scoring (`required` / `forbidden` regex)
- multi-capability profile runs (`/api/profile`)
- strongest/weakest area aggregation
- run storage + PDF reporting + analysis workflow

## Near-Term Priorities

### Milestone 1: Capability Test Quality Hardening

- expand benchmark suite with higher-signal tasks per category
- reduce ambiguous prompts and weak regex checks
- add capability-test linting checks (format quality + grading quality)

### Milestone 2: Scoring Robustness

- add richer scoring modes (exact match, numeric tolerance, structured JSON checks)
- track false positives/false negatives from current regex-only grading
- enforce stricter pass-threshold policy by capability type

### Milestone 3: Comparability and Reporting

- add model-vs-model comparison views
- add category trend reporting across historical runs
- improve profile report readability for model selection decisions

### Milestone 4: Reliability and Test Coverage

- add tests for profile endpoint edge cases and capability loader constraints
- add regression tests for capability scoring behavior
- ensure deterministic CI test environment

### Milestone 5: Benchmark Operations

- define governance for capability-test changes (versioning and changelog)
- provide migration notes when benchmark definitions change
- establish baseline suites (fast/dev vs full/deep)

## Non-Goals

- Docker/k8s/Terraform migration
- frontend framework rewrite
- heavy auth/infrastructure expansion
- distributed service decomposition

## Success Criteria

The roadmap is successful when:

1. capability tests are objectively gradable and high signal
2. model profiles are reliable enough for model selection decisions
3. benchmark changes remain versioned, testable, and reproducible
