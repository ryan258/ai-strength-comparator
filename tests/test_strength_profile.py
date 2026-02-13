from __future__ import annotations

from lib.query_processor import aggregate_capability_stats, evaluate_capability_response
from lib.strength_profile import build_strength_profile, filter_capability_tests


def test_evaluate_capability_response_tracks_required_and_forbidden() -> None:
    evaluation = {
        "required": [r"hello", r"world"],
        "forbidden": [r"hack"],
        "pass_threshold": 0.8,
    }

    result = evaluate_capability_response("hello world", evaluation)

    assert result["score"] == 1.0
    assert result["passed"] is True
    assert result["missingRequired"] == []
    assert result["matchedForbidden"] == []


def test_aggregate_capability_stats_computes_pass_rate() -> None:
    responses = [
        {"score": 1.0, "passed": True},
        {"score": 0.5, "passed": False},
        {"score": 1.0, "passed": True},
    ]

    summary = aggregate_capability_stats(responses, pass_threshold=0.8)

    assert summary["total"] == 3
    assert summary["passCount"] == 2
    assert summary["passRate"] == (2 / 3) * 100
    assert summary["averageScore"] == (1.0 + 0.5 + 1.0) / 3


def test_build_strength_profile_sorts_strongest_and_weakest() -> None:
    capabilities = [
        {"id": "s1", "title": "Reasoning Test", "category": "Reasoning", "type": "capability"},
        {"id": "s2", "title": "Safety Test", "category": "Safety", "type": "capability"},
        {"id": "s3", "title": "Coding Test", "category": "Coding", "type": "capability"},
        {"id": "s4", "title": "Writing Test", "category": "Writing", "type": "capability"},
    ]
    runs = [
        {
            "runId": "model-001",
            "capabilityId": "s1",
            "summary": {"averageScore": 0.9, "passRate": 100.0},
        },
        {
            "runId": "model-002",
            "capabilityId": "s2",
            "summary": {"averageScore": 0.4, "passRate": 0.0},
        },
        {
            "runId": "model-003",
            "capabilityId": "s3",
            "summary": {"averageScore": 0.8, "passRate": 75.0},
        },
        {
            "runId": "model-004",
            "capabilityId": "s4",
            "summary": {"averageScore": 0.3, "passRate": 0.0},
        },
    ]

    profile = build_strength_profile("test/model", runs, capabilities)

    assert profile["overallStrength"] == "Developing"
    assert profile["strongestAreas"][0]["capabilityId"] == "s1"
    assert profile["weakestAreas"][0]["capabilityId"] == "s4"
    strongest_ids = {item["capabilityId"] for item in profile["strongestAreas"]}
    weakest_ids = {item["capabilityId"] for item in profile["weakestAreas"]}
    assert strongest_ids.isdisjoint(weakest_ids)


def test_build_strength_profile_avoids_overlap_when_few_tests() -> None:
    capabilities = [
        {"id": "s1", "title": "Reasoning Test", "category": "Reasoning", "type": "capability"},
        {"id": "s2", "title": "Safety Test", "category": "Safety", "type": "capability"},
    ]
    runs = [
        {
            "runId": "model-001",
            "capabilityId": "s1",
            "summary": {"averageScore": 0.9, "passRate": 100.0},
        },
        {
            "runId": "model-002",
            "capabilityId": "s2",
            "summary": {"averageScore": 0.4, "passRate": 0.0},
        },
    ]

    profile = build_strength_profile("test/model", runs, capabilities)

    assert profile["strongestAreas"]
    assert profile["weakestAreas"] == []


def test_filter_capability_tests_respects_category_filter() -> None:
    capabilities = [
        {"id": "s1", "type": "capability", "category": "Reasoning"},
        {"id": "s2", "type": "capability", "category": "Safety"},
        {"id": "s3", "type": "legacy", "category": "Reasoning"},
    ]

    filtered = filter_capability_tests(capabilities, categories=["safety"])

    assert len(filtered) == 1
    assert filtered[0]["id"] == "s2"
