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
