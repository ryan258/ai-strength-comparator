from __future__ import annotations

from lib.ai_service import AIModelNotFoundError
from tests.helpers import success_run_payload


def test_compare_endpoint_returns_htmx_fragment(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_execute_run(run_config):
        return success_run_payload(run_config)

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


def test_compare_endpoint_compares_selected_capability_across_all_models(client, monkeypatch) -> None:
    services = client.app.state.services
    services.config.AVAILABLE_MODELS = [
        {"id": "test/model", "name": "Test Model"},
        {"id": "other/model", "name": "Other Model"},
    ]

    async def fake_execute_run(run_config):
        average_score = 0.95 if run_config.modelName == "other/model" else 0.85
        return success_run_payload(run_config, average_score=average_score)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"cmp-cap-{run_counter['value']:03d}"

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
        json={
            "comparisonScope": "capability",
            "capabilityId": "math_order_of_ops",
            "iterations": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparisonScope"] == "capability"
    assert payload["capabilityId"] == "math_order_of_ops"
    assert payload["capabilityTitle"] == "Arithmetic: Order of Operations"
    assert payload["testsPerModel"] == 1
    assert payload["iterations"] == 2
    assert payload["categories"] == ["Reasoning"]
    assert payload["modelsCompared"] == 2
    assert [item["modelId"] for item in payload["rankings"]] == ["other/model", "test/model"]


def test_compare_endpoint_capability_scope_renders_capability_in_fragment(client, monkeypatch) -> None:
    services = client.app.state.services
    services.config.AVAILABLE_MODELS = [
        {"id": "test/model", "name": "Test Model"},
        {"id": "other/model", "name": "Other Model"},
    ]

    async def fake_execute_run(run_config):
        return success_run_payload(run_config)

    run_counter = {"value": 0}

    async def fake_generate_run_id(_model_name: str) -> str:
        run_counter["value"] += 1
        return f"cmp-frag-{run_counter['value']:03d}"

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
        json={
            "comparisonScope": "capability",
            "capabilityId": "math_order_of_ops",
            "iterations": 1,
        },
    )

    assert response.status_code == 200
    assert "Capability: Arithmetic: Order of Operations" in response.text
    assert "Reasoning" in response.text


def test_compare_endpoint_rejects_when_no_models_configured(client) -> None:
    services = client.app.state.services
    services.config.AVAILABLE_MODELS = []

    response = client.post("/api/compare", json={"iterations": 1})

    assert response.status_code == 400
    assert "No models configured" in response.json()["detail"]


def test_compare_endpoint_returns_404_when_all_models_are_missing(client, monkeypatch) -> None:
    services = client.app.state.services

    async def raise_missing_model(_run_config):
        raise AIModelNotFoundError("missing model", status_code=404)

    monkeypatch.setattr(services.query_processor, "execute_run", raise_missing_model)

    response = client.post(
        "/api/compare",
        json={
            "models": ["missing/model-a", "missing/model-b"],
            "iterations": 1,
            "categories": ["Reasoning"],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Requested model not found."


def test_compare_endpoint_returns_500_when_all_comparisons_fail(client, monkeypatch) -> None:
    services = client.app.state.services

    async def raise_runtime_error(_run_config):
        raise RuntimeError("comparison failed")

    monkeypatch.setattr(services.query_processor, "execute_run", raise_runtime_error)

    response = client.post(
        "/api/compare",
        json={
            "models": ["test/model", "other/model"],
            "iterations": 1,
            "categories": ["Reasoning"],
        },
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["message"] == "All model comparisons failed."
    assert detail["errors"]
