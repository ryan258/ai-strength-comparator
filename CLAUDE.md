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
