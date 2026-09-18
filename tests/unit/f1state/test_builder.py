"""Uses lightweight duck-typed stand-ins for DomainEvent (any object with
the right attributes and a `.type` string) rather than the real
f1core.events dataclasses, so this — the most bug-prone part of T6 — can be
executed now. See f1state.builder's module docstring for why.
"""

from __future__ import annotations

from dataclasses import dataclass

from f1state.builder import CriticalEventTrigger, LapCompletedTrigger, RaceStateBuilder
from f1state.state import RaceState


@dataclass(frozen=True)
class _FakeLap:
    driver: int
    lap: int
    lap_time_s: float | None = 90.0
    position: int | None = 1
    gap_to_leader_s: float | None = 0.0
    interval_s: float | None = 0.0
    compound: str | None = "MEDIUM"
    tyre_age_laps: int | None = 1
    track_status: str | None = "GREEN"
    is_pit_out_lap: bool = False
    is_pit_in_lap: bool = False
    type: str = "lap_completed"


@dataclass(frozen=True)
class _FakePit:
    driver: int
    lap: int
    pit_lane_time_s: float | None = 22.5
    stationary_time_s: float | None = 2.4
    type: str = "pit_stop"


@dataclass(frozen=True)
class _FakeRaceControl:
    category: str | None
    flag: str | None
    message: str
    type: str = "race_control"


@dataclass(frozen=True)
class _FakeWeather:
    track_temp_c: float | None
    air_temp_c: float | None
    rainfall: bool | None
    type: str = "weather"


@dataclass(frozen=True)
class _FakeLocation:
    driver: int
    x_m: float
    y_m: float
    type: str = "location_update"


def _state() -> RaceState:
    return RaceState(session_key=9912)


def test_lap_completed_updates_car_fields() -> None:
    builder = RaceStateBuilder()
    state, triggers = builder.apply(
        _state(), _FakeLap(driver=1, lap=5, position=2, gap_to_leader_s=1.5, interval_s=0.3)
    )

    car = state.car(1)
    assert car.position == 2
    assert car.gap_to_leader_s == 1.5
    assert car.interval_s == 0.3
    assert car.compound == "MEDIUM"
    assert car.tyre_age_laps == 1
    assert car.last_lap == 5
    assert triggers == [LapCompletedTrigger(driver=1, lap=5)]


def test_compounds_used_accumulates_unique_compounds() -> None:
    builder = RaceStateBuilder()
    state = _state()
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=1, compound="MEDIUM"))
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=2, compound="MEDIUM"))
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=22, compound="HARD"))

    assert state.car(1).compounds_used == ("MEDIUM", "HARD")


def test_state_lap_advances_to_the_highest_seen() -> None:
    builder = RaceStateBuilder()
    state = _state()
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=10))
    state, _ = builder.apply(state, _FakeLap(driver=2, lap=9))  # backmarker, behind the leader

    assert state.lap == 10


def test_stale_lap_event_is_an_idempotent_no_op() -> None:
    builder = RaceStateBuilder()
    state = _state()
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=10, position=3))

    same_state, triggers = builder.apply(state, _FakeLap(driver=1, lap=9, position=1))

    assert same_state == state
    assert triggers == []


def test_duplicate_lap_event_is_an_idempotent_no_op() -> None:
    builder = RaceStateBuilder()
    state = _state()
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=10, position=3))

    same_state, triggers = builder.apply(state, _FakeLap(driver=1, lap=10, position=99))

    assert same_state == state  # the re-delivered (even if different) event changes nothing
    assert triggers == []


def test_pit_stop_sets_in_pit_and_increments_counters() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(
        _state(), _FakePit(driver=1, lap=9, pit_lane_time_s=24.156, stationary_time_s=2.2)
    )

    car = state.car(1)
    assert car.in_pit is True
    assert car.pit_stops == 1
    assert car.stint_number == 2
    assert len(car.pit_history) == 1
    assert car.pit_history[0].lap == 9
    assert car.pit_history[0].lane_time_s == 24.156
    assert car.pit_history[0].stationary_time_s == 2.2


def test_pit_history_accumulates_across_multiple_stops() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(_state(), _FakePit(driver=1, lap=9))
    state, _ = builder.apply(state, _FakePit(driver=1, lap=30))

    car = state.car(1)
    assert [record.lap for record in car.pit_history] == [9, 30]
    assert car.pit_stops == 2


def test_completing_the_out_lap_clears_in_pit() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(_state(), _FakePit(driver=1, lap=9))
    state, _ = builder.apply(state, _FakeLap(driver=1, lap=10, is_pit_out_lap=True))

    assert state.car(1).in_pit is False


def test_safety_car_deployed_updates_status_and_triggers_critical_event() -> None:
    builder = RaceStateBuilder()
    state, triggers = builder.apply(
        _state(),
        _FakeRaceControl(category="SafetyCar", flag=None, message="SAFETY CAR DEPLOYED"),
    )

    assert state.track_status == "SC"
    assert triggers == [CriticalEventTrigger(reason="SC", detail="SAFETY CAR DEPLOYED")]


def test_safety_car_ending_recovers_to_green() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(
        _state(), _FakeRaceControl(category="SafetyCar", flag=None, message="SAFETY CAR DEPLOYED")
    )
    state, triggers = builder.apply(
        state, _FakeRaceControl(category="SafetyCar", flag=None, message="SAFETY CAR ENDING")
    )

    assert state.track_status == "GREEN"
    assert triggers == [CriticalEventTrigger(reason="CLEAR", detail="SAFETY CAR ENDING")]


def test_race_control_message_with_no_status_change_is_a_no_op() -> None:
    builder = RaceStateBuilder()
    state, triggers = builder.apply(
        _state(), _FakeRaceControl(category="Other", flag=None, message="PIT EXIT CLOSED")
    )

    assert state.track_status == "GREEN"  # unchanged default
    assert triggers == []


def test_rain_onset_triggers_a_critical_event() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(
        _state(), _FakeWeather(track_temp_c=30.0, air_temp_c=20.0, rainfall=False)
    )

    state, triggers = builder.apply(
        state, _FakeWeather(track_temp_c=28.0, air_temp_c=19.0, rainfall=True)
    )

    assert state.rainfall is True
    assert triggers == [CriticalEventTrigger(reason="RAIN_START", detail="rainfall detected")]


def test_continued_rain_does_not_retrigger() -> None:
    builder = RaceStateBuilder()
    state, _ = builder.apply(
        _state(), _FakeWeather(track_temp_c=28.0, air_temp_c=19.0, rainfall=True)
    )

    state, triggers = builder.apply(
        state, _FakeWeather(track_temp_c=27.5, air_temp_c=18.9, rainfall=True)
    )

    assert triggers == []


def test_location_update_does_not_change_race_state() -> None:
    builder = RaceStateBuilder()
    state0 = _state()

    state1, triggers = builder.apply(state0, _FakeLocation(driver=1, x_m=10.0, y_m=20.0))

    assert state1 == state0
    assert triggers == []


def test_unknown_event_type_degrades_gracefully() -> None:
    @dataclass(frozen=True)
    class _FakeFutureEvent:
        type: str = "manual_input"

    builder = RaceStateBuilder()
    state0 = _state()

    state1, triggers = builder.apply(state0, _FakeFutureEvent())

    assert state1 == state0
    assert triggers == []


def test_team_lookup_populates_car_team_on_first_lap() -> None:
    builder = RaceStateBuilder(team_by_driver_number={1: "red_bull"})

    state, _ = builder.apply(_state(), _FakeLap(driver=1, lap=1))

    assert state.car(1).team == "red_bull"


def test_team_is_not_overwritten_once_set() -> None:
    builder = RaceStateBuilder(team_by_driver_number={1: "red_bull"})
    state, _ = builder.apply(_state(), _FakeLap(driver=1, lap=1))

    # Even if the lookup were somehow to change mid-race, an already-known
    # team assignment for a driver never flips mid-session.
    builder_with_different_map = RaceStateBuilder(team_by_driver_number={1: "racing_bulls"})
    state, _ = builder_with_different_map.apply(state, _FakeLap(driver=1, lap=2))

    assert state.car(1).team == "red_bull"
