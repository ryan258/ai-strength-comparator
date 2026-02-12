from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_startup_reports_healthy_state(client) -> None:
    health = client.get("/health")
    assert health.status_code == 200

    payload = health.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == "6.0.0"


def test_version_header_is_attached(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-App-Version"] == "6.0.0"


def test_choice_inference_enabled_by_default(client) -> None:
    qp = client.app.state.services.query_processor
    assert qp.choice_inference_model == "test/model"


def test_choice_inference_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
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
        AI_CHOICE_INFERENCE_ENABLED=False,
    )
    app = main.create_app(config_override=config)

    with TestClient(app) as test_client:
        qp = test_client.app.state.services.query_processor
        assert qp.choice_inference_model is None
