from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from lib.ai_service import AIService


class DummyCompletions:
    def __init__(self, response: object) -> None:
        self._response = response

    async def create(self, **kwargs):
        return self._response


class DummyClient:
    def __init__(self, response: object) -> None:
        self.chat = SimpleNamespace(completions=DummyCompletions(response))


def _mk_response(
    *,
    content=None,
    refusal=None,
    reasoning=None,
    text=None,
    finish_reason="stop",
) -> object:
    message = SimpleNamespace(content=content, refusal=refusal, reasoning=reasoning)
    choice = SimpleNamespace(message=message, text=text, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _mk_service_with_response(response: object) -> AIService:
    service = AIService(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        referer="http://localhost",
        app_name="test-app",
        max_retries=0,
        retry_delay=0,
    )
    service.client = DummyClient(response)
    return service


def test_get_model_response_accepts_refusal_text_when_content_missing() -> None:
    service = _mk_service_with_response(_mk_response(refusal="I cannot do that."))

    result = asyncio.run(service.get_model_response("test/model", "test prompt"))

    assert result == "I cannot do that."


def test_get_model_response_extracts_text_from_structured_content_parts() -> None:
    service = _mk_service_with_response(
        _mk_response(content=[{"type": "text", "text": "{3} Pick targeted alert"}])
    )

    result = asyncio.run(service.get_model_response("test/model", "test prompt"))

    assert result == "{3} Pick targeted alert"


def test_get_model_response_reports_length_finish_reason_as_token_issue() -> None:
    service = _mk_service_with_response(
        _mk_response(content=None, refusal=None, reasoning=None, finish_reason="length")
    )

    with pytest.raises(Exception, match="max_tokens"):
        asyncio.run(service.get_model_response("test/model", "test prompt"))
