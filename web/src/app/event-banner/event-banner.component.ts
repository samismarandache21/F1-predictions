import { Component, effect, inject, signal } from '@angular/core';

import { ReplayStore } from '../core/replay.store';

interface BannerMessage {
  id: number;
  text: string;
  kind: 'info' | 'warning' | 'danger';
}

const MESSAGE_LIFETIME_MS = 8000;

/**
 * SC/VSC/red and weather-change banners (T9). Retirement banners are not
 * implemented: RaceState's `retired` field is present for schema
 * forward-compatibility but never populated by the M1 builder — reliable
 * detection needs race-control cross-referencing and a DNF hazard model,
 * which is M5 scope (see f1state/state.py's docstring).
 */
@Component({
  selector: 'app-event-banner',
  standalone: true,
  template: `
    @if (messages().length > 0) {
      <div class="banner-stack">
        @for (message of messages(); track message.id) {
          <div class="banner" [class]="message.kind">{{ message.text }}</div>
        }
      </div>
    }
  `,
  styles: [
    `
      .banner-stack {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding: 0.5rem 0.75rem;
      }
      .banner {
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
      }
      .banner.info {
        background: color-mix(in srgb, var(--f1-panel) 70%, #3498db 20%);
      }
      .banner.warning {
        background: color-mix(in srgb, var(--f1-panel) 70%, #f39c12 25%);
      }
      .banner.danger {
        background: color-mix(in srgb, var(--f1-panel) 70%, var(--f1-accent) 30%);
      }
    `,
  ],
})
export class EventBannerComponent {
  private readonly store = inject(ReplayStore);
  private lastStatus: string | null = null;
  private lastRainfall: boolean | null = null;
  private nextId = 0;

  protected readonly messages = signal<BannerMessage[]>([]);

  constructor() {
    effect(() => {
      const frame = this.store.frame();
      if (!frame) {
        return;
      }
      const { track_status: status, rainfall } = frame.state;

      if (this.lastStatus !== null && status !== this.lastStatus) {
        this.push(this.statusMessage(status), this.statusKind(status));
      }
      if (this.lastRainfall !== null && rainfall && rainfall !== this.lastRainfall) {
        this.push('Rain detected at the circuit', 'warning');
      }

      this.lastStatus = status;
      this.lastRainfall = rainfall;
    });
  }

  private push(text: string, kind: BannerMessage['kind']): void {
    const message: BannerMessage = { id: this.nextId++, text, kind };
    this.messages.update((current) => [message, ...current].slice(0, 5));
    setTimeout(() => {
      this.messages.update((current) => current.filter((m) => m.id !== message.id));
    }, MESSAGE_LIFETIME_MS);
  }

  private statusMessage(status: string): string {
    switch (status) {
      case 'SC':
        return 'Safety Car deployed';
      case 'VSC':
        return 'Virtual Safety Car deployed';
      case 'RED':
        return 'Red flag';
      case 'YELLOW':
        return 'Yellow flag';
      case 'GREEN':
        return 'Track clear — green flag';
      default:
        return status;
    }
  }

  private statusKind(status: string): BannerMessage['kind'] {
    if (status === 'RED' || status === 'SC') {
      return 'danger';
    }
    if (status === 'VSC' || status === 'YELLOW') {
      return 'warning';
    }
    return 'info';
  }
}
