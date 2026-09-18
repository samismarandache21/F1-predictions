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
