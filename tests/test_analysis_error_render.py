from __future__ import annotations


def test_analysis_error_render_escapes_exception_text(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_get_run(run_id: str):
        return {
            "runId": run_id,
            "modelName": "test/model",
            "paradoxId": "autonomous_vehicle_equal_innocents",
            "paradoxType": "trolley",
            "responses": [{"decisionToken": "{1}", "explanation": "test"}],
            "summary": {"options": [], "undecided": {"count": 0, "percentage": 0}},
            "options": [],
        }

    async def raise_analysis_error(_cfg):
        raise ValueError('<script>alert("x")</script>')

    monkeypatch.setattr(services.storage, "get_run", fake_get_run)
    monkeypatch.setattr(services.analysis_engine, "generate_insight", raise_analysis_error)

    response = client.post("/api/runs/model-001/analyze")
    assert response.status_code == 200

    body = response.text
    assert "analysis failed" in body
    assert "<script>alert(\"x\")</script>" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;/script&gt;" in body
