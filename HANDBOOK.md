# AI Ethics Comparator Handbook

Last updated: 2026-02-05

This handbook explains how to use the current FastAPI + HTMX application for trolley-style ethical experiments.

## 1. What This Tool Does

AI Ethics Comparator lets you:

- run repeated model responses on the same paradox scenario
- capture decision tokens (`{1}`, `{2}`, `{3}`, `{4}`)
- aggregate per-option decision rates
- generate analyst summaries from stored run data
- export run reports as PDF

Current scope:

- scenario type: `trolley` only
- paradox options: 2-4
- persistence: local JSON files under `results/`

## 2. Installation

### Prerequisites

- Python 3.10+
- OpenRouter API key

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

Create `.env` with required values:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
APP_BASE_URL=http://localhost:8000
```

Optional:

```env
APP_NAME="AI Ethics Comparator"
DEFAULT_MODEL=provider/model-name
ANALYST_MODEL=provider/model-name
MAX_ITERATIONS=20
AI_CONCURRENCY_LIMIT=2
AI_MAX_RETRIES=5
AI_RETRY_DELAY=2
AI_CHOICE_INFERENCE_ENABLED=true
```

Run the app:

```bash
./run_server.sh
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## 3. UI Walkthrough

The homepage has two main areas:

- `Configuration` panel (left)
- `Results Stream` (bottom)

### Configuration Inputs

- `Paradox Scenario`: choose a scenario from `paradoxes.json`
- `AI Model (OpenRouter ID)`: select preset or type any model ID
- `Persona (Prepended)`: optional text prepended to the prompt
- `Iterations`: number of requests in a run (bounded by `MAX_ITERATIONS`)

### System Status

- shows scenario details for current paradox
- displays busy indicator while a run is executing

## 4. Running an Experiment

1. Select a paradox.
2. Enter model ID.
3. Optionally set a persona.
4. Choose iteration count.
5. Click `Run Experiment`.

The new run appears at the top of `Results Stream`.

## 5. Reading Results

Each run card includes:

- model name and paradox title
- rendered scenario text
- per-option counts and percentages
- undecided count (if the model did not emit a valid token)
- stacked distribution bar
- generated `Run ID`

Each card also has:

- `View Analysis` modal action
- `PDF` export action
- expandable raw JSON dump

## 6. Ethical Analysis Flow

Inside a run modal:

- If an analysis already exists, you can view cached output.
- If none exists, enter analyst model (or keep default) and generate.
- If generation fails, the app renders a safe error partial (escaped message, retry input).
- `Regenerate` forces a fresh analysis.

Insight outputs are stored in the run’s `insights[]` array.

## 7. Run IDs and Migration

Run IDs are strict and validated as:

- pattern: `<base>-NNN`
- regex: `^[A-Za-z0-9_-]+-\d{3}$`

Examples:

- valid: `gpt-4o-001`
- invalid: `gpt-4o`, `gpt-4o-01`, `bad.id-001`

On startup, the app attempts to migrate legacy IDs into strict format and logs how many were migrated.

## 8. Data Model Reference

Every run record (`results/<run_id>.json`) includes:

- `runId`, `timestamp`, `modelName`, `paradoxId`, `paradoxType`
- `prompt`, optional `systemPrompt`
- `iterationCount`, `params`
- `options[]`
- `responses[]`
- `summary.options[]` and `summary.undecided`
- optional `insights[]`

## 9. API Endpoints

- `GET /health`
- `GET /api/paradoxes`
- `GET /api/fragments/paradox-details?paradoxId=...`
- `POST /api/query`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/insight`
- `POST /api/runs/{run_id}/analyze`
- `GET /api/runs/{run_id}/pdf`

## 10. Testing

Minimal pytest suite is included under `tests/`.

Run:

```bash
pytest
```

Coverage focus today:

- startup health and version header
- strict run ID validation
- legacy run ID migration
- escaped analysis error rendering

## 11. Troubleshooting

### App fails at startup

- Confirm required env vars are set:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_BASE_URL`
  - `APP_BASE_URL`

### Query request fails with 401/402/429

- `401`: invalid API key
- `402`: insufficient credits/quota
- `429`: rate-limited

### Analysis fails

- Try another analyst model in the modal retry field
- Check provider availability/credits

### `pytest` reports skips due missing imports

Install runtime dependencies first:

```bash
pip install -r requirements.txt
```

## 12. Research Practices

Recommended baseline:

- use at least 20 iterations for meaningful proportions
- keep persona prompts concise and intentional
- compare runs by changing one variable at a time
- preserve run JSONs for reproducibility and audit

## 13. Security Notes

- `.env` is gitignored; keep real keys out of VCS.
- User-visible markdown is escaped before rendering.
- Links and images are stripped in markdown rendering.
- Run lookup paths are guarded by strict run ID validation.
