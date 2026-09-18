"""Wires the M2 f1core Orchestrator (docs/plan/phase-2.md T1) into the live
pipeline: on each lap_completed event, builds a car.lap.observation Value
from the event and the just-updated CarState, recomputes that driver's
tyre/pace/lap-time/finish-time predictions via the registered Components,
and returns the resolved Values for RaceStateBuilder.apply_predictions to
mirror onto CarState.

NOT RUNNABLE in this dev environment: constructing f1core.Value/Snapshot
needs Python >= 3.11 here (see f1models/tyre.py's module docstring). All
f1core/f1models/f1engine imports are deferred into PredictionPipeline's
methods, not module level, so importing this module itself doesn't require
the real toolchain — only actually using it does.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from f1core.events import DomainEvent
    from f1core.snapshot import Explanation
    from f1core.values import Value
    from f1state.state import CarState

# Resolved var_ids RaceStateBuilder.apply_predictions knows how to mirror
# onto CarState. Keeping this list here (not in builder.py) means adding a
# new M2+ prediction only touches this module, not the event-dispatch one.
RESOLVED_VAR_IDS = (
    "car.tyre.deg_rate",
    "car.tyre.deg_cliff_lap",
    "car.pace.base_s",
    "car.lap.time_pred",
    "car.race.finish_time_pred",
)


def _is_clean_air(event: DomainEvent) -> bool:
    """CLAUDE.md's glossary, read straight off the event: interval to the
    car ahead > 2s, not an in/out lap (f1ingest already derives
    is_pit_out_lap/is_pit_in_lap per-lap), green flag."""
    return (
        event.track_status == "GREEN"
        and event.interval_s is not None
        and event.interval_s > 2.0
        and not event.is_pit_out_lap
        and not event.is_pit_in_lap
    )


class PredictionPipeline:
    def __init__(self, config_dir: Path) -> None:
        from f1core.graph import DependencyGraph
        from f1core.orchestrator import Orchestrator
        from f1core.registry import VariableRegistry
        from f1core.snapshot import Snapshot
        from f1engine.predictors import DeterministicRacePredictor, LapTimePredictor
        from f1models.pace import PaceEstimator
        from f1models.tyre import TyreDegEstimator

        registry = VariableRegistry.load(config_dir / "variables")
        graph = DependencyGraph(registry)
        components = [
            TyreDegEstimator(),
            PaceEstimator(),
            LapTimePredictor(),
            DeterministicRacePredictor(),
        ]
        self._orchestrator = Orchestrator(graph, components)
        self._snapshot = Snapshot(state_version="m2-0", registry=registry)
        self._version_counter = 0

    def on_lap_completed(
        self, car: CarState, event: DomainEvent, total_laps: int | None = None
    ) -> dict[str, Value]:
        """`total_laps` (from the enclosing RaceState, already known at
        session creation — see f1api.live.LiveReplayManager.create) seeds
        race.total_laps into the snapshot: DeterministicRacePredictor needs
        it and nothing else in this per-driver pipeline would ever set it.
        """
        from f1core.values import Kind, Value

        if event.lap_time_s is None:
            # No usable data for this lap (a known OpenF1 gap, e.g. lap 1
            # of a session) — degrade gracefully rather than feed a fit
            # or a race-time sum a None (CLAUDE.md rule 7).
            return {}

        self._version_counter += 1
        state_version = f"m2-{self._version_counter}"
        scope_id = str(event.driver)

        updates = []
        if total_laps is not None:
            updates.append(
                Value(
                    var_id="race.total_laps",
                    scope_id="",
                    kind=Kind.OBSERVED,
                    data=total_laps,
                    source="f1state.predictions",
                    state_version=state_version,
                    ts=event.ts,
                )
            )
        updates.append(
            Value(
                var_id="car.lap.observation",
                scope_id=f"{scope_id}:{event.lap}",
                kind=Kind.OBSERVED,
                data={
                    "lap": event.lap,
                    "tyre_age_laps": event.tyre_age_laps or 0,
                    "compound": event.compound,
                    "lap_time_s": event.lap_time_s,
                    "is_clean_air": _is_clean_air(event),
                    "stint_number": car.stint_number,
                },
                source="f1state.predictions",
                state_version=state_version,
                ts=event.ts,
            )
        )
        self._snapshot = self._snapshot.with_updates(updates, state_version)
        self._snapshot = self._orchestrator.recompute(
            self._snapshot,
            changed_var_ids=["car.lap.observation"],
            scope_id=scope_id,
            state_version=state_version,
        )

        resolved = {}
        for var_id in RESOLVED_VAR_IDS:
            value = self._snapshot.get(var_id, scope_id)
            if value is not None:
                resolved[var_id] = value
        return resolved

    def explain(self, var_id: str, driver: int) -> Explanation:
        """Delegates to f1core.Snapshot.explain on this pipeline's current
        snapshot — "why is this prediction what it is" (docs/plan/phase-2.md
        T5's done-when). Not yet wired to an HTTP endpoint (T6 only extends
        CarStateOut/LiveFrameOut); exposing it is docs/backlog.md."""
        return self._snapshot.explain(var_id, str(driver))
