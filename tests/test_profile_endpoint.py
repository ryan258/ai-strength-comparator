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


def test_profile_endpoint_returns_htmx_fragment(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_execute_run(run_config):
        return _success_run_payload(run_config)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"model-{run_counter['value']:03d}"

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
        "/api/profile",
        headers={"HX-Request": "true"},
        json={"modelName": "test/model", "iterations": 1, "categories": ["Reasoning"]},
    )

    assert response.status_code == 200
    assert "Strength Profile" in response.text
    assert "Overall Score" in response.text
    assert "Partial Results" not in response.text


def test_profile_endpoint_returns_partial_results_when_some_capabilities_fail(
    client,
    monkeypatch,
) -> None:
    services = client.app.state.services

    async def fake_execute_run(run_config):
        capability = run_config.resolved_capability()
        if capability["id"] == "math_order_of_ops":
            raise RuntimeError("simulated profile failure")
        return _success_run_payload(run_config)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"model-{run_counter['value']:03d}"

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
        "/api/profile",
        json={"modelName": "test/model", "iterations": 1, "categories": ["Reasoning"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["partial"] is True
    assert payload["errors"]
    assert payload["errors"][0]["capabilityId"] == "math_order_of_ops"
    assert payload["profile"]["tests"]
    assert payload["runs"]


def test_profile_endpoint_htmx_shows_partial_warning(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_execute_run(run_config):
        capability = run_config.resolved_capability()
        if capability["id"] == "math_order_of_ops":
            raise RuntimeError("simulated profile failure")
        return _success_run_payload(run_config)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"model-{run_counter['value']:03d}"

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
        "/api/profile",
        headers={"HX-Request": "true"},
        json={"modelName": "test/model", "iterations": 1, "categories": ["Reasoning"]},
    )

    assert response.status_code == 200
    assert "Partial Results" in response.text
    assert "math_order_of_ops" in response.text


def test_profile_endpoint_returns_500_when_all_capabilities_fail(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_execute_run(_run_config):
        raise RuntimeError("all failed")

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"model-{run_counter['value']:03d}"

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
        "/api/profile",
        json={"modelName": "test/model", "iterations": 1, "categories": ["Reasoning"]},
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"]["message"] == "All capability runs failed."
    assert payload["detail"]["errors"]


def test_profile_endpoint_rejects_invalid_categories(client) -> None:
    response = client.post(
        "/api/profile",
        json={"modelName": "test/model", "iterations": 1, "categories": ["NoSuchCategory"]},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid categories:" in detail
    assert "Valid categories:" in detail


def test_profile_endpoint_enforces_config_max_iterations(client) -> None:
    response = client.post(
        "/api/profile",
        json={"modelName": "test/model", "iterations": 999},
    )

    assert response.status_code == 400
    assert "exceeds limit" in response.json()["detail"]
