import { predictedPositionsByDriver, sortCarsByPosition, sortCarsByPredictedFinish } from './sort-cars';

describe('sortCarsByPosition', () => {
  it('orders cars by position ascending', () => {
    const cars = [
      { driver: 44, position: 3 },
      { driver: 1, position: 1 },
      { driver: 16, position: 2 },
    ];

    expect(sortCarsByPosition(cars).map((c) => c.driver)).toEqual([1, 16, 44]);
  });

  it('does not mutate the input array', () => {
    const cars = [
      { driver: 44, position: 2 },
      { driver: 1, position: 1 },
    ];
    const original = [...cars];

    sortCarsByPosition(cars);

    expect(cars).toEqual(original);
  });

  it('sorts cars with no position after every car with a known position', () => {
    const cars = [
      { driver: 1, position: null },
      { driver: 44, position: 1 },
      { driver: 16, position: 2 },
    ];

    expect(sortCarsByPosition(cars).map((c) => c.driver)).toEqual([44, 16, 1]);
  });

  it('orders positionless cars by driver number for a stable result', () => {
    const cars = [
      { driver: 44, position: null },
      { driver: 1, position: null },
      { driver: 16, position: null },
    ];

    expect(sortCarsByPosition(cars).map((c) => c.driver)).toEqual([1, 16, 44]);
  });

  it('handles the full 22-car grid', () => {
    const cars = Array.from({ length: 22 }, (_, i) => ({
      driver: i + 1,
      position: 22 - i,
    }));

    const sorted = sortCarsByPosition(cars);

    expect(sorted.map((c) => c.position)).toEqual(
      Array.from({ length: 22 }, (_, i) => i + 1),
    );
    expect(new Set(sorted.map((c) => c.position)).size).toBe(22);
  });
});

describe('sortCarsByPredictedFinish', () => {
  it('orders cars by predicted finish time ascending', () => {
    const cars = [
      { driver: 44, predictedFinishTimeS: 4830.0 },
      { driver: 1, predictedFinishTimeS: 4810.5 },
      { driver: 16, predictedFinishTimeS: 4820.0 },
    ];

    expect(sortCarsByPredictedFinish(cars).map((c) => c.driver)).toEqual([1, 16, 44]);
  });

  it('does not mutate the input array', () => {
    const cars = [
      { driver: 44, predictedFinishTimeS: 4820.0 },
      { driver: 1, predictedFinishTimeS: 4810.0 },
    ];
    const original = [...cars];

    sortCarsByPredictedFinish(cars);

    expect(cars).toEqual(original);
  });

  it('sorts cars with no prediction yet after every car with one', () => {
    const cars = [
      { driver: 1, predictedFinishTimeS: null },
      { driver: 44, predictedFinishTimeS: 4810.0 },
      { driver: 16, predictedFinishTimeS: 4820.0 },
    ];

    expect(sortCarsByPredictedFinish(cars).map((c) => c.driver)).toEqual([44, 16, 1]);
  });

  it('orders cars with no prediction by driver number for a stable result', () => {
    const cars = [
      { driver: 44, predictedFinishTimeS: null },
      { driver: 1, predictedFinishTimeS: null },
    ];

    expect(sortCarsByPredictedFinish(cars).map((c) => c.driver)).toEqual([1, 44]);
  });
});

describe('predictedPositionsByDriver', () => {
  it('assigns 1-based ranks in predicted finish order', () => {
    const cars = [
      { driver: 44, predictedFinishTimeS: 4830.0 },
      { driver: 1, predictedFinishTimeS: 4810.5 },
      { driver: 16, predictedFinishTimeS: 4820.0 },
    ];

    const ranks = predictedPositionsByDriver(cars);

    expect(ranks.get(1)).toBe(1);
    expect(ranks.get(16)).toBe(2);
    expect(ranks.get(44)).toBe(3);
  });

  it('omits drivers with no prediction yet', () => {
    const cars = [
      { driver: 1, predictedFinishTimeS: 4810.0 },
      { driver: 44, predictedFinishTimeS: null },
    ];

    const ranks = predictedPositionsByDriver(cars);

    expect(ranks.has(1)).toBeTrue();
    expect(ranks.has(44)).toBeFalse();
  });
});
