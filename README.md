# AI Strength Comparator (FastAPI + HTMX)

AI Strength Comparator is a local-first benchmarking app that measures what an LLM is reliably good at, where it is weak, and how it performs across capability categories.

See the project direction in `NORTH_STAR.md`.

## North Star
Produce **actionable, deterministic model strength profiles**.

For each model, the app should answer:

- What capability areas are strongest?
- What areas are weakest?
- How reliable are results across repeated runs?

## Benchmark Model
Capability tests are defined in `capabilities.json`.

Each capability test uses deterministic grading:

- `evaluation.required`: regex patterns that must appear
- `evaluation.forbidden`: regex patterns that must not appear
- `evaluation.pass_threshold`: normalized threshold for pass/fail

For creativity and ideation tasks, scoring uses constrained-output novelty proxies (anti-cliche constraints, mechanism + validation requirements).
For research tasks, scoring is source-grounded: outputs must match evidence and required citation format.

### Capability Test Requirements
A strong capability test should be:

1. Single-objective
2. Strict-output (token/number/JSON/CSV/etc.)
3. Deterministically gradable
4. Low-ambiguity
5. Time-stable

## Default Capability Domains
The default suite includes tests for:

- Reasoning
- Logic
- Data Reasoning
- Instruction Following
- Extraction
- Coding
- Creativity
- Novel Ideation
- Research Grounding
- Writing (creative, email, social/viral-style)
- Safety
- Reliability

## Stack
- Backend: FastAPI
- Templates: Jinja2
- Interactivity: HTMX
- AI Provider: OpenRouter via OpenAI Python SDK
- Reports: WeasyPrint PDF generation

## Quick Start

### 1. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

### 2. Configure `.env`

```env
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
APP_BASE_URL=http://localhost:8000
APP_NAME="AI Strength Comparator"

# optional
ANALYST_MODEL=provider/model-name
DEFAULT_MODEL=provider/model-name
MAX_ITERATIONS=20
AI_CONCURRENCY_LIMIT=2
AI_MAX_RETRIES=5
AI_RETRY_DELAY=2
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

## Core Flows

- `Run Selected Test`: execute one capability test repeatedly
- `Run Full Strength Profile`: run all capability tests (or filtered categories)
- `Compare All Models`: run selected capability set across all configured models and rank them
- `View Analysis`: generate model-level strengths/weaknesses commentary
- `Profile/Comparison Insights`: generate aggregate analyst synthesis for profiles and comparisons
- `PDF Export`: download run report

## API Endpoints

- `GET /` - main UI
- `GET /health` - health + version
- `GET /api/capabilities` - list capability tests (canonical)
- `POST /api/query` - execute one capability test run
- `POST /api/profile` - execute full/filtered multi-capability profile
- `POST /api/compare` - execute cross-model comparison over selected capabilities
- `POST /api/insights` - generate aggregate insights for `profile` or `comparison` payloads
- `GET /api/runs` - list stored runs
- `GET /api/runs/{run_id}` - fetch run data
- `POST /api/runs/{run_id}/analyze` - generate strength/weakness analysis
- `GET /api/runs/{run_id}/pdf` - export PDF report

## Run Data Shape (Capability Run)

Stored under `results/<run_id>.json`:

- `runId`, `timestamp`, `modelName`, `capabilityId`, `capabilityType`
- `prompt`, optional `systemPrompt`, `iterationCount`, `params`
- `responses[]` with `raw`, `score`, `passed`, and evidence fields
- `summary.averageScore`, `summary.passRate`, `summary.passCount`
- optional `insights[]`

## Security and Operational Notes

- Secrets are env-only (`OPENROUTER_API_KEY`, `APP_BASE_URL`, `OPENROUTER_BASE_URL`)
- Strict run ID validation is enforced on retrieval routes
- Markdown rendering escapes HTML and strips links/images
- `.env` is gitignored; `.example.env` documents required vars

## How to Extend the Benchmark

1. Add new capability objects in `capabilities.json`.
2. Keep prompts constrained and outputs machine-checkable.
3. Use precise regex patterns in `required` / `forbidden`.
4. Run `pytest` to verify startup/loading behavior.
5. Compare profile output quality before and after additions.
