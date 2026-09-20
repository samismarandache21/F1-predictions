/**
 * Timing tower ordering: by position ascending. Cars with no recorded
 * position yet (haven't completed a lap — e.g. right at race start, or a
 * cold-start circuit's first lap before OpenF1's as-of position join has
 * anything to report) sort after every car with a known position, and are
 * ordered by driver number among themselves so the tower doesn't jitter
 * randomly while multiple cars are still positionless.
 */

export interface SortableCar {
  driver: number;
  position: number | null;
}

export function sortCarsByPosition<T extends SortableCar>(cars: readonly T[]): T[] {
  return [...cars].sort((a, b) => {
    if (a.position === null && b.position === null) {
      return a.driver - b.driver;
    }
    if (a.position === null) {
      return 1;
    }
    if (b.position === null) {
      return -1;
    }
    return a.position - b.position;
  });
}

export interface PredictablyFinishingCar {
  driver: number;
  predictedFinishTimeS: number | null;
}

/**
 * V5's predicted running order (docs/plan/phase-2.md T7): sorting each
 * driver's car.race.finish_time_pred is the only place this cross-driver
 * ordering can happen — f1engine's DeterministicRacePredictor deliberately
 * only ever sees one driver's scope_id per compute() call (see
 * f1engine/predictors.py's module docstring), so it can't produce this
 * ranking itself. Cars with no prediction yet sort after every car with
 * one, ordered by driver number among themselves, mirroring
 * sortCarsByPosition's same convention for missing data.
 */
export function sortCarsByPredictedFinish<T extends PredictablyFinishingCar>(
  cars: readonly T[],
): T[] {
  return [...cars].sort((a, b) => {
    if (a.predictedFinishTimeS === null && b.predictedFinishTimeS === null) {
      return a.driver - b.driver;
    }
    if (a.predictedFinishTimeS === null) {
      return 1;
    }
    if (b.predictedFinishTimeS === null) {
      return -1;
    }
    return a.predictedFinishTimeS - b.predictedFinishTimeS;
  });
}

/** 1-based predicted finishing position for every car with a prediction,
 * keyed by driver number — the "order" half of V5, looked up per row in
 * the timing tower rather than re-sorting once per car rendered. */
export function predictedPositionsByDriver<T extends PredictablyFinishingCar>(
  cars: readonly T[],
): Map<number, number> {
  const ranked = sortCarsByPredictedFinish(cars).filter((car) => car.predictedFinishTimeS !== null);
  return new Map(ranked.map((car, index) => [car.driver, index + 1]));
}
