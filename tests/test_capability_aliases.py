from __future__ import annotations

from lib.validation import QueryRequest


def test_query_request_accepts_capability_id() -> None:
    payload = QueryRequest(modelName="test/model", capabilityId="math_order_of_ops")

    assert payload.capability_id == "math_order_of_ops"


def test_capability_endpoints_are_available(client) -> None:
    capability_list = client.get("/api/capabilities")
    assert capability_list.status_code == 200
    data = capability_list.json()
    assert isinstance(data, list)
    assert any(item.get("id") == "math_order_of_ops" for item in data)


def test_capability_details_fragment_renders(client) -> None:
    response = client.get("/api/fragments/capability-details", params={"capabilityId": "math_order_of_ops"})

    assert response.status_code == 200
    assert "Capability Prompt" in response.text
