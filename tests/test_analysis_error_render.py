from __future__ import annotations


def test_analysis_error_render_escapes_exception_text(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_get_run(run_id: str):
        return {
            "runId": run_id,
            "modelName": "test/model",
            "capabilityId": "math_order_of_ops",
            "capabilityType": "capability",
            "responses": [{"iteration": 1, "raw": "57", "score": 1.0, "passed": True}],
            "summary": {"averageScore": 1.0, "passRate": 100.0, "passCount": 1, "total": 1},
            "options": [],
        }

    async def raise_analysis_error(_cfg):
        raise ValueError('<script>alert("x")</script>')

    monkeypatch.setattr(services.storage, "get_run", fake_get_run)
    monkeypatch.setattr(services.analysis_engine, "generate_insight", raise_analysis_error)

    response = client.post("/api/runs/model-001/analyze")
    assert response.status_code == 400

    body = response.text
    assert "analysis failed" in body
    assert "<script>alert(\"x\")</script>" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;/script&gt;" in body
