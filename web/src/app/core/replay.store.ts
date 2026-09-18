import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { CarStateOut, GeometryOut, ReplayControlAction, SessionOut } from './api-types';
import { ApiService } from './api.service';
import { LiveStreamService } from './live-stream.service';

/**
 * Orchestrates one active replay: session selection, starting the replay
 * (POST /replays), the WebSocket connection, circuit geometry, and which
 * driver the user is following. The track map (T9) owns its own 60 fps
 * render loop on top of `frame`/`geometry` rather than this store, since
 * that's a rendering concern, not shared application state.
 */
@Injectable({ providedIn: 'root' })
export class ReplayStore {
  private readonly api = inject(ApiService);
  private readonly liveStream = inject(LiveStreamService);

  readonly session = signal<SessionOut | null>(null);
  readonly liveId = signal<string | null>(null);
  readonly geometry = signal<GeometryOut | null>(null);
  readonly followedDriver = signal<number | null>(null);
  readonly error = signal<string | null>(null);

  readonly frame = this.liveStream.frame;
  readonly connected = this.liveStream.connected;

  readonly cars = computed<CarStateOut[]>(() => {
    const frame = this.frame();
    return frame ? Object.values(frame.state.cars) : [];
  });

  readonly followedTeam = computed<string | null>(() => {
    const driver = this.followedDriver();
    if (driver == null) {
      return null;
    }
    return this.cars().find((car) => car.driver === driver)?.team ?? null;
  });

  /** The followed driver's teammate: same team, different driver number
   * (T9: "highlights the chosen driver and their teammate"). */
  readonly followedTeammate = computed<number | null>(() => {
    const driver = this.followedDriver();
    const team = this.followedTeam();
    if (driver == null || team == null) {
      return null;
    }
    return this.cars().find((car) => car.driver !== driver && car.team === team)?.driver ?? null;
  });

  async startReplay(session: SessionOut, speed: number): Promise<void> {
    this.error.set(null);
    this.session.set(session);
    try {
      const { live_id } = await firstValueFrom(
        this.api.createReplay({ session_key: session.session_key, speed }),
      );
      this.liveId.set(live_id);
      this.liveStream.connect(live_id);

      if (session.circuit_id) {
        const geometry = await firstValueFrom(this.api.getGeometry(session.circuit_id));
        this.geometry.set(geometry);
      }
    } catch (err) {
      this.error.set('Could not start the replay. Is the backend running?');
      throw err;
    }
  }

  setFollowedDriver(driver: number | null): void {
    this.followedDriver.set(driver);
  }

  control(action: ReplayControlAction, opts?: { speed?: number; seekTs?: string }): void {
    const liveId = this.liveId();
    if (!liveId) {
      return;
    }
    this.api
      .controlReplay(liveId, { action, speed: opts?.speed, seek_ts: opts?.seekTs })
      .subscribe();
  }

  stop(): void {
    this.liveStream.disconnect();
    this.liveId.set(null);
    this.session.set(null);
    this.geometry.set(null);
    this.followedDriver.set(null);
  }
}
