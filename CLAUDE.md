# CLAUDE.md

Guidance for coding agents working in this repository.

## Project Snapshot

AI Strength Comparator is a FastAPI + Jinja2 + HTMX application for running repeated LLM evaluations on deterministic capability tests.

Current behavior:

- Capability types: `capability` (deterministic scoring)
- Storage: flat JSON files in `results/`
- Strict run IDs: `<base>-NNN`

## Non-Negotiables

- Keep `lib/` portable and framework-agnostic.
- Keep routes thin in `main.py`; core logic belongs in `lib/`.
- No Docker/k8s/terraform additions.
- No React/build-step frontend additions.
- Use Candlelight palette for user-facing UI colors only:
  - `#121212`
  - `#EBD2BE`
  - `#A6ACCD`
  - `#98C379`
  - `#E06C75`

## Quick Commands

```bash
# setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest

# dev server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# tests
pytest
```

## Architecture

### Entry Point

- `main.py`
  - app factory (`create_app`)
  - startup initialization and dependency wiring
  - HTTP/HTMX routes
  - middleware and error mapping

### Arsenal Modules (`lib/`)

- `config.py` - typed app config/env loading
- `validation.py` - Pydantic request validation
- `ai_service.py` - OpenRouter client + retry/backoff + typed exceptions
- `query_processor.py` - iteration orchestration + deterministic scoring + aggregation
- `analysis.py` - analyst prompt compilation + insight parsing
- `storage.py` - run persistence + strict ID migration
- `view_models.py` - template-facing data prep + safe markdown filter
- `reporting.py` - PDF generation
- `capabilities.py` - capability loading/validation
- `strength_profile.py` - strength profile aggregation + category filtering

### UI

- `templates/index.html` and `templates/partials/*.html`
- HTMX endpoints return partials for progressive rendering.

## Startup Lifecycle

At startup (`main.py`):

1. Load `AppConfig` from env + `models.json`.
2. Validate required secrets/URLs.
3. Initialize `AIService`, `RunStorage`, `QueryProcessor`, `AnalysisEngine`, `ReportGenerator`.
4. Run `RunStorage.migrate_legacy_run_ids()`.
5. Attach initialized services to `app.state.services`.

If required env vars are missing, startup fails fast.

## Run ID Rules

Canonical pattern in code: `^[A-Za-z0-9_-]+-\d{3}$`

- valid: `model-001`, `gpt_4-042`
- invalid: `model`, `model-01`, `bad.id-001`

All routes that access a specific run validate this pattern.

## Run Record Schema (Current)

`results/<run_id>.json` contains:

```json
{
  "runId": "model-001",
  "timestamp": "2026-01-01T00:00:00+00:00",
  "modelName": "provider/model",
  "capabilityId": "scenario_id",
  "capabilityType": "capability",
  "prompt": "Rendered prompt text",
  "iterationCount": 20,
  "params": {
    "temperature": 1.0,
    "top_p": 1.0,
    "max_tokens": 1000,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "seed": 123
  },
  "summary": {
    "total": 20,
    "averageScore": 0.9,
    "minScore": 0.5,
    "maxScore": 1.0,
    "passCount": 18,
    "passRate": 90.0,
    "passThreshold": 0.8
  },
  "responses": [
    {
      "iteration": 1,
      "score": 0.9,
      "passed": true,
      "matchedRequired": ["..."],
      "missingRequired": [],
      "matchedForbidden": [],
      "raw": "...",
      "timestamp": "2026-01-01T00:00:01+00:00"
    }
  ],
  "insights": [
    {
      "timestamp": "2026-01-01T00:10:00+00:00",
      "analystModel": "provider/analyst",
      "content": {"executive_summary": "...", "strengths": [], "weaknesses": [], "reliability": [], "recommendations": []}
    }
  ]
}
```

## API Endpoints

- `GET /` - full app page
- `GET /health` - health/version metadata
- `GET /api/capabilities` - all capabilities
- `GET /api/fragments/capability-details` - capability detail partial
- `POST /api/query` - execute run
- `POST /api/profile` - execute strength profile across capabilities
- `GET /api/runs` - list run metadata
- `GET /api/runs/{run_id}` - fetch one run
- `POST /api/runs/{run_id}/analyze` - render analysis partial
- `GET /api/runs/{run_id}/pdf` - download report

## Testing

`tests/` includes a minimal but meaningful baseline:

- startup + version header checks
- strict run ID validation checks
- legacy run ID migration check
- analysis error escaping check
- capability alias/endpoint checks
- strength profile building + filtering
- query processor parsing + scoring

Run with `pytest`.

## Implementation Notes

- Preserve app-factory pattern; avoid module-level service globals.
- Keep exception messages safe for UI rendering.
- For new storage migrations, keep operations idempotent.
- Prefer explicit dataclasses/config objects for new integrations.
- Do not hardcode secrets, endpoints, or model IDs in code.
- Use typed exceptions from `lib/ai_service.py` for error handling in routes.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **ai-strength-comparator** (531 symbols, 1199 relationships, 43 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/ai-strength-comparator/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/ai-strength-comparator/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ai-strength-comparator/clusters` | All functional areas |
| `gitnexus://repo/ai-strength-comparator/processes` | All execution flows |
| `gitnexus://repo/ai-strength-comparator/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
