from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.config import AppConfig


def test_concurrency_limit_must_be_positive(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONCURRENCY_LIMIT", "0")

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        AppConfig()


def test_retry_delay_must_be_integer(monkeypatch) -> None:
    monkeypatch.setenv("AI_RETRY_DELAY", "not-an-int")

    with pytest.raises(ValueError, match="AI_RETRY_DELAY must be an integer"):
        AppConfig()


def test_required_string_settings_reject_none() -> None:
    with pytest.raises(ValidationError):
        AppConfig(
            OPENROUTER_API_KEY="test-key",
            APP_BASE_URL="http://localhost:8000",
            OPENROUTER_BASE_URL=None,
        )


def test_validate_secrets_rejects_empty_required_strings() -> None:
    config = AppConfig(
        OPENROUTER_API_KEY="test-key",
        APP_BASE_URL="http://localhost:8000",
        OPENROUTER_BASE_URL="",
    )

    with pytest.raises(ValueError, match="OPENROUTER_BASE_URL not found"):
        config.validate_secrets()
