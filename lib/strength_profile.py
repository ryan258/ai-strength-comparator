"""
Strength Profile - Arsenal Module
Pure aggregation utilities for capability benchmark runs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional


def classify_strength(score: float) -> str:
    """Map a normalized score to a qualitative strength label."""
    if score >= 0.8:
        return "Strong"
    if score >= 0.6:
        return "Developing"
    return "Weak"


def _safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    return default


def summarize_capability_run(
    run_data: Mapping[str, Any],
    capability: Mapping[str, Any],
) -> Dict[str, Any]:
    """Build a compact score summary for one capability run."""
    summary = run_data.get("summary", {}) if isinstance(run_data.get("summary"), dict) else {}
    average_score = _safe_float(summary.get("averageScore"), 0.0)
    pass_rate = _safe_float(summary.get("passRate"), 0.0)

    return {
        "runId": run_data.get("runId", ""),
        "capabilityId": run_data.get("capabilityId", ""),
        "title": capability.get("title", "Unknown Test"),
        "category": capability.get("category", "General"),
        "averageScore": average_score,
        "passRate": pass_rate,
        "strength": classify_strength(average_score),
    }


def build_strength_profile(
    model_name: str,
    runs: Iterable[Mapping[str, Any]],
    capabilities: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate many capability runs into one model strength profile."""
    capability_map: Dict[str, Mapping[str, Any]] = {}
    for capability in capabilities:
        capability_id = capability.get("id")
        if isinstance(capability_id, str):
            capability_map[capability_id] = capability

    test_summaries: List[Dict[str, Any]] = []
    category_scores: Dict[str, List[float]] = defaultdict(list)

    for run in runs:
        capability_id = run.get("capabilityId")
        if not isinstance(capability_id, str):
            continue

        capability = capability_map.get(
            capability_id,
            {"title": capability_id, "category": "General"},
        )
        run_summary = summarize_capability_run(run, capability)
        test_summaries.append(run_summary)
        category_scores[run_summary["category"]].append(run_summary["averageScore"])

    total_tests = len(test_summaries)
    if total_tests == 0:
        return {
            "modelName": model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overallScore": 0.0,
            "overallStrength": "Weak",
            "tests": [],
            "categoryBreakdown": [],
            "strongestAreas": [],
            "weakestAreas": [],
        }

    average_score = sum(item["averageScore"] for item in test_summaries) / total_tests

    category_breakdown: List[Dict[str, Any]] = []
    for category, values in category_scores.items():
        if not values:
            continue
        category_avg = sum(values) / len(values)
        category_breakdown.append(
            {
                "category": category,
                "averageScore": category_avg,
                "strength": classify_strength(category_avg),
                "testCount": len(values),
            }
        )

    category_breakdown.sort(key=lambda item: item["averageScore"], reverse=True)
    sorted_tests = sorted(test_summaries, key=lambda item: item["averageScore"], reverse=True)

    strongest = sorted_tests[:3]
    strongest_ids = {
        str(item.get("capabilityId", ""))
        for item in strongest
    }
    weakest_candidates = [
        item
        for item in reversed(sorted_tests)
        if str(item.get("capabilityId", "")) not in strongest_ids
    ]
    weakest = weakest_candidates[:3]

    return {
        "modelName": model_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overallScore": average_score,
        "overallStrength": classify_strength(average_score),
        "tests": sorted_tests,
        "categoryBreakdown": category_breakdown,
        "strongestAreas": strongest,
        "weakestAreas": weakest,
    }


def filter_capability_tests(
    capabilities: Iterable[Mapping[str, Any]],
    categories: Optional[Iterable[str]] = None,
) -> List[Mapping[str, Any]]:
    """Return capability tests optionally filtered by category."""
    category_filter = {category.strip().lower() for category in categories or [] if category.strip()}

    selected: List[Mapping[str, Any]] = []
    for capability in capabilities:
        if capability.get("type") != "capability":
            continue
        if not category_filter:
            selected.append(capability)
            continue

        category_name = str(capability.get("category", "")).strip().lower()
        if category_name in category_filter:
            selected.append(capability)

    return selected
