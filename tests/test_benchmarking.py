from __future__ import annotations

import asyncio
from typing import Any

import pytest

from lib.benchmarking import (
    BenchmarkOrchestrator,
    BenchmarkExecutionFailedError,
    CapabilityBatchConfig,
    ComparisonExecutionConfig,
    available_capability_categories,
    resolve_comparison_capabilities,
    resolve_selected_capabilities,
)
from tests.helpers import success_run_payload

CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "cap-1",
        "title": "Capability One",
        "type": "capability",
        "category": "Reasoning",
        "promptTemplate": "Solve the task.",
        "evaluation": {
            "required": ["solve"],
            "forbidden": [],
            "pass_threshold": 0.8,
            "ignore_case": True,
        },
    },
    {
        "id": "cap-2",
        "title": "Capability Two",
        "type": "capability",
        "category": "Safety",
        "promptTemplate": "Decline dangerous output.",
        "evaluation": {
            "required": ["decline"],
            "forbidden": [],
            "pass_threshold": 0.8,
            "ignore_case": True,
        },
    },
]


class ConcurrentQueryProcessor:
    def __init__(self) -> None:
        self.active_models: set[str] = set()
        self.saw_concurrent_models = False

    async def execute_run(self, run_config) -> dict[str, Any]:
        self.active_models.add(run_config.modelName)
        if len(self.active_models) > 1:
            self.saw_concurrent_models = True

        try:
            await asyncio.sleep(0.02)
        finally:
            self.active_models.remove(run_config.modelName)

        average_score = 0.9 if run_config.modelName.endswith("b") else 0.7
        return success_run_payload(run_config, average_score=average_score)


def test_available_capability_categories_returns_sorted_unique_values() -> None:
    categories = available_capability_categories(CAPABILITIES + [dict(CAPABILITIES[0])])

    assert categories == ["Reasoning", "Safety"]


def test_resolve_selected_capabilities_rejects_unknown_categories() -> None:
    with pytest.raises(ValueError, match="Invalid categories: Missing"):
        resolve_selected_capabilities(CAPABILITIES, ["Missing"])


def test_resolve_comparison_capabilities_selects_single_capability() -> None:
    selected, selected_capability = resolve_comparison_capabilities(
        CAPABILITIES,
        comparison_scope="capability",
        capability_id="cap-2",
    )

    assert [capability["id"] for capability in selected] == ["cap-2"]
    assert selected_capability is not None
    assert selected_capability["title"] == "Capability Two"


def test_execute_model_comparison_runs_models_in_parallel() -> None:
    processor = ConcurrentQueryProcessor()
    persisted: list[str] = []

    async def fake_persist(model_name: str, run_data: dict[str, Any]) -> str:
        persisted.append(f"{model_name}:{run_data['capabilityId']}")
        return f"{model_name}-001"

    orchestrator = BenchmarkOrchestrator(
        query_processor=processor,
        persist_run=fake_persist,
        concurrency_limit=2,
    )

    payload = asyncio.run(
        orchestrator.execute_model_comparison(
            ComparisonExecutionConfig(
                model_ids=["provider/model-a", "provider/model-b"],
                capabilities=[CAPABILITIES[0]],
                iterations=1,
                categories=["Reasoning"],
                model_names={
                    "provider/model-a": "Model A",
                    "provider/model-b": "Model B",
                },
            )
        )
    )

    assert processor.saw_concurrent_models is True
    assert payload["rankings"][0]["modelId"] == "provider/model-b"
    assert payload["rankings"][0]["rank"] == 1
    assert payload["testsPerModel"] == 1
    assert len(persisted) == 2


def test_execute_profile_raises_when_all_capabilities_fail() -> None:
    class FailingQueryProcessor:
        async def execute_run(self, run_config) -> dict[str, Any]:
            raise RuntimeError(f"failed: {run_config.modelName}")

    async def fake_persist(_model_name: str, _run_data: dict[str, Any]) -> str:
        return "ignored"

    orchestrator = BenchmarkOrchestrator(
        query_processor=FailingQueryProcessor(),
        persist_run=fake_persist,
        concurrency_limit=2,
    )

    with pytest.raises(BenchmarkExecutionFailedError, match="All capability runs failed"):
        asyncio.run(
            orchestrator.execute_profile(
                CapabilityBatchConfig(
                    model_name="provider/model-a",
                    capabilities=[CAPABILITIES[0]],
                    iterations=1,
                )
            )
        )


def test_execute_model_comparison_raises_when_all_models_fail_non_fatally() -> None:
    class FailingQueryProcessor:
        async def execute_run(self, _run_config) -> dict[str, Any]:
            raise RuntimeError("comparison failed")

    async def fake_persist(_model_name: str, _run_data: dict[str, Any]) -> str:
        return "ignored"

    orchestrator = BenchmarkOrchestrator(
        query_processor=FailingQueryProcessor(),
        persist_run=fake_persist,
        concurrency_limit=2,
    )

    with pytest.raises(BenchmarkExecutionFailedError, match="All model comparisons failed"):
        asyncio.run(
            orchestrator.execute_model_comparison(
                ComparisonExecutionConfig(
                    model_ids=["provider/model-a", "provider/model-b"],
                    capabilities=[CAPABILITIES[0]],
                    iterations=1,
                )
            )
        )
