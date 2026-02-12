# AI Ethics Comparator (FastAPI + HTMX)

AI Ethics Comparator is a local-first research tool for measuring how LLMs respond to trolley-style ethical dilemmas across repeated iterations.

## Current Scope

- Paradox type: `trolley` only (2-4 options per scenario)
- Storage format: flat JSON files at `results/<run_id>.json`
- Run ID format: strict `<base>-NNN` (example: `claude-3-opus-001`)
- Legacy migration: startup migrates legacy IDs to strict format

## Stack

- Backend: FastAPI
- Templates: Jinja2
- Interactivity: HTMX
- AI provider: OpenRouter via OpenAI Python SDK
- Reports: WeasyPrint PDF generation

## Quick Start

### 1. Environment

Requirements:

- Python 3.10+
- OpenRouter API key

Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

### 2. Configure

Create `.env` (or copy from `.example.env`):

```env
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
APP_BASE_URL=http://localhost:8000
APP_NAME="AI Ethics Comparator"

# optional overrides
ANALYST_MODEL=provider/model-name
DEFAULT_MODEL=provider/model-name
MAX_ITERATIONS=20
AI_CONCURRENCY_LIMIT=2
AI_MAX_RETRIES=5
AI_RETRY_DELAY=2
AI_CHOICE_INFERENCE_ENABLED=true
```

### 3. Run

```bash
./run_server.sh
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

### 4. Test

```bash
pytest
```

Minimal suite currently covers:

- startup/health behavior
- strict run ID validation
- legacy run ID migration
- safe analysis error rendering (escaped output)

## API Surface

- `GET /` - main UI
- `GET /health` - health + version
- `GET /api/paradoxes` - list paradox definitions
- `GET /api/fragments/paradox-details?paradoxId=...` - HTMX fragment
- `POST /api/query` - execute run
- `GET /api/runs` - list run metadata
- `GET /api/runs/{run_id}` - get full run record
- `POST /api/insight` - generate and optionally persist insight
- `POST /api/runs/{run_id}/analyze` - HTMX analysis render
- `GET /api/runs/{run_id}/pdf` - PDF export

## Run Data Shape

Each run file (`results/<run_id>.json`) includes:

- identity: `runId`, `timestamp`, `modelName`, `paradoxId`, `paradoxType`
- prompt + execution config: `prompt`, optional `systemPrompt`, `iterationCount`, `params`
- option metadata: `options[]`
- per-iteration responses: `responses[]`
- aggregate stats: `summary.options[]` + `summary.undecided`
- optional analysis history: `insights[]`

## Repository Layout

- `main.py` - app factory, startup wiring, routes
- `lib/` - reusable modules (`ai_service`, `query_processor`, `analysis`, `storage`, etc.)
- `templates/` - Jinja2 views/partials
- `static/` - Candlelight theme assets
- `tests/` - pytest suite
- `paradoxes.json` - scenario library
- `results/` - persisted run output (gitignored)
- `CONTRIBUTING.md` - contribution and documentation sync rules

## Security and Operational Notes

- Required secrets validated at startup (`OPENROUTER_API_KEY`, `APP_BASE_URL`, `OPENROUTER_BASE_URL`)
- Strict run ID regex blocks malformed lookup paths
- Markdown rendering escapes raw HTML and strips links/images
- `.env` is gitignored; `.example.env` documents expected variables
