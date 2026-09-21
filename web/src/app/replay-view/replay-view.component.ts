import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';

import { DegradationChartComponent } from '../degradation-chart/degradation-chart.component';
import { EventBannerComponent } from '../event-banner/event-banner.component';
import { PitPanelComponent } from '../pit-panel/pit-panel.component';
import { ReplayControlsComponent } from '../replay-controls/replay-controls.component';
import { ReplayStore } from '../core/replay.store';
import { TimingTowerComponent } from '../timing-tower/timing-tower.component';
import { TrackMapComponent } from '../track-map/track-map.component';

@Component({
  selector: 'app-replay-view',
  standalone: true,
  imports: [
    DegradationChartComponent,
    EventBannerComponent,
    PitPanelComponent,
    ReplayControlsComponent,
    TimingTowerComponent,
    TrackMapComponent,
  ],
  template: `
    @if (!store.session()) {
      <p class="redirect-hint">No active replay. <a (click)="backToPicker()">Pick a session</a>.</p>
    } @else {
      <div class="replay-view">
        <app-replay-controls />
        <app-event-banner />
        <div class="layout">
          <div class="map-pane">
            <app-track-map />
          </div>
          <div class="side-pane">
            <app-timing-tower />
            <app-degradation-chart />
            <app-pit-panel />
          </div>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .redirect-hint {
        padding: 2rem;
      }
      .redirect-hint a {
        color: var(--f1-accent);
        cursor: pointer;
      }
      .replay-view {
        display: flex;
        flex-direction: column;
        height: 100vh;
      }
      .layout {
        flex: 1;
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr);
        gap: 0.5rem;
        padding: 0.5rem;
        overflow: hidden;
      }
      .map-pane {
        min-height: 300px;
      }
      .side-pane {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        min-width: 0;
        overflow: auto;
      }

      /* Responsive: stack vertically on narrow screens (T9). */
      @media (max-width: 800px) {
        .layout {
          grid-template-columns: 1fr;
          grid-template-rows: minmax(240px, 45vh) auto;
        }
      }
    `,
  ],
})
export class ReplayViewComponent {
  protected readonly store = inject(ReplayStore);
  private readonly router = inject(Router);

  backToPicker(): void {
    this.store.stop();
    void this.router.navigate(['/']);
  }
}
