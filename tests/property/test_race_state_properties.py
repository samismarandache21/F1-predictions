"""Property tests for RaceStateBuilder, per docs/plan/phase-1.md T6's
'Done when': unique positions and monotonic lap counts.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from f1state.builder import RaceStateBuilder
from f1state.state import RaceState


@dataclass(frozen=True)
class _FakeLap:
    driver: int
    lap: int
    position: int | None = None
    type: str = "lap_completed"
    lap_time_s: float | None = 90.0
    gap_to_leader_s: float | None = 0.0
    interval_s: float | None = 0.0
    compound: str | None = "MEDIUM"
    tyre_age_laps: int | None = 1
    track_status: str | None = "GREEN"
    is_pit_out_lap: bool = False
    is_pit_in_lap: bool = False


@given(
    st.lists(
        st.tuples(st.integers(1, 22), st.integers(1, 60)),
        min_size=1,
        max_size=50,
        unique=True,  # unique (driver, lap) pairs: no duplicate lap re-delivery here
    )
)
@settings(max_examples=100)
def test_last_lap_is_always_the_max_lap_seen_per_driver(pairs: list[tuple[int, int]]) -> None:
    """However these (driver, lap) events arrive, each driver's tracked
    last_lap ends up as the maximum lap number they appeared with — the
    'monotonic lap counts' invariant from docs/plan/phase-1.md T6."""
    builder = RaceStateBuilder()
    state = RaceState(session_key=1)
    expected_max: dict[int, int] = {}
    for driver, lap in pairs:
        expected_max[driver] = max(expected_max.get(driver, 0), lap)
        state, _ = builder.apply(state, _FakeLap(driver=driver, lap=lap))

    for driver, max_lap in expected_max.items():
        assert state.car(driver).last_lap == max_lap


@given(st.permutations(list(range(1, 23))))
@settings(max_examples=50)
def test_distinct_input_positions_stay_distinct(order: list[int]) -> None:
    """22 drivers, each reporting a distinct position on the same lap, in a
    random arrival order: the final state must show all 22 positions, still
    distinct — the 'unique positions' invariant from docs/plan/phase-1.md T6."""
    builder = RaceStateBuilder()
    state = RaceState(session_key=1)
    for position, driver in enumerate(order, start=1):
        state, _ = builder.apply(state, _FakeLap(driver=driver, lap=1, position=position))

    positions = [state.car(driver).position for driver in range(1, 23)]
    assert sorted(positions) == list(range(1, 23))
    assert len(set(positions)) == len(positions)
