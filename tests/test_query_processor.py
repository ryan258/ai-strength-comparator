from __future__ import annotations

import asyncio
from typing import Any

import pytest

from lib.query_processor import QueryProcessor, RunConfig, evaluate_capability_response


class DummyAIService:
    def __init__(self, responses: list[str], fail_on_calls: set[int] | None = None) -> None:
        self._responses = responses
        self._fail_on_calls = fail_on_calls or set()
        self.call_count = 0

    async def get_model_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
        params: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> str:
        self.call_count += 1
        if self.call_count in self._fail_on_calls:
            raise RuntimeError(f"simulated failure {self.call_count}")
        return self._responses[self.call_count - 1]


def _capability_fixture() -> dict[str, Any]:
    return {
        "id": "cap-1",
        "type": "capability",
        "category": "Reasoning",
        "promptTemplate": "Reply with alpha.",
        "evaluation": {
            "required": [r"alpha"],
            "forbidden": [r"forbidden"],
            "pass_threshold": 0.8,
        },
    }


def test_execute_run_scores_capability_iterations() -> None:
    dummy_ai = DummyAIService(["alpha success", "forbidden text"])
    qp = QueryProcessor(dummy_ai, concurrency_limit=1)

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="test/model",
                capability=_capability_fixture(),
                iterations=2,
                systemPrompt="Be concise.",
                params={"max_tokens": 200},
            )
        )
    )

    assert run_data["capabilityType"] == "capability"
    assert run_data["summary"]["total"] == 2
    assert run_data["summary"]["passCount"] == 1
    assert run_data["summary"]["passRate"] == 50.0
    assert run_data["responses"][0]["passed"] is True
    assert run_data["responses"][1]["passed"] is False
    assert run_data["iterationCount"] == 2
    assert run_data["systemPrompt"] == "Be concise."
    assert run_data["params"]["max_tokens"] == 200


def test_execute_run_rejects_non_capability_types() -> None:
    dummy_ai = DummyAIService(["irrelevant"])
    qp = QueryProcessor(dummy_ai, concurrency_limit=1)

    with pytest.raises(ValueError, match="Unsupported capability type: legacy"):
        asyncio.run(
            qp.execute_run(
                RunConfig(
                    modelName="test/model",
                    capability={"id": "bad", "type": "legacy", "promptTemplate": "..."},
                    iterations=1,
                )
            )
        )


def test_execute_run_records_iteration_errors_as_failed_scores() -> None:
    dummy_ai = DummyAIService(["alpha success", "ignored"], fail_on_calls={2})
    qp = QueryProcessor(dummy_ai, concurrency_limit=1)

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="test/model",
                capability=_capability_fixture(),
                iterations=2,
            )
        )
    )

    assert run_data["summary"]["total"] == 2
    assert run_data["summary"]["passCount"] == 1
    assert run_data["responses"][1]["passed"] is False
    assert run_data["responses"][1]["score"] == 0.0
    assert "simulated failure 2" in run_data["responses"][1]["error"]


def test_evaluate_response_is_case_sensitive_by_default() -> None:
    evaluation = {
        "required": [r"\AYES\Z"],
        "forbidden": [],
        "pass_threshold": 1.0,
    }

    result = evaluate_capability_response("yes", evaluation)

    assert result["passed"] is False
    assert result["score"] == 0.0


def test_evaluate_response_supports_ignore_case_override() -> None:
    evaluation = {
        "required": [r"\AYES\Z"],
        "forbidden": [],
        "pass_threshold": 1.0,
        "ignore_case": True,
    }

    result = evaluate_capability_response("yes", evaluation)

    assert result["passed"] is True
    assert result["score"] == 1.0
