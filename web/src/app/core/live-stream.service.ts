import { Injectable, signal } from '@angular/core';

import { LiveFrameOut } from './api-types';
import { wsUrl } from './api.config';

/**
 * Thin wrapper around the native WebSocket connecting to
 * /live/{id}/stream (T8). Exposes the latest frame as a signal; the track
 * map (T9) buffers the last two frames itself to interpolate between them.
 */
@Injectable({ providedIn: 'root' })
export class LiveStreamService {
  private socket: WebSocket | null = null;

  readonly frame = signal<LiveFrameOut | null>(null);
  readonly connected = signal(false);

  connect(liveId: string): void {
    this.disconnect();

    const socket = new WebSocket(wsUrl(`/live/${liveId}/stream`));
    socket.onopen = () => this.connected.set(true);
    socket.onclose = () => this.connected.set(false);
    socket.onerror = () => this.connected.set(false);
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        this.frame.set(JSON.parse(event.data) as LiveFrameOut);
      } catch {
        // Malformed frame: drop it rather than crash the stream.
      }
    };
    this.socket = socket;
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
    this.connected.set(false);
    this.frame.set(null);
  }
}
