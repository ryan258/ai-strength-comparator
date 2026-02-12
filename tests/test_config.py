from __future__ import annotations

import pytest

from lib.config import AppConfig


def test_choice_inference_env_false_parses_to_false(monkeypatch) -> None:
    monkeypatch.setenv("AI_CHOICE_INFERENCE_ENABLED", "false")

    cfg = AppConfig()

    assert cfg.AI_CHOICE_INFERENCE_ENABLED is False


def test_choice_inference_env_invalid_raises(monkeypatch) -> None:
    monkeypatch.setenv("AI_CHOICE_INFERENCE_ENABLED", "maybe")

    with pytest.raises(ValueError, match="AI_CHOICE_INFERENCE_ENABLED"):
        AppConfig()
