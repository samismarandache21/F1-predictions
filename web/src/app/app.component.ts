import { Component, signal } from '@angular/core';

/**
 * T1 placeholder root. T9 replaces this with the session picker, replay
 * controls, track map, timing tower, pit panel and event banner
 * (docs/plan/phase-1.md).
 */
@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main class="placeholder">
      <h1>F1 Strategy</h1>
      <p>{{ status() }}</p>
    </main>
  `,
  styles: [
    `
      .placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        gap: 0.5rem;
      }
    `,
  ],
})
export class AppComponent {
  protected readonly status = signal('M1 — Watch: session picker coming up.');
}
