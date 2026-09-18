from __future__ import annotations


def test_list_sessions_returns_seeded_rows(client) -> None:
    response = client.get("/sessions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_key"] == 9912
    assert data[0]["circuit_id"] == "monza"
    assert data[0]["season"] == 2025


def test_list_sessions_filters_by_year(client) -> None:
    response = client.get("/sessions", params={"year": 2026})

    assert response.status_code == 200
    assert response.json() == []


def test_list_sessions_filters_by_session_type(client) -> None:
    response = client.get("/sessions", params={"session_type": "Qualifying"})

    assert response.status_code == 200
    assert response.json() == []


def test_get_session_by_key(client) -> None:
    response = client.get("/sessions/9912")

    assert response.status_code == 200
    body = response.json()
    assert body["session_type"] == "Race"
    assert body["total_laps"] == 53


def test_get_unknown_session_is_404(client) -> None:
    response = client.get("/sessions/123456")

    assert response.status_code == 404
