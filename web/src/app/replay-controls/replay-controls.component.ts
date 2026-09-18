import { Component, inject } from '@angular/core';

import { ReplayStore } from '../core/replay.store';

const SPEEDS = [1, 2, 5, 10, 25, 50];

@Component({
  selector: 'app-replay-controls',
  standalone: true,
  template: `
    <div class="controls">
      <button type="button" (click)="play()" [attr.aria-label]="'Play'">▶</button>
      <button type="button" (click)="pause()" [attr.aria-label]="'Pause'">⏸</button>

      <label class="speed-label">
        Speed
        <select (change)="onSpeedChange($event)">
          @for (speedOption of speeds; track speedOption) {
            <option [value]="speedOption">{{ speedOption }}x</option>
          }
        </select>
      </label>

      <span class="status" [class.connected]="store.connected()">
        {{ store.connected() ? 'Connected' : 'Disconnected' }}
      </span>
    </div>
  `,
  styles: [
    `
      .controls {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid var(--f1-border);
      }
      button {
        border: 1px solid var(--f1-border);
        background: var(--f1-panel);
        color: inherit;
        border-radius: 6px;
        padding: 0.35rem 0.75rem;
        cursor: pointer;
        font-size: 1rem;
      }
      .speed-label {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        color: var(--f1-muted);
      }
      .status {
        margin-left: auto;
        font-size: 0.85rem;
        color: var(--f1-muted);
      }
      .status.connected {
        color: #2ecc71;
      }
    `,
  ],
})
export class ReplayControlsComponent {
  protected readonly store = inject(ReplayStore);
  protected readonly speeds = SPEEDS;

  play(): void {
    this.store.control('play');
  }

  pause(): void {
    this.store.control('pause');
  }

  onSpeedChange(event: Event): void {
    const speed = Number((event.target as HTMLSelectElement).value);
    this.store.control('speed', { speed });
  }
}
