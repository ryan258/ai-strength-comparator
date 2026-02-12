# Paradoxes Reference

Last updated: February 6, 2026

This project’s scenario source of truth is `/Users/ryanjohnson/Projects/ai-ethics-comparator/paradoxes.json`.

## Current Dataset Snapshot

As of February 6, 2026:

- total scenarios: `89`
- paradox type: `trolley` for all scenarios
- option-count distribution:
  - 2 options: `53`
  - 3 options: `2`
  - 4 options: `34`

The runtime supports only trolley-style processing in `lib/query_processor.py`.

## JSON Schema

Each paradox entry is expected to match this shape:

```json
{
  "id": "unique_identifier",
  "title": "Display title",
  "type": "trolley",
  "category": "Optional category label",
  "promptTemplate": "Scenario text with {{OPTIONS}} placeholder",
  "options": [
    {
      "id": 1,
      "label": "Short option name",
      "description": "Detailed option consequences"
    }
  ]
}
```

Validation rules in `lib/paradoxes.py`:

- `id`, `title`, `promptTemplate` must be strings
- `options` must be a list with 2-4 entries
- each option requires:
  - integer `id` from 1 to 4
  - string `label`
  - string `description`

## Prompt Contract

Prompts should instruct the model to:

- choose exactly one option token (`{1}` through `{N}`)
- provide explanation after the token

`lib/query_processor.py` parses the first valid token and treats missing/invalid tokens as undecided.

## Backward Compatibility

`lib/paradoxes.py` still includes fallback normalization for legacy binary fields (`group1Default`/`group2Default`), but canonical data should use the `options[]` schema above.

## How To Add a New Paradox

1. Add a new object to `paradoxes.json` using the canonical schema.
2. Ensure `id` is unique and URL-safe.
3. Keep option IDs sequential starting at `1`.
4. Use clear, measurable option descriptions.
5. Verify load success by hitting:
   - `GET /api/paradoxes`
   - UI dropdown on `/`

## Dataset Verification Commands

Recompute basic counts from the JSON file:

```bash
jq 'length' paradoxes.json
jq '[.[].type] | group_by(.) | map({type: .[0], count: length})' paradoxes.json
jq '[.[].options | length] | {two: map(select(.==2))|length, three: map(select(.==3))|length, four: map(select(.==4))|length}' paradoxes.json
```

## Notes for Researchers

- Use multiple iterations per run to stabilize percentages.
- Treat undecided outcomes as signal, not noise.
- Keep run configs and prompts unchanged when comparing model behavior.
