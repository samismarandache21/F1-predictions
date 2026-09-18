/**
 * Pure geometry helpers for the track map: projecting a raw (x, y) sample
 * onto the circuit polyline to get its arc-length position `s`, and the
 * inverse lookup (s -> x, y) used when rendering an interpolated position.
 *
 * Mirrors backend/f1track/src/f1track/projection.py's CircuitProjector
 * (KD-tree there, since it runs against thousands of historical samples at
 * ingestion time; a linear scan here, since this only runs once per
 * incoming live position sample — a handful of times a second per car, not
 * once per animation frame — so an O(N) scan over ~2000 polyline points is
 * cheap). See docs/f1-strategy-foundation.md §5.
 */

export interface PolylineGeometry {
  x: number[];
  y: number[];
  s: number[];
  lengthM: number;
}

export interface ProjectedPoint {
  s: number;
  distM: number;
}

function projectOntoSegment(
  px: number,
  py: number,
  ax: number,
  ay: number,
  aS: number,
  bx: number,
  by: number,
  bS: number,
): { s: number; dist: number } {
  const abx = bx - ax;
  const aby = by - ay;
  const segLenSq = abx * abx + aby * aby;
  if (segLenSq === 0) {
    return { s: aS, dist: Math.hypot(px - ax, py - ay) };
  }
  let t = ((px - ax) * abx + (py - ay) * aby) / segLenSq;
  t = Math.max(0, Math.min(1, t));
  const projX = ax + t * abx;
  const projY = ay + t * aby;
  const dist = Math.hypot(px - projX, py - projY);
  return { s: aS + t * (bS - aS), dist };
}

/** Nearest point on the polyline to (x, y): its arc-length position `s`
 * and how far off the track (x, y) actually was. */
export function projectToS(geometry: PolylineGeometry, x: number, y: number): ProjectedPoint {
  const n = geometry.x.length;
  if (n === 0) {
    return { s: 0, distM: 0 };
  }

  let bestIdx = 0;
  let bestDistSq = Infinity;
  for (let i = 0; i < n; i++) {
    const dx = geometry.x[i] - x;
    const dy = geometry.y[i] - y;
    const distSq = dx * dx + dy * dy;
    if (distSq < bestDistSq) {
      bestDistSq = distSq;
      bestIdx = i;
    }
  }

  let bestS = geometry.s[bestIdx];
  let bestDist = Math.sqrt(bestDistSq);

  // Refine against the two segments touching the nearest point, exactly
  // like the backend projector — the wraparound segment (last point back
  // to the first) uses lengthM as its far end so `s` stays monotonic
  // through the wrap instead of jumping back to 0.
  for (const start of [bestIdx - 1, bestIdx]) {
    const i = ((start % n) + n) % n;
    const j = (i + 1) % n;
    const bS = j === 0 ? geometry.lengthM : geometry.s[j];
    const { s, dist } = projectOntoSegment(
      x,
      y,
      geometry.x[i],
      geometry.y[i],
      geometry.s[i],
      geometry.x[j],
      geometry.y[j],
      bS,
    );
    if (dist < bestDist) {
      bestDist = dist;
      bestS = ((s % geometry.lengthM) + geometry.lengthM) % geometry.lengthM;
    }
  }

  return { s: bestS, distM: bestDist };
}

/** Inverse lookup: s -> (x, y), via binary search over the sorted `s`
 * array followed by linear interpolation between the two bracketing
 * points. Used to render a car at an interpolated arc-length position
 * without cutting across the infield (docs/f1-strategy-foundation.md §5:
 * "interpolate along s, not in straight lines between points"). */
export function sToXY(geometry: PolylineGeometry, s: number): { x: number; y: number } {
  const n = geometry.x.length;
  if (n === 0) {
    return { x: 0, y: 0 };
  }
  const sMod = ((s % geometry.lengthM) + geometry.lengthM) % geometry.lengthM;

  // Largest index i with geometry.s[i] <= sMod (geometry.s is sorted ascending).
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (geometry.s[mid] <= sMod) {
      lo = mid;
    } else {
      hi = mid - 1;
    }
  }

  const i = lo;
  const j = (i + 1) % n;
  const sI = geometry.s[i];
  const sJ = j === 0 ? geometry.lengthM : geometry.s[j];
  const segLen = sJ - sI;
  const t = segLen === 0 ? 0 : (sMod - sI) / segLen;

  return {
    x: geometry.x[i] + t * (geometry.x[j] - geometry.x[i]),
    y: geometry.y[i] + t * (geometry.y[j] - geometry.y[i]),
  };
}
