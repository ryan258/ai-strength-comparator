# CLAUDE.md

Guidance for coding agents working in this repository.

## Project Snapshot

AI Ethics Comparator is a FastAPI + Jinja2 + HTMX application for running repeated LLM evaluations on trolley-style ethical scenarios.

Current behavior:

- Scenario type: `trolley` only
- Options per paradox: 2-4
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
- `ai_service.py` - OpenRouter client + retry/backoff
- `query_processor.py` - iteration orchestration + token parsing + aggregation
- `analysis.py` - analyst prompt compilation + insight parsing
- `storage.py` - run persistence + strict ID migration
- `view_models.py` - template-facing data prep + safe markdown filter
- `reporting.py` - PDF generation
- `paradoxes.py` - paradox loading/validation

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
  "paradoxId": "scenario_id",
  "paradoxType": "trolley",
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
  "options": [
    {"id": 1, "label": "Option 1", "description": "..."},
    {"id": 2, "label": "Option 2", "description": "..."}
  ],
  "summary": {
    "total": 20,
    "options": [
      {"id": 1, "count": 14, "percentage": 70.0},
      {"id": 2, "count": 6, "percentage": 30.0}
    ],
    "undecided": {"count": 0, "percentage": 0.0}
  },
  "responses": [
    {
      "iteration": 1,
      "decisionToken": "{1}",
      "optionId": 1,
      "explanation": "...",
      "raw": "...",
      "timestamp": "2026-01-01T00:00:01+00:00"
    }
  ],
  "insights": [
    {
      "timestamp": "2026-01-01T00:10:00+00:00",
      "analystModel": "provider/analyst",
      "content": {"legacy_text": "..."}
    }
  ]
}
```

## API Endpoints

- `GET /` - full app page
- `GET /health` - health/version metadata
- `GET /api/paradoxes` - all paradoxes
- `GET /api/fragments/paradox-details` - paradox detail partial
- `POST /api/query` - execute run
- `POST /api/insight` - generate insight JSON response
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

Run with `pytest`.

## Implementation Notes

- Preserve app-factory pattern; avoid module-level service globals.
- Keep exception messages safe for UI rendering.
- For new storage migrations, keep operations idempotent.
- Prefer explicit dataclasses/config objects for new integrations.
- Do not hardcode secrets, endpoints, or model IDs in code.
