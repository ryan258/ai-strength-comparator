from __future__ import annotations


def _structured_content() -> dict:
    return {
        "executive_summary": "Synthetic aggregate summary.",
        "strengths": ["High score in reasoning."],
        "weaknesses": ["Lower consistency in safety."],
        "reliability": ["Coverage remained high across tests."],
        "recommendations": ["Increase iterations for narrow categories."],
    }


def test_aggregate_insights_endpoint_returns_htmx_fragment(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_generate(_config) -> dict:
        return {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "analystModel": "test/model",
            "targetType": "profile",
            "content": _structured_content(),
        }

    monkeypatch.setattr(services.analysis_engine, "generate_aggregate_insight", fake_generate)

    response = client.post(
        "/api/insights",
        headers={"HX-Request": "true"},
        json={
            "targetType": "profile",
            "payload": {"overallScore": 0.88, "tests": []},
            "analystModel": "test/model",
            "contentId": "aggregate-analysis-content-test",
        },
    )

    assert response.status_code == 200
    assert "Executive Summary" in response.text
    assert "Strength Signals" in response.text


def test_aggregate_insights_endpoint_accepts_string_payload_json(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_generate(config) -> dict:
        assert config.target_type == "comparison"
        assert config.payload.get("modelsCompared") == 2
        return {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "analystModel": "test/model",
            "targetType": "comparison",
            "content": _structured_content(),
        }

    monkeypatch.setattr(services.analysis_engine, "generate_aggregate_insight", fake_generate)

    response = client.post(
        "/api/insights",
        json={
            "targetType": "comparison",
            "payload": "{\"modelsCompared\": 2, \"rankings\": []}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["targetType"] == "comparison"
    assert "content" in payload
