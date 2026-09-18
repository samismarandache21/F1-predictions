import { PolylineGeometry, projectToS, sToXY } from './geometry';

// A 10x10 square loop, traversed anticlockwise-in-index-order starting at
// the origin. Deliberately small and exact so every expected value below
// can be hand-verified, unlike the real ~2000-point circuit polylines.
//
//   (0,10) -- s=30 --- (10,10) s=20
//     |                     |
//   s=30..40 (wrap)      s=10..20
//     |                     |
//   (0,0) -- s=0..10 --- (10,0) s=10
const SQUARE: PolylineGeometry = {
  x: [0, 10, 10, 0],
  y: [0, 0, 10, 10],
  s: [0, 10, 20, 30],
  lengthM: 40,
};

describe('projectToS', () => {
  it('projects a point exactly on the first edge', () => {
    const result = projectToS(SQUARE, 3, 0);
    expect(result.s).toBeCloseTo(3, 6);
    expect(result.distM).toBeCloseTo(0, 6);
  });

  it('projects a point exactly on the second edge', () => {
    const result = projectToS(SQUARE, 10, 3);
    expect(result.s).toBeCloseTo(13, 6);
    expect(result.distM).toBeCloseTo(0, 6);
  });

  it('projects a point exactly on the wraparound edge (last point back to the first)', () => {
    const result = projectToS(SQUARE, 0, 5);
    expect(result.s).toBeCloseTo(35, 6);
    expect(result.distM).toBeCloseTo(0, 6);
  });

  it('reports the perpendicular distance for a point off the track', () => {
    const result = projectToS(SQUARE, 3, -3);
    expect(result.s).toBeCloseTo(3, 6);
    expect(result.distM).toBeCloseTo(3, 6);
  });
});

describe('sToXY', () => {
  it('is the inverse of a point on the first edge', () => {
    const point = sToXY(SQUARE, 5);
    expect(point.x).toBeCloseTo(5, 6);
    expect(point.y).toBeCloseTo(0, 6);
  });

  it('is the inverse of a point on the wraparound edge', () => {
    const point = sToXY(SQUARE, 35);
    expect(point.x).toBeCloseTo(0, 6);
    expect(point.y).toBeCloseTo(5, 6);
  });

  it('wraps s === lengthM back to the start/finish point', () => {
    const point = sToXY(SQUARE, 40);
    expect(point.x).toBeCloseTo(0, 6);
    expect(point.y).toBeCloseTo(0, 6);
  });

  it('round-trips with projectToS for a point already on the polyline', () => {
    const original = { x: 10, y: 7 };
    const projected = projectToS(SQUARE, original.x, original.y);
    const roundTripped = sToXY(SQUARE, projected.s);
    expect(roundTripped.x).toBeCloseTo(original.x, 6);
    expect(roundTripped.y).toBeCloseTo(original.y, 6);
  });
});
