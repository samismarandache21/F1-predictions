import { Component, computed, effect, inject, signal } from '@angular/core';

import { CarStateOut } from '../core/api-types';
import { ReplayStore } from '../core/replay.store';
import {
  DegradationHistoryTracker,
  LapPoint,
  ObservableCarState,
  fittedLinePreview,
} from './degradation-history';

const CHART_WIDTH = 260;
const CHART_HEIGHT = 140;
const PADDING = 28;
const MARGIN = 10;

interface PlottedPoint {
  x: number;
  y: number;
}

interface ChartData {
  points: (PlottedPoint & { lap: number; isCleanAir: boolean })[];
  line: [PlottedPoint, PlottedPoint] | null;
}

function toObservable(car: CarStateOut): ObservableCarState {
  return {
    driver: car.driver,
    stintNumber: car.stint_number,
    lastLap: car.last_lap,
    lastLapTimeS: car.last_lap_time_s,
    tyreAgeLaps: car.tyre_age_laps,
    lastLapIsCleanAir: car.last_lap_is_clean_air,
  };
}

/**
 * V4: per-driver degradation chart (docs/plan/phase-2.md T7) — observed
 * clean-air laps (age vs. lap time) plotted against a preview of the
 * reported car.tyre.deg_rate, with its kind (estimated/prior) badged so
 * this never claims more confidence than the backend actually has.
 *
 * Follows the same "no compiler available here" caveat as T9's frontend
 * work: written and statically checked (import/export resolution, brace
 * balance), not executed — see the T9 summary for the verification method
 * and its limits.
 */
@Component({
  selector: 'app-degradation-chart',
  standalone: true,
  template: `
    <div class="degradation-chart">
      <h2>Tyre degradation</h2>
      @if (followedCar(); as car) {
        @if (chart().points.length === 0) {
          <p class="empty">No laps recorded yet for #{{ car.driver }}.</p>
        } @else {
          <svg [attr.viewBox]="'0 0 ' + width + ' ' + height" class="chart">
            <line class="axis" [attr.x1]="PADDING" [attr.y1]="height - PADDING" [attr.x2]="width - MARGIN" [attr.y2]="height - PADDING" />
            <line class="axis" [attr.x1]="PADDING" [attr.y1]="MARGIN" [attr.x2]="PADDING" [attr.y2]="height - PADDING" />
            @if (chart().line; as line) {
              <line
                class="fit-line"
                [attr.x1]="line[0].x"
                [attr.y1]="line[0].y"
                [attr.x2]="line[1].x"
                [attr.y2]="line[1].y"
              />
            }
            @for (point of chart().points; track point.lap) {
              <circle
                [attr.cx]="point.x"
                [attr.cy]="point.y"
                [attr.r]="point.isCleanAir ? 3.5 : 2.5"
                [class.clean]="point.isCleanAir"
                [class.dirty]="!point.isCleanAir"
              />
            }
          </svg>
          <p class="axis-label">tyre age (laps) →</p>
        }
        <div class="badge-row">
          <span class="badge" [class.prior]="car.deg_rate_kind === 'prior'">
            {{ car.deg_rate_kind ?? 'no data' }}
          </span>
          <span class="deg-value">{{ formatDegRate(car.deg_rate_s_per_lap) }}</span>
        </div>
      } @else {
        <p class="empty">Select a driver in the timing tower to see their degradation.</p>
      }
    </div>
  `,
  styles: [
    `
      .degradation-chart {
        padding: 0.5rem 0.75rem;
      }
      h2 {
        font-size: 0.9rem;
        text-transform: uppercase;
        color: var(--f1-muted);
        margin: 0 0 0.5rem;
      }
      .chart {
        width: 100%;
        height: auto;
        display: block;
      }
      .axis {
        stroke: var(--f1-border);
        stroke-width: 1;
      }
      .fit-line {
        stroke: var(--f1-accent);
        stroke-width: 1.5;
        stroke-dasharray: 4 3;
      }
      circle.clean {
        fill: var(--f1-fg);
      }
      circle.dirty {
        fill: var(--f1-muted);
        opacity: 0.5;
      }
      .axis-label {
        margin: 0.15rem 0 0;
        font-size: 0.65rem;
        color: var(--f1-muted);
        text-align: right;
      }
      .badge-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.4rem;
        font-variant-numeric: tabular-nums;
      }
      .badge {
        padding: 0.05rem 0.5rem;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        background: color-mix(in srgb, var(--f1-accent) 25%, transparent);
        color: var(--f1-fg);
      }
      .badge.prior {
        background: color-mix(in srgb, var(--f1-muted) 30%, transparent);
      }
      .deg-value {
        font-size: 0.85rem;
      }
      .empty {
        color: var(--f1-muted);
      }
    `,
  ],
})
export class DegradationChartComponent {
  protected readonly width = CHART_WIDTH;
  protected readonly height = CHART_HEIGHT;
  protected readonly PADDING = PADDING;
  protected readonly MARGIN = MARGIN;

  private readonly store = inject(ReplayStore);
  private readonly tracker = new DegradationHistoryTracker();
  private readonly historyVersion = signal(0);

  protected readonly followedCar = computed<CarStateOut | null>(() => {
    const driver = this.store.followedDriver();
    if (driver == null) {
      return null;
    }
    return this.store.cars().find((car) => car.driver === driver) ?? null;
  });

  private readonly history = computed<readonly LapPoint[]>(() => {
    this.historyVersion(); // dependency only: re-read the tracker on every new frame
    const driver = this.store.followedDriver();
    return driver == null ? [] : this.tracker.historyFor(driver);
  });

  protected readonly chart = computed<ChartData>(() => {
    const points = this.history();
    const car = this.followedCar();
    if (points.length === 0) {
      return { points: [], line: null };
    }

    const line =
      car?.deg_rate_s_per_lap != null ? fittedLinePreview(points, car.deg_rate_s_per_lap) : [];

    const ages = [...points.map((p) => p.tyreAgeLaps), ...line.map((p) => p.tyreAgeLaps)];
    const times = [...points.map((p) => p.lapTimeS), ...line.map((p) => p.lapTimeS)];
    const minAge = Math.min(...ages);
    const maxAge = Math.max(...ages);
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const scaleX = (age: number): number => this.scaleX(age, minAge, maxAge);
    const scaleY = (time: number): number => this.scaleY(time, minTime, maxTime);

    return {
      points: points.map((p) => ({
        x: scaleX(p.tyreAgeLaps),
        y: scaleY(p.lapTimeS),
        lap: p.lap,
        isCleanAir: p.isCleanAir,
      })),
      line:
        line.length === 2
          ? [
              { x: scaleX(line[0].tyreAgeLaps), y: scaleY(line[0].lapTimeS) },
              { x: scaleX(line[1].tyreAgeLaps), y: scaleY(line[1].lapTimeS) },
            ]
          : null,
    };
  });

  constructor() {
    // A new WS frame (~4 Hz) may carry a newly-completed lap for any car;
    // observe all of them (cheap at 22 cars) so switching the followed
    // driver mid-replay still shows everything accumulated so far.
    effect(() => {
      const frame = this.store.frame();
      if (!frame) {
        return;
      }
      const cars = Object.values(frame.state.cars);
      for (const car of cars) {
        this.tracker.observe(toObservable(car));
      }
      this.tracker.prune(new Set(cars.map((car) => car.driver)));
      this.historyVersion.update((version) => version + 1);
    });
  }

  formatDegRate(value: number | null): string {
    if (value == null) {
      return '—';
    }
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(3)} s/lap`;
  }

  private scaleX(age: number, minAge: number, maxAge: number): number {
    const span = Math.max(maxAge - minAge, 1);
    return PADDING + ((age - minAge) / span) * (this.width - PADDING - MARGIN);
  }

  private scaleY(time: number, minTime: number, maxTime: number): number {
    const span = Math.max(maxTime - minTime, 0.05);
    return this.height - PADDING - ((time - minTime) / span) * (this.height - PADDING - MARGIN);
  }
}
