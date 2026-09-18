import { Component, computed, inject } from '@angular/core';

import { ReplayStore } from '../core/replay.store';
import { sortCarsByPosition } from './sort-cars';

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
    `,
  ],
})
export class TimingTowerComponent {
  protected readonly store = inject(ReplayStore);
  protected readonly sortedCars = computed(() => sortCarsByPosition(this.store.cars()));

  follow(driver: number): void {
    this.store.setFollowedDriver(this.store.followedDriver() === driver ? null : driver);
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
