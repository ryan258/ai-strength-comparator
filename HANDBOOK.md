# AI Strength Comparator Handbook

Last updated: 2026-02-12

This handbook explains how to use the FastAPI + HTMX application for benchmarking LLM capabilities across deterministic capability tests.

## 1. What This Tool Does

AI Strength Comparator lets you:

- run repeated model responses on capability tests
- score capability tests deterministically via regex-based evaluation rules
- aggregate pass rates and score distributions
- build strength profiles across multiple capability categories
- generate analyst summaries from stored run data
- export run reports as PDF

Current scope:

- capability types: `capability` (deterministic scoring)
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
APP_NAME="AI Strength Comparator"
DEFAULT_MODEL=provider/model-name
ANALYST_MODEL=provider/model-name
MAX_ITERATIONS=20
AI_CONCURRENCY_LIMIT=2
AI_MAX_RETRIES=5
AI_RETRY_DELAY=2
```

Run the app:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## 3. Capability Scoring

Each capability test has an `evaluation` block with:

- `required`: regex patterns the response must match
- `forbidden`: regex patterns the response must not match
- `pass_threshold`: minimum score to pass (0.0-1.0)

Score formula: `(matched_required / total_required) - (0.5 * forbidden_hits)`, floored at 0.

## 4. UI Walkthrough

The homepage has two main areas:

- `Configuration` panel (left)
- `Results Stream` (bottom)

### Configuration Inputs

- `Capability Test`: choose a test from `capabilities.json`
- `AI Model (OpenRouter ID)`: select preset or type any model ID
- `Persona (Prepended)`: optional text prepended to the prompt
- `Iterations`: number of requests in a run (bounded by `MAX_ITERATIONS`)

### System Status

- shows capability details for current selection
- displays busy indicator while a run is executing

## 5. Running an Experiment

1. Select a capability test.
2. Enter model ID.
3. Optionally set a persona.
4. Choose iteration count.
5. Click `Run Experiment`.

The new run appears at the top of `Results Stream`.

### Strength Profiles

To benchmark a model across an entire category of capability tests:

1. Select a model.
2. Choose category filters (or leave blank for all).
3. Set iterations per test.
4. Submit a profile request via `POST /api/profile`.

The profile aggregates scores across all matching capability tests and surfaces the model's strongest and weakest areas.

## 6. Reading Results

Each run card displays:

- model name and capability title
- category badge
- average score and pass rate
- pass/fail count
- strength badge (Strong/Developing/Weak)
- stacked pass/fail bar
- run metadata and model configuration

### Common Elements

- generated `Run ID`
- `View Analysis` modal action
- `PDF` export action
- expandable raw JSON dump

## 7. Analysis Flow

Inside a run modal:

- If an analysis already exists, you can view cached output.
- If none exists, enter analyst model (or keep default) and generate.
- If generation fails, the app renders a safe error partial (escaped message, retry input).
- `Regenerate` forces a fresh analysis.

Structured analysis output includes:

- `executive_summary`: high-level assessment
- `strengths`: list of observed strengths
- `weaknesses`: list of observed weaknesses
- `reliability`: consistency and reliability assessment
- `recommendations`: list of suggested next steps

Insight outputs are stored in the run's `insights[]` array.

## 8. Run IDs and Migration

Run IDs are strict and validated as:

- pattern: `<base>-NNN`
- regex: `^[A-Za-z0-9_-]+-\d{3}$`

Examples:

- valid: `gpt-4o-001`
- invalid: `gpt-4o`, `gpt-4o-01`, `bad.id-001`

On startup, the app attempts to migrate legacy IDs into strict format and logs how many were migrated.

## 9. Data Model Reference

Every run record (`results/<run_id>.json`) includes:

- `runId`, `timestamp`, `modelName`, `capabilityId`, `capabilityType`
- `prompt`, optional `systemPrompt`
- `iterationCount`, `params`
- `responses[]` (raw output + deterministic scoring fields)
- `summary` (capability scoring aggregates)
- optional `insights[]`

### Capability Summary

```json
{
  "total": 10,
  "averageScore": 0.9,
  "minScore": 0.5,
  "maxScore": 1.0,
  "passCount": 9,
  "passRate": 90.0,
  "passThreshold": 0.8
}
```

## 10. API Endpoints

- `GET /health`
- `GET /api/capabilities`
- `GET /api/fragments/capability-details?capabilityId=...`
- `POST /api/query` - execute a single capability run
- `POST /api/profile` - execute a strength profile across capabilities
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/analyze`
- `GET /api/runs/{run_id}/pdf`

## 11. Testing

Pytest suite under `tests/`:

```bash
pytest
```

Coverage includes:

- startup health and version header
- strict run ID validation
- legacy run ID migration
- escaped analysis error rendering
- capability endpoint and alias checks
- query processor execution and deterministic scoring
- strength profile building and category filtering
- AI service response extraction and error handling

## 12. Troubleshooting

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

## 13. Research Practices

Recommended baseline:

- use at least 20 iterations for meaningful proportions
- keep persona prompts concise and intentional
- compare runs by changing one variable at a time
- preserve run JSONs for reproducibility and audit
- use strength profiles to identify category-level patterns across many tests

## 14. Security Notes

- `.env` is gitignored; keep real keys out of VCS.
- User-visible markdown is escaped before rendering.
- Links and images are stripped in markdown rendering.
- Run lookup paths are guarded by strict run ID validation and path traversal checks.
- AI service errors use typed exceptions to prevent leaking internal details to the UI.
