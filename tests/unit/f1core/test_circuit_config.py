from pathlib import Path

from f1core.config.circuit import load_all_circuits


def test_fixture_circuits_load(config_dir: Path) -> None:
    circuits = load_all_circuits(config_dir / "circuits")
    assert set(circuits) == {"monza", "madring"}
    assert circuits["monza"].pit_lane_loss_s.value == 24.0
    assert circuits["monza"].type == "permanent"


def test_cold_start_circuit_has_no_fabricated_priors(config_dir: Path) -> None:
    circuits = load_all_circuits(config_dir / "circuits")
    madring = circuits["madring"]
    assert madring.length_m is None
    assert madring.pit_lane_loss_s.value is None
    assert madring.overtake_difficulty.value is None
    assert madring.data_since == 2026
