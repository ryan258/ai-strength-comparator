from __future__ import annotations


def success_run_payload(run_config, *, average_score: float = 0.9) -> dict:
    capability = run_config.resolved_capability()
    passed = average_score >= 0.8
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "modelName": run_config.modelName,
        "capabilityId": capability["id"],
        "capabilityType": "capability",
        "summary": {
            "total": 1,
            "averageScore": average_score,
            "passRate": 100.0 if passed else 0.0,
            "passCount": 1 if passed else 0,
            "passThreshold": 0.8,
        },
        "responses": [{"iteration": 1, "score": average_score, "passed": passed}],
        "prompt": capability["promptTemplate"],
    }
