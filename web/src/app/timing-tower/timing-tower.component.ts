import { Component, computed, inject } from '@angular/core';

import { ReplayStore } from '../core/replay.store';
import { predictedPositionsByDriver, sortCarsByPosition } from './sort-cars';

@Component({
  selector: 'app-timing-tower',
  standalone: true,
  template: `
    <table class="timing-tower">
      <thead>
        <tr>
          <th>Pos</th>
          <th>Car</th>
          <th>Gap</th>
          <th>Interval</th>
          <th>Tyre</th>
          <th>Stops</th>
          <th>Last lap</th>
          <th>Pred. pos</th>
          <th>Pred. finish</th>
        </tr>
      </thead>
      <tbody>
        @for (car of sortedCars(); track car.driver) {
          <tr
            class="row"
            [class.followed]="car.driver === store.followedDriver()"
            [class.teammate]="car.driver === store.followedTeammate()"
            (click)="follow(car.driver)"
          >
            <td>{{ car.position ?? '—' }}</td>
            <td>
              <span class="driver-chip" [style.background]="car.team_colour ?? 'var(--f1-muted)'">
                #{{ car.driver }}
              </span>
            </td>
            <td>{{ formatGap(car.gap_to_leader_s) }}</td>
            <td>{{ formatGap(car.interval_s) }}</td>
            <td>{{ car.compound ?? '—' }}<span class="tyre-age">{{ tyreAgeSuffix(car.tyre_age_laps) }}</span></td>
            <td>{{ car.pit_stops }}</td>
            <td>{{ formatLapTime(car.last_lap_time_s) }}</td>
            <td [class.pred-gain]="predictedDelta(car) > 0" [class.pred-loss]="predictedDelta(car) < 0">
              {{ predictedPositions().get(car.driver) ?? '—' }}
            </td>
            <td>
              {{ formatLapTime(car.predicted_finish_time_s) }}
              @if (car.prediction_kind && car.deg_rate_kind) {
                <span
                  class="badge"
                  [class.prior]="car.deg_rate_kind === 'prior'"
                  [title]="degRateKindTitle(car.deg_rate_kind)"
                >
                  {{ car.deg_rate_kind }}
                </span>
              }
            </td>
          </tr>
        }
      </tbody>
    </table>
  `,
  styles: [
    `
      .timing-tower {
        width: 100%;
        border-collapse: collapse;
        font-variant-numeric: tabular-nums;
      }
      th {
        text-align: left;
        font-size: 0.75rem;
        text-transform: uppercase;
        color: var(--f1-muted);
        padding: 0.4rem 0.6rem;
        border-bottom: 1px solid var(--f1-border);
      }
      td {
        padding: 0.35rem 0.6rem;
        border-bottom: 1px solid var(--f1-border);
        white-space: nowrap;
      }
      .row {
        cursor: pointer;
      }
      .row:hover {
        background: color-mix(in srgb, var(--f1-panel) 80%, var(--f1-fg) 5%);
      }
      .row.followed {
        outline: 2px solid var(--f1-accent);
        outline-offset: -2px;
      }
      .row.teammate {
        background: color-mix(in srgb, var(--f1-panel) 70%, var(--f1-accent) 8%);
      }
      .driver-chip {
        display: inline-block;
        padding: 0.1rem 0.5rem;
        border-radius: 999px;
        color: #fff;
        font-weight: 600;
        font-size: 0.85rem;
      }
      .tyre-age {
        color: var(--f1-muted);
        margin-left: 0.25rem;
      }
      .pred-gain {
        color: #2ecc71;
      }
      .pred-loss {
        color: var(--f1-accent);
      }
      .badge {
        display: inline-block;
        margin-left: 0.35rem;
        padding: 0.02rem 0.4rem;
        border-radius: 999px;
        font-size: 0.65rem;
        text-transform: uppercase;
        background: color-mix(in srgb, var(--f1-accent) 25%, transparent);
        color: var(--f1-fg);
      }
      .badge.prior {
        background: color-mix(in srgb, var(--f1-muted) 30%, transparent);
        color: var(--f1-muted);
      }
    `,
  ],
})
export class TimingTowerComponent {
  protected readonly store = inject(ReplayStore);
  protected readonly sortedCars = computed(() => sortCarsByPosition(this.store.cars()));

  /** V5 (docs/plan/phase-2.md T7): each car's predicted running-order
   * position, ranked by car.race.finish_time_pred across all 22 drivers —
   * see sort-cars.ts's predictedPositionsByDriver for why this ranking
   * has to happen here rather than in f1engine. */
  protected readonly predictedPositions = computed(() =>
    predictedPositionsByDriver(
      this.store
        .cars()
        .map((car) => ({ driver: car.driver, predictedFinishTimeS: car.predicted_finish_time_s })),
    ),
  );

  follow(driver: number): void {
    this.store.setFollowedDriver(this.store.followedDriver() === driver ? null : driver);
  }

  degRateKindTitle(kind: string): string {
    return kind === 'prior'
      ? 'Degradation rate is a generic prior, not yet fit from actual laps'
      : 'Degradation rate fit from actual clean-air laps';
  }

  /** Positive: predicted to gain positions from here (predicted rank
   * better than current); negative: predicted to lose them. Zero/unknown
   * when either figure is missing. */
  predictedDelta(car: { driver: number; position: number | null }): number {
    const predicted = this.predictedPositions().get(car.driver);
    if (predicted == null || car.position == null) {
      return 0;
    }
    return car.position - predicted;
  }

  formatGap(value: number | null): string {
    if (value == null) {
      return '—';
    }
    return `+${value.toFixed(3)}`;
  }

  tyreAgeSuffix(age: number | null): string {
    return age == null ? '' : ` (${age})`;
  }

  formatLapTime(value: number | null): string {
    if (value == null) {
      return '—';
    }
    const minutes = Math.floor(value / 60);
    const seconds = (value % 60).toFixed(3).padStart(6, '0');
    return `${minutes}:${seconds}`;
  }
}
