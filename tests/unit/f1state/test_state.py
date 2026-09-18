from __future__ import annotations

from f1state.state import CarState, RaceState


def test_with_car_never_mutates_the_original_state() -> None:
    state0 = RaceState(session_key=9912)
    car = CarState(driver=1, position=1)

    state1 = state0.with_car(car)

    assert state0.cars == {}
    assert state1.cars == {1: car}
    assert state1 is not state0


def test_with_car_does_not_share_the_underlying_dict_across_versions() -> None:
    state0 = RaceState(session_key=9912)
    state1 = state0.with_car(CarState(driver=1, position=1))
    state2 = state1.with_car(CarState(driver=2, position=2))

    # If with_car ever mutated the previous dict in place instead of
    # copying, state1 would leak driver 2 too.
    assert 2 not in state1.cars
    assert set(state2.cars) == {1, 2}


def test_state_version_increments_on_each_update() -> None:
    state = RaceState(session_key=9912)
    state = state.with_car(CarState(driver=1))
    state = state.with_car(CarState(driver=1, position=3))

    assert state.state_version == 2


def test_car_returns_a_default_for_an_unknown_driver() -> None:
    state = RaceState(session_key=9912)

    car = state.car(44)

    assert car.driver == 44
    assert car.position is None
    assert car.retired is False
