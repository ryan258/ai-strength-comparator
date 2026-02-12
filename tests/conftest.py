from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    main = importlib.import_module("main")

    class DummyReportGenerator:
        def __init__(self, templates_dir: str = "templates") -> None:
            self.templates_dir = templates_dir

        def generate_pdf_report(self, run_data, paradox, insight=None) -> bytes:
            return b"%PDF-1.4\n"

    class TempRunStorage(main.RunStorage):
        def __init__(self, _results_root: str) -> None:
            super().__init__(str(tmp_path / "results"))

    monkeypatch.setattr(main, "ReportGenerator", DummyReportGenerator)
    monkeypatch.setattr(main, "RunStorage", TempRunStorage)

    config = main.AppConfig(
        OPENROUTER_API_KEY="test/dummy-key",
        APP_BASE_URL="http://localhost:8000",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        AVAILABLE_MODELS=[{"id": "test/model", "name": "Test Model"}],
        ANALYST_MODEL="test/model",
        DEFAULT_MODEL="test/model",
    )

    return main.create_app(config_override=config)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
