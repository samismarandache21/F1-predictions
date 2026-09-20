import { DegradationHistoryTracker, ObservableCarState, fittedLinePreview } from './degradation-history';

function car(overrides: Partial<ObservableCarState> = {}): ObservableCarState {
  return {
    driver: 44,
    stintNumber: 1,
    lastLap: null,
    lastLapTimeS: null,
    tyreAgeLaps: null,
    lastLapIsCleanAir: null,
    ...overrides,
  };
}

describe('DegradationHistoryTracker', () => {
  it('ignores a car with no completed lap yet', () => {
    const tracker = new DegradationHistoryTracker();

    tracker.observe(car());

    expect(tracker.historyFor(44)).toEqual([]);
  });

  it('records a point once a lap is completed', () => {
    const tracker = new DegradationHistoryTracker();

    tracker.observe(
      car({ lastLap: 1, lastLapTimeS: 91.2, tyreAgeLaps: 0, lastLapIsCleanAir: true }),
    );

    expect(tracker.historyFor(44)).toEqual([
      { lap: 1, tyreAgeLaps: 0, lapTimeS: 91.2, isCleanAir: true },
    ]);
  });

  it('does not duplicate a point when the same lap is observed again', () => {
    const tracker = new DegradationHistoryTracker();
    const sameLap = car({ lastLap: 5, lastLapTimeS: 92.0, tyreAgeLaps: 4 });

    tracker.observe(sameLap);
    tracker.observe(sameLap);
    tracker.observe(sameLap);

    expect(tracker.historyFor(44).length).toBe(1);
  });

  it('accumulates one point per new lap in order', () => {
    const tracker = new DegradationHistoryTracker();

    tracker.observe(car({ lastLap: 1, lastLapTimeS: 91.0, tyreAgeLaps: 0 }));
    tracker.observe(car({ lastLap: 2, lastLapTimeS: 91.1, tyreAgeLaps: 1 }));
    tracker.observe(car({ lastLap: 3, lastLapTimeS: 91.2, tyreAgeLaps: 2 }));

    expect(tracker.historyFor(44).map((point) => point.lap)).toEqual([1, 2, 3]);
  });

  it('clears history when the stint number changes (a pit stop)', () => {
    const tracker = new DegradationHistoryTracker();

    tracker.observe(car({ stintNumber: 1, lastLap: 20, lastLapTimeS: 93.0, tyreAgeLaps: 19 }));
    tracker.observe(car({ stintNumber: 2, lastLap: 22, lastLapTimeS: 89.0, tyreAgeLaps: 0 }));

    expect(tracker.historyFor(44)).toEqual([
      { lap: 22, tyreAgeLaps: 0, lapTimeS: 89.0, isCleanAir: false },
    ]);
  });

  it('tracks multiple drivers independently', () => {
    const tracker = new DegradationHistoryTracker();

    tracker.observe(car({ driver: 1, lastLap: 1, lastLapTimeS: 90.0, tyreAgeLaps: 0 }));
    tracker.observe(car({ driver: 44, lastLap: 1, lastLapTimeS: 91.0, tyreAgeLaps: 0 }));

    expect(tracker.historyFor(1).length).toBe(1);
    expect(tracker.historyFor(44).length).toBe(1);
  });

  it('prune removes history for drivers no longer active', () => {
    const tracker = new DegradationHistoryTracker();
    tracker.observe(car({ driver: 1, lastLap: 1, lastLapTimeS: 90.0, tyreAgeLaps: 0 }));
    tracker.observe(car({ driver: 44, lastLap: 1, lastLapTimeS: 91.0, tyreAgeLaps: 0 }));

    tracker.prune(new Set([44]));

    expect(tracker.historyFor(1)).toEqual([]);
    expect(tracker.historyFor(44).length).toBe(1);
  });
});

describe('fittedLinePreview', () => {
  it('returns an empty preview with no clean-air points', () => {
    expect(fittedLinePreview([{ lap: 1, tyreAgeLaps: 0, lapTimeS: 90, isCleanAir: false }], 0.05)).toEqual(
      [],
    );
  });

  it('is flat across the age range for a zero degradation rate', () => {
    const points = [
      { lap: 1, tyreAgeLaps: 0, lapTimeS: 90.0, isCleanAir: true },
      { lap: 2, tyreAgeLaps: 1, lapTimeS: 90.0, isCleanAir: true },
      { lap: 3, tyreAgeLaps: 2, lapTimeS: 90.0, isCleanAir: true },
    ];

    const line = fittedLinePreview(points, 0);

    expect(line[0].lapTimeS).toBeCloseTo(90.0, 6);
    expect(line[1].lapTimeS).toBeCloseTo(90.0, 6);
  });

  it('slopes upward across the age range for a positive degradation rate', () => {
    const points = [
      { lap: 1, tyreAgeLaps: 0, lapTimeS: 90.0, isCleanAir: true },
      { lap: 2, tyreAgeLaps: 10, lapTimeS: 90.5, isCleanAir: true },
    ];

    const line = fittedLinePreview(points, 0.05);

    expect(line[0].tyreAgeLaps).toBe(0);
    expect(line[1].tyreAgeLaps).toBe(10);
    expect(line[1].lapTimeS).toBeGreaterThan(line[0].lapTimeS);
    expect(line[1].lapTimeS - line[0].lapTimeS).toBeCloseTo(0.05 * 10, 6);
  });

  it('excludes dirty-air points from the mean anchor', () => {
    const points = [
      { lap: 1, tyreAgeLaps: 0, lapTimeS: 90.0, isCleanAir: true },
      { lap: 2, tyreAgeLaps: 1, lapTimeS: 200.0, isCleanAir: false }, // e.g. behind a Safety Car
    ];

    const line = fittedLinePreview(points, 0);

    expect(line.every((point) => Math.abs(point.lapTimeS - 90.0) < 1)).toBeTrue();
  });
});
