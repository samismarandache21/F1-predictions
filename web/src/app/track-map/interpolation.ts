/**
 * Smooth car motion between discrete position samples (the WebSocket
 * pushes at 4 Hz; the track map renders at 60 fps).
 *
 * Technique: render `RENDER_BUFFER_MS` behind the latest known sample, and
 * interpolate linearly in arc-length (`s`) space between the two real
 * samples bracketing that render time — never a straight line in (x, y),
 * which would cut across the infield through a corner
 * (docs/f1-strategy-foundation.md §5). Always having a "next" sample to
 * interpolate towards (by rendering slightly in the past) is what keeps
 * the motion smooth instead of stepping forward in jumps every 250ms.
 */

export const RENDER_BUFFER_MS = 300;

export interface PositionSample {
  s: number;
  timestampMs: number;
}

/**
 * Interpolate the arc-length position between two samples at `renderTimeMs`.
 * Takes the *shortest* path around the closed loop — if the raw `s` values
 * imply crossing the start/finish line, interpolating the "long way round"
 * would be wrong.
 */
export function interpolateS(
  prev: PositionSample,
  next: PositionSample,
  renderTimeMs: number,
  lengthM: number,
): number {
  if (next.timestampMs <= prev.timestampMs) {
    return ((next.s % lengthM) + lengthM) % lengthM;
  }

  const rawT = (renderTimeMs - prev.timestampMs) / (next.timestampMs - prev.timestampMs);
  const t = Math.max(0, Math.min(1, rawT));

  let delta = next.s - prev.s;
  if (delta > lengthM / 2) {
    delta -= lengthM;
  } else if (delta < -lengthM / 2) {
    delta += lengthM;
  }

  const s = prev.s + delta * t;
  return ((s % lengthM) + lengthM) % lengthM;
}
