from pathlib import Path

from f1ingest.cache import RawResponseCache


def test_miss_then_hit_round_trip(tmp_path: Path) -> None:
    cache = RawResponseCache(tmp_path)
    assert cache.get("openf1", "/laps", {"session_key": 9912}) is None

    payload = [{"lap_number": 1, "lap_duration": 87.498}]
    cache.put("openf1", "/laps", {"session_key": 9912}, payload)

    assert cache.get("openf1", "/laps", {"session_key": 9912}) == payload


def test_different_params_are_different_cache_entries(tmp_path: Path) -> None:
    cache = RawResponseCache(tmp_path)
    cache.put("openf1", "/laps", {"session_key": 1}, ["a"])
    cache.put("openf1", "/laps", {"session_key": 2}, ["b"])

    assert cache.get("openf1", "/laps", {"session_key": 1}) == ["a"]
    assert cache.get("openf1", "/laps", {"session_key": 2}) == ["b"]


def test_different_sources_do_not_collide(tmp_path: Path) -> None:
    cache = RawResponseCache(tmp_path)
    cache.put("openf1", "/results", {}, ["openf1-data"])
    cache.put("jolpica", "/results", {}, ["jolpica-data"])

    assert cache.get("openf1", "/results", {}) == ["openf1-data"]
    assert cache.get("jolpica", "/results", {}) == ["jolpica-data"]
