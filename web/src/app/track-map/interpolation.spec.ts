import { interpolateS } from './interpolation';

const LENGTH_M = 5000;

describe('interpolateS', () => {
  it('interpolates linearly halfway between two samples', () => {
    const prev = { s: 100, timestampMs: 1000 };
    const next = { s: 150, timestampMs: 2000 };

    expect(interpolateS(prev, next, 1500, LENGTH_M)).toBeCloseTo(125, 6);
  });

  it('clamps to the previous sample before the window starts', () => {
    const prev = { s: 100, timestampMs: 1000 };
    const next = { s: 150, timestampMs: 2000 };

    expect(interpolateS(prev, next, 500, LENGTH_M)).toBeCloseTo(100, 6);
  });

  it('clamps to the next sample after the window ends', () => {
    const prev = { s: 100, timestampMs: 1000 };
    const next = { s: 150, timestampMs: 2000 };

    expect(interpolateS(prev, next, 2500, LENGTH_M)).toBeCloseTo(150, 6);
  });

  it('takes the short way around the loop when crossing the start/finish line', () => {
    // Car is at s=4990 (near the end of the lap) and next sample reports
    // s=20 (just after crossing back to the start). The naive interpolation
    // (20 - 4990 = -4970) would animate the car running the track
    // backwards almost a full lap; the correct path is forward through the
    // line, a total distance of only 30 m.
    const prev = { s: 4990, timestampMs: 1000 };
    const next = { s: 20, timestampMs: 2000 };

    const halfway = interpolateS(prev, next, 1500, LENGTH_M);

    expect(halfway).toBeCloseTo(5, 6); // 4990 + 15 (half of the 30 m gap), wrapped
  });

  it('reaches exactly the next sample at the end of a wraparound interpolation', () => {
    const prev = { s: 4990, timestampMs: 1000 };
    const next = { s: 20, timestampMs: 2000 };

    expect(interpolateS(prev, next, 2000, LENGTH_M)).toBeCloseTo(20, 6);
  });

  it('falls back to the next sample when timestamps are non-increasing (bad data)', () => {
    const prev = { s: 100, timestampMs: 2000 };
    const next = { s: 150, timestampMs: 2000 };

    expect(interpolateS(prev, next, 2000, LENGTH_M)).toBeCloseTo(150, 6);
  });
});
