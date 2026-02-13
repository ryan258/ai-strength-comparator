from __future__ import annotations

import asyncio
from typing import Any

from lib.analysis import AnalysisConfig, AnalysisEngine, _extract_json_object


class DummyAIService:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text

    async def get_model_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
        params: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> str:
        return self.response_text


def test_extract_json_object_handles_braces_inside_strings() -> None:
    payload = (
        'preface {"executive_summary":"Brace } inside text",'
        '"strengths":["one"],"weaknesses":["two"],'
        '"reliability":["three"],"recommendations":["four"]} trailing'
    )

    extracted = _extract_json_object(payload)

    assert extracted is not None
    assert extracted.endswith("}")
    assert "Brace } inside text" in extracted


def test_generate_insight_falls_back_when_schema_is_invalid() -> None:
    raw_content = (
        '{"executive_summary":"ok","strengths":[],"weaknesses":[],'
        '"reliability":"not-a-list","recommendations":[]}'
    )
    engine = AnalysisEngine(DummyAIService(raw_content))

    result = asyncio.run(
        engine.generate_insight(
            AnalysisConfig(
                run_data={"modelName": "test/model", "capabilityId": "cap-1", "responses": []},
                analyst_model="test/model",
            )
        )
    )

    assert "legacy_text" in result["content"]
    assert result["content"]["legacy_text"] == raw_content

