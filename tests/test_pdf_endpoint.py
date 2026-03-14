from __future__ import annotations

from lib.reporting import ReportGenerationUnavailableError


def test_pdf_endpoint_returns_503_when_pdf_dependencies_are_unavailable(
    client,
    monkeypatch,
) -> None:
    services = client.app.state.services

    async def fake_get_run(run_id: str) -> dict:
        return {
            "runId": run_id,
            "modelName": "test/model",
            "capabilityId": "math_order_of_ops",
            "capabilityType": "capability",
            "responses": [{"iteration": 1, "raw": "57", "score": 1.0, "passed": True}],
            "summary": {"averageScore": 1.0, "passRate": 100.0, "passCount": 1, "total": 1},
        }

    def raise_unavailable(_run_data, _capability, _insight=None) -> bytes:
        raise ReportGenerationUnavailableError("WeasyPrint is unavailable")

    monkeypatch.setattr(services.storage, "get_run", fake_get_run)
    monkeypatch.setattr(services.report_generator, "generate_pdf_report", raise_unavailable)

    response = client.get("/api/runs/model-001/pdf")

    assert response.status_code == 503
    assert response.json()["detail"] == "WeasyPrint is unavailable"
