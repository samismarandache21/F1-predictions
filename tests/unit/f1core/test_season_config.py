from pathlib import Path

from f1core.config.season import load_season


def test_2026_season_has_22_active_drivers_every_round(config_dir: Path) -> None:
    season = load_season(config_dir / "seasons" / "2026.yaml")
    assert season.grid_size == 22
    for round_no in range(1, season.rounds + 1):
        active = season.drivers_for_round(round_no)
        assert len(active) == 22, f"round {round_no} had {len(active)} active drivers"


def test_2026_round_11_to_12_substitution(config_dir: Path) -> None:
    """docs/f1-driver-circuit-intel.md §1: Hadjar injured from round 12;
    Lawson moves Racing Bulls -> Red Bull; Tsunoda moves in as his replacement."""
    season = load_season(config_dir / "seasons" / "2026.yaml")

    before = season.entry_list(11)
    assert before["hadjar"] == "red_bull"
    assert before["lawson"] == "racing_bulls"
    assert "tsunoda" not in before

    after = season.entry_list(12)
    assert after["lawson"] == "red_bull"
    assert after["tsunoda"] == "racing_bulls"
    assert "hadjar" not in after


def test_2025_season_has_20_active_drivers_every_round(config_dir: Path) -> None:
    season = load_season(config_dir / "seasons" / "2025.yaml")
    assert season.grid_size == 20
    for round_no in range(1, season.rounds + 1):
        active = season.drivers_for_round(round_no)
        assert len(active) == 20, f"round {round_no} had {len(active)} active drivers"
