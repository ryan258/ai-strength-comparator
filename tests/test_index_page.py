from __future__ import annotations


def test_index_page_exposes_both_compare_actions(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Compare All Models by Category" in response.text
    assert "Compare All Models on Selected Test" in response.text
