import { Component, computed, inject } from '@angular/core';

import { CarStateOut, PitStopRecordOut } from '../core/api-types';
import { ReplayStore } from '../core/replay.store';

interface PitRow {
  driver: number;
  teamColour: string | null;
  record: PitStopRecordOut;
}

@Component({
  selector: 'app-pit-panel',
  standalone: true,
  template: `
    <div class="pit-panel">
      <h2>Pit stops</h2>
      @if (rows().length === 0) {
        <p class="empty">No stops yet.</p>
      } @else {
        <table>
          <thead>
            <tr>
              <th>Car</th>
              <th>Lap</th>
              <th>Lane</th>
              <th>Stationary</th>
            </tr>
          </thead>
          <tbody>
            @for (row of rows(); track row.driver + '-' + row.record.lap) {
              <tr>
                <td>
                  <span class="driver-chip" [style.background]="row.teamColour ?? 'var(--f1-muted)'">
                    #{{ row.driver }}
                  </span>
                </td>
                <td>{{ row.record.lap }}</td>
                <td>{{ formatSeconds(row.record.lane_time_s) }}</td>
                <td>{{ formatSeconds(row.record.stationary_time_s) }}</td>
              </tr>
            }
          </tbody>
        </table>
      }
    </div>
  `,
  styles: [
    `
      .pit-panel {
        padding: 0.5rem 0.75rem;
      }
      h2 {
        font-size: 0.9rem;
        text-transform: uppercase;
        color: var(--f1-muted);
        margin: 0 0 0.5rem;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-variant-numeric: tabular-nums;
      }
      th {
        text-align: left;
        font-size: 0.75rem;
        color: var(--f1-muted);
        padding: 0.25rem 0.5rem;
      }
      td {
        padding: 0.25rem 0.5rem;
        border-bottom: 1px solid var(--f1-border);
      }
      .driver-chip {
        display: inline-block;
        padding: 0.05rem 0.45rem;
        border-radius: 999px;
        color: #fff;
        font-weight: 600;
        font-size: 0.8rem;
      }
      .empty {
        color: var(--f1-muted);
      }
    `,
  ],
})
export class PitPanelComponent {
  protected readonly store = inject(ReplayStore);

  /** One row per completed stop across every car, most recent first —
   * "stops per driver with lap, lane time and stationary time" (T9). */
  protected readonly rows = computed<PitRow[]>(() => {
    const cars: CarStateOut[] = this.store.cars();
    const rows: PitRow[] = [];
    for (const car of cars) {
      for (const record of car.pit_history) {
        rows.push({ driver: car.driver, teamColour: car.team_colour, record });
      }
    }
    return rows.sort((a, b) => b.record.lap - a.record.lap);
  });

  formatSeconds(value: number | null): string {
    return value == null ? '—' : `${value.toFixed(1)}s`;
  }
}
