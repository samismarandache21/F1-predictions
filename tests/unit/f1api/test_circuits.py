"""Seeds circuit_geometry with a plain `.insert()`, not
f1ingest.geometry_store.save_geometry: that helper uses
`sqlalchemy.dialects.postgresql.insert` for its upsert, which only
compiles against real Postgres — see conftest.py's docstring.
"""

from __future__ import annotations

import json

from f1ingest.db.schema import circuit_geometry


def _seed_geometry(engine, *, circuit_id: str = "monza") -> None:
    with engine.begin() as conn:
        conn.execute(
            circuit_geometry.insert().values(
                circuit_id=circuit_id,
                version=1,
                built_from_session_key=9912,
                length_m=5801.3,
                points_json=json.dumps({"x": [0.0, 1.0], "y": [0.0, 1.0], "s": [0.0, 10.0]}),
                sector_boundaries_s_json=json.dumps([1885.2, 3684.0]),
                rotation_deg=-95.07,
                pit_lane_json=None,
            )
        )


def test_get_geometry_returns_the_stored_geometry(client, seeded_engine) -> None:
    _seed_geometry(seeded_engine)

    response = client.get("/circuits/monza/geometry")

    assert response.status_code == 200
    body = response.json()
    assert body["circuit_id"] == "monza"
    assert body["length_m"] == 5801.3
    assert body["x"] == [0.0, 1.0]
    assert body["sector_boundaries_s"] == [1885.2, 3684.0]
    assert body["pit_lane_x"] is None


def test_get_geometry_for_unknown_circuit_is_404(client) -> None:
    response = client.get("/circuits/nonexistent/geometry")

    assert response.status_code == 404
