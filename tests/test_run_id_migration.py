from __future__ import annotations

import asyncio
import json


def test_legacy_run_ids_are_migrated_to_strict_format(client) -> None:
    services = client.app.state.services
    results_root = services.storage.results_root
    results_root.mkdir(parents=True, exist_ok=True)

    legacy_path = results_root / "legacyrun.json"
    legacy_data = {
        "modelName": "test/model",
        "capabilityId": "math_order_of_ops",
        "capabilityType": "capability",
        "responses": [{"iteration": 1, "raw": "57", "score": 1.0, "passed": True}],
        "summary": {"averageScore": 1.0, "passRate": 100.0, "passCount": 1, "total": 1},
        "options": [],
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    mapping = asyncio.run(services.storage.migrate_legacy_run_ids())
    assert mapping["legacyrun"] == "legacyrun-001"

    strict_path = results_root / "legacyrun-001.json"
    assert strict_path.exists()

    strict_data = json.loads(strict_path.read_text(encoding="utf-8"))
    assert strict_data["runId"] == "legacyrun-001"
