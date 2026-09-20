/**
 * Client-side per-driver lap history for the V4 degradation chart
 * (docs/plan/phase-2.md T7). The backend never streams full lap history —
 * CarStateOut only ever carries the *latest* lap's fields (see
 * f1state/state.py's CarState) — so this accumulates one point per
 * completed lap out of the same WS frames the rest of the UI already
 * consumes, the same way track-map/interpolation.ts builds its own
 * render buffer out of position samples rather than needing the backend
 * to buffer them.
 */

export interface LapPoint {
  lap: number;
  tyreAgeLaps: number;
  lapTimeS: number;
  isCleanAir: boolean;
}

export interface ObservableCarState {
  driver: number;
  stintNumber: number;
  lastLap: number | null;
  lastLapTimeS: number | null;
  tyreAgeLaps: number | null;
  lastLapIsCleanAir: boolean | null;
}

/** Tracks lap history per driver, reset whenever that driver's stint
 * changes — the backend's own fit (f1models.tyre.TyreDegEstimator) is
 * scoped to the current stint only, so the chart mirrors that rather than
 * showing tyre-life data that spans a pit stop. */
export class DegradationHistoryTracker {
  private readonly historyByDriver = new Map<number, LapPoint[]>();
  private readonly stintByDriver = new Map<number, number>();

  /** Call once per incoming frame per car. No-ops when the lap fields
   * aren't populated yet, or when this lap was already recorded. */
  observe(car: ObservableCarState): void {
    if (car.lastLap == null || car.lastLapTimeS == null || car.tyreAgeLaps == null) {
      return;
    }

    const knownStint = this.stintByDriver.get(car.driver);
    if (knownStint !== undefined && knownStint !== car.stintNumber) {
      this.historyByDriver.delete(car.driver);
    }
    this.stintByDriver.set(car.driver, car.stintNumber);

    const history = this.historyByDriver.get(car.driver) ?? [];
    const lastRecorded = history[history.length - 1];
    if (lastRecorded && lastRecorded.lap === car.lastLap) {
      return;
    }

    history.push({
      lap: car.lastLap,
      tyreAgeLaps: car.tyreAgeLaps,
      lapTimeS: car.lastLapTimeS,
      isCleanAir: car.lastLapIsCleanAir ?? false,
    });
    this.historyByDriver.set(car.driver, history);
  }

  historyFor(driver: number): readonly LapPoint[] {
    return this.historyByDriver.get(driver) ?? [];
  }

  /** Drops history for any driver not in `activeDrivers` — called when the
   * followed driver changes, so switching away and back doesn't leak a
   * stale chart from a driver who's no longer being watched (memory only;
   * correctness doesn't depend on this). */
  prune(activeDrivers: ReadonlySet<number>): void {
    for (const driver of this.historyByDriver.keys()) {
      if (!activeDrivers.has(driver)) {
        this.historyByDriver.delete(driver);
        this.stintByDriver.delete(driver);
      }
    }
  }
}

export interface FitPreviewPoint {
  tyreAgeLaps: number;
  lapTimeS: number;
}

/**
 * A two-point line preview of the reported degradation rate, anchored
 * through the mean of the *clean-air* observed points — not a re-fit of
 * f1models.degradation_math's real model (which the frontend has no way
 * to reproduce exactly; it only ever sees the resolved deg_rate_s_per_lap,
 * not the raw fit inputs). This is a display aid showing the reported
 * slope's direction and magnitude against the actual laps, not a claim
 * that the backend computed this exact line.
 */
export function fittedLinePreview(
  points: readonly LapPoint[],
  degRateSPerLap: number,
): FitPreviewPoint[] {
  const clean = points.filter((point) => point.isCleanAir);
  if (clean.length === 0) {
    return [];
  }

  const meanAge = clean.reduce((sum, point) => sum + point.tyreAgeLaps, 0) / clean.length;
  const meanLapTimeS = clean.reduce((sum, point) => sum + point.lapTimeS, 0) / clean.length;
  const minAge = Math.min(...clean.map((point) => point.tyreAgeLaps));
  const maxAge = Math.max(...clean.map((point) => point.tyreAgeLaps));

  return [minAge, maxAge].map((tyreAgeLaps) => ({
    tyreAgeLaps,
    lapTimeS: meanLapTimeS + degRateSPerLap * (tyreAgeLaps - meanAge),
  }));
}
