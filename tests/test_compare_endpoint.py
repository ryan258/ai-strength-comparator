from __future__ import annotations


def _success_run_payload(run_config) -> dict:
    capability = run_config.resolved_capability()
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "modelName": run_config.modelName,
        "capabilityId": capability["id"],
        "capabilityType": "capability",
        "summary": {
            "total": 1,
            "averageScore": 0.9,
            "passRate": 100.0,
            "passCount": 1,
            "passThreshold": 0.8,
        },
        "responses": [{"iteration": 1, "score": 0.9, "passed": True}],
        "prompt": capability["promptTemplate"],
    }


def test_compare_endpoint_returns_htmx_fragment(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_execute_run(run_config):
        return _success_run_payload(run_config)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"cmp-{run_counter['value']:03d}"

    async def fake_save_run(
        _run_id: str,
        _run_data: dict,
        allow_overwrite: bool = True,
    ) -> None:
        return None

    monkeypatch.setattr(services.query_processor, "execute_run", fake_execute_run)
    monkeypatch.setattr(services.storage, "generate_run_id", fake_generate_run_id)
    monkeypatch.setattr(services.storage, "save_run", fake_save_run)

    response = client.post(
        "/api/compare",
        headers={"HX-Request": "true"},
        json={"iterations": 1, "categories": ["Reasoning"]},
    )

    assert response.status_code == 200
    assert "Model Comparison" in response.text
    assert "Rankings" in response.text
    assert "#1" in response.text


def test_compare_endpoint_rejects_when_no_models_configured(client) -> None:
    services = client.app.state.services
    services.config.AVAILABLE_MODELS = []

    response = client.post("/api/compare", json={"iterations": 1})

    assert response.status_code == 400
    assert "No models configured" in response.json()["detail"]

