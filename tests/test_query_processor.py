from __future__ import annotations

import asyncio

from lib.query_processor import (
    _extract_choice_from_classifier_output,
    _infer_option_from_text,
    QueryProcessor,
    RunConfig,
    parse_trolley_response,
    render_options_template,
)


def test_render_options_template_appends_strict_single_choice_contract() -> None:
    paradox = {
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "Alpha", "description": "Do alpha."},
            {"id": 2, "label": "Beta", "description": "Do beta."},
        ],
    }

    prompt, resolved_options = render_options_template(paradox)

    assert len(resolved_options) == 2
    assert "**Output Contract (Strict):**" in prompt
    assert "`{1}`" in prompt
    assert "`{2}`" in prompt
    assert '"{1} or {2}"' in prompt


def test_parse_trolley_response_marks_multiple_tokens_as_undecided() -> None:
    parsed = parse_trolley_response("{1} or {2} depends on context", option_count=4)

    assert parsed["decisionToken"] is None
    assert parsed["optionId"] is None
    assert parsed["explanation"] == "{1} or {2} depends on context"


def test_parse_trolley_response_keeps_single_token() -> None:
    parsed = parse_trolley_response("{3} Targeted action is proportional.", option_count=4)

    assert parsed["decisionToken"] == "{3}"
    assert parsed["optionId"] == 3
    assert parsed["explanation"] == "Targeted action is proportional."


def test_parse_trolley_response_accepts_repeated_same_token() -> None:
    parsed = parse_trolley_response("I choose {2}. Final answer remains {2}.", option_count=3)

    assert parsed["decisionToken"] == "{2}"
    assert parsed["optionId"] == 2


def test_infer_option_from_text_detects_explicit_commitment() -> None:
    response = (
        "After weighing tradeoffs, I think a balanced policy is best. "
        "So I'd choose {2}."
    )
    assert _infer_option_from_text(response, option_count=3) == 2


def test_extract_choice_from_classifier_output() -> None:
    assert _extract_choice_from_classifier_output("2", option_count=4) == 2
    assert _extract_choice_from_classifier_output("{3}", option_count=4) == 3
    assert _extract_choice_from_classifier_output("0", option_count=4) is None


def test_query_processor_ai_classifier_fallback_infers_option() -> None:
    class DummyAIService:
        def __init__(self) -> None:
            self.call_count = 0

        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> str:
            self.call_count += 1
            if "Classify the FINAL chosen option" in prompt:
                return "2"
            return "I am evaluating all options and balancing tradeoffs."

    dummy_ai = DummyAIService()
    qp = QueryProcessor(
        dummy_ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model="classifier/model",
    )
    paradox = {
        "id": "test_paradox",
        "type": "trolley",
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
            {"id": 3, "label": "C", "description": "Option C"},
        ],
    }

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="generator/model",
                paradox=paradox,
                iterations=1,
                params={"max_tokens": 200},
            )
        )
    )

    response = run_data["responses"][0]
    assert response["decisionToken"] == "{2}"
    assert response["optionId"] == 2
    assert response["inferred"] is True
    assert response["inferenceMethod"] == "ai_classifier"
    assert dummy_ai.call_count == 2
