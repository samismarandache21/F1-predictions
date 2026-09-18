import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { SessionOut } from '../core/api-types';
import { ApiService } from '../core/api.service';
import { ReplayStore } from '../core/replay.store';

const SPEEDS = [1, 2, 5, 10, 25, 50];

@Component({
  selector: 'app-session-picker',
  standalone: true,
  template: `
    <section class="session-picker">
      <h1>F1 Strategy</h1>
      <p class="hint">Pick a session, choose a speed, and press play.</p>

      @if (loading()) {
        <p>Loading sessions…</p>
      } @else if (error()) {
        <p class="error">{{ error() }}</p>
      } @else if (sessions().length === 0) {
        <p class="empty">
          No sessions ingested yet. Run <code>make ingest SEASON=2025 ROUND=16</code> (Monza) or
          <code>make ingest SEASON=2026 ROUND=14</code> (Madring).
        </p>
      } @else {
        <ul class="sessions">
          @for (session of sessions(); track session.session_key) {
            <li>
              <button
                type="button"
                class="session-card"
                [class.selected]="selected()?.session_key === session.session_key"
                (click)="select(session)"
              >
                <span class="name">{{ session.session_name }}</span>
                <span class="meta">
                  {{ session.season }} · {{ session.circuit_id ?? 'unknown circuit' }} ·
                  {{ session.total_laps ?? '?' }} laps
                </span>
              </button>
            </li>
          }
        </ul>

        @if (selected(); as chosen) {
          <div class="start-bar">
            <label class="speed-label">
              Speed
              <select (change)="onSpeedChange($event)">
                @for (speedOption of speeds; track speedOption) {
                  <option [value]="speedOption" [selected]="speedOption === speed()">
                    {{ speedOption }}x
                  </option>
                }
              </select>
            </label>
            <button type="button" class="play" (click)="start(chosen)" [disabled]="starting()">
              {{ starting() ? 'Starting…' : 'Play' }}
            </button>
          </div>
        }
      }
    </section>
  `,
  styles: [
    `
      .session-picker {
        max-width: 640px;
        margin: 0 auto;
        padding: 2rem 1rem;
      }
      h1 {
        margin-bottom: 0.25rem;
      }
      .hint {
        color: var(--f1-muted);
        margin-top: 0;
      }
      .error {
        color: var(--f1-accent);
      }
      .sessions {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .session-card {
        width: 100%;
        text-align: left;
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid var(--f1-border);
        background: var(--f1-panel);
        color: inherit;
        cursor: pointer;
        font: inherit;
      }
      .session-card.selected {
        border-color: var(--f1-accent);
      }
      .session-card .meta {
        color: var(--f1-muted);
        font-size: 0.85rem;
      }
      .start-bar {
        margin-top: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
      }
      .play {
        padding: 0.5rem 1.5rem;
        border-radius: 6px;
        border: none;
        background: var(--f1-accent);
        color: white;
        cursor: pointer;
        font-weight: 600;
      }
      .play:disabled {
        opacity: 0.6;
        cursor: default;
      }
    `,
  ],
})
export class SessionPickerComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly store = inject(ReplayStore);
  private readonly router = inject(Router);

  protected readonly speeds = SPEEDS;
  protected readonly sessions = signal<SessionOut[]>([]);
  protected readonly loading = signal(true);
  protected readonly starting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly selected = signal<SessionOut | null>(null);
  protected readonly speed = signal(1);

  ngOnInit(): void {
    this.api.listSessions().subscribe({
      next: (sessions) => {
        this.sessions.set(sessions);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load sessions. Is the backend running?');
        this.loading.set(false);
      },
    });
  }

  select(session: SessionOut): void {
    this.selected.set(session);
  }

  onSpeedChange(event: Event): void {
    this.speed.set(Number((event.target as HTMLSelectElement).value));
  }

  async start(session: SessionOut): Promise<void> {
    this.starting.set(true);
    try {
      await this.store.startReplay(session, this.speed());
      await this.router.navigate(['/replay']);
    } catch {
      // store.error already carries the message; the picker just stops spinning.
    } finally {
      this.starting.set(false);
    }
  }
}
