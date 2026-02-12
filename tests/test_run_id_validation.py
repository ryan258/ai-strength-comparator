from __future__ import annotations

import pytest


@pytest.mark.parametrize("run_id", ["model", "model-01", "model-0001", "bad.id-001"])
def test_run_id_requires_strict_suffix(client, run_id: str) -> None:
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid run_id"


def test_strict_run_id_shape_is_accepted(client) -> None:
    response = client.get("/api/runs/model-001")
    assert response.status_code == 404
