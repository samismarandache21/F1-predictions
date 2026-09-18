import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  effect,
  inject,
} from '@angular/core';

import { GeometryOut } from '../core/api-types';
import { ReplayStore } from '../core/replay.store';
import { PolylineGeometry, projectToS, sToXY } from './geometry';
import { PositionSample, RENDER_BUFFER_MS, interpolateS } from './interpolation';

interface CarBuffer {
  prev: PositionSample;
  next: PositionSample;
}

type Transform = (x: number, y: number) => [number, number];

/**
 * Canvas circuit map: the polyline plus 22 car dots in team colours,
 * interpolated along `s` at 60 fps with a ~300 ms render buffer
 * (docs/f1-strategy-foundation.md §5) rather than straight-lining between
 * raw (x, y) samples, which could cut across a corner's infield.
 */
@Component({
  selector: 'app-track-map',
  standalone: true,
  template: `<canvas #canvas class="track-canvas"></canvas>`,
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        height: 100%;
        min-height: 300px;
      }
      .track-canvas {
        width: 100%;
        height: 100%;
        display: block;
      }
    `,
  ],
})
export class TrackMapComponent implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private readonly canvasRef!: ElementRef<HTMLCanvasElement>;

  private readonly store = inject(ReplayStore);
  private ctx: CanvasRenderingContext2D | null = null;
  private rafHandle: number | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private readonly buffers = new Map<number, CarBuffer>();

  constructor() {
    // A new position sample per car arrives at whatever rate location_update
    // events come through (up to ~4 Hz from the WS push loop); each one
    // shifts the interpolation window forward by one sample.
    effect(() => {
      const frame = this.store.frame();
      const geometry = this.store.geometry();
      if (!frame || !geometry) {
        return;
      }
      this.ingestFrame(frame.positions, geometry, Date.now());
    });
  }

  ngAfterViewInit(): void {
    const canvas = this.canvasRef.nativeElement;
    this.ctx = canvas.getContext('2d');

    this.resizeObserver = new ResizeObserver(() => this.resizeCanvas());
    this.resizeObserver.observe(canvas);
    this.resizeCanvas();

    this.rafHandle = requestAnimationFrame(this.renderLoop);
  }

  ngOnDestroy(): void {
    if (this.rafHandle !== null) {
      cancelAnimationFrame(this.rafHandle);
    }
    this.resizeObserver?.disconnect();
  }

  private resizeCanvas(): void {
    const canvas = this.canvasRef.nativeElement;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
  }

  private ingestFrame(
    positions: Record<number, { x: number; y: number }>,
    geometry: GeometryOut,
    timestampMs: number,
  ): void {
    const polyline = toPolyline(geometry);
    for (const [driverStr, pos] of Object.entries(positions)) {
      const driver = Number(driverStr);
      const { s } = projectToS(polyline, pos.x, pos.y);
      const sample: PositionSample = { s, timestampMs };
      const existing = this.buffers.get(driver);
      // First sample for this car: seed both ends of the buffer with it so
      // it renders immediately instead of waiting for a second sample.
      this.buffers.set(driver, { prev: existing?.next ?? sample, next: sample });
    }
  }

  private readonly renderLoop = (): void => {
    this.draw();
    this.rafHandle = requestAnimationFrame(this.renderLoop);
  };

  private draw(): void {
    const ctx = this.ctx;
    const geometry = this.store.geometry();
    const canvas = this.canvasRef.nativeElement;
    if (!ctx || !geometry) {
      return;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const transform = computeTransform(geometry, canvas.width, canvas.height);
    drawPolyline(ctx, geometry, transform);

    const polyline = toPolyline(geometry);
    const renderTimeMs = Date.now() - RENDER_BUFFER_MS;
    const followedDriver = this.store.followedDriver();
    const carsByDriver = new Map(this.store.cars().map((car) => [car.driver, car]));

    for (const [driver, buffer] of this.buffers) {
      const s = interpolateS(buffer.prev, buffer.next, renderTimeMs, geometry.length_m);
      const { x, y } = sToXY(polyline, s);
      const [cx, cy] = transform(x, y);
      const colour = carsByDriver.get(driver)?.team_colour ?? '#999999';
      drawCar(ctx, cx, cy, driver, colour, driver === followedDriver);
    }
  }
}

function toPolyline(geometry: GeometryOut): PolylineGeometry {
  return { x: geometry.x, y: geometry.y, s: geometry.s, lengthM: geometry.length_m };
}

function computeTransform(geometry: GeometryOut, width: number, height: number): Transform {
  const minX = Math.min(...geometry.x);
  const maxX = Math.max(...geometry.x);
  const minY = Math.min(...geometry.y);
  const maxY = Math.max(...geometry.y);
  const padding = 40;
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const scale = Math.min((width - padding * 2) / spanX, (height - padding * 2) / spanY);
  const offsetX = (width - spanX * scale) / 2 - minX * scale;
  const offsetY = (height - spanY * scale) / 2 - minY * scale;
  // Canvas Y grows downward; track telemetry Y is a plain Cartesian axis,
  // so flip it to avoid rendering the circuit upside down.
  return (x: number, y: number) => [x * scale + offsetX, height - (y * scale + offsetY)];
}

function drawPolyline(ctx: CanvasRenderingContext2D, geometry: GeometryOut, transform: Transform): void {
  ctx.beginPath();
  geometry.x.forEach((x, i) => {
    const [cx, cy] = transform(x, geometry.y[i]);
    if (i === 0) {
      ctx.moveTo(cx, cy);
    } else {
      ctx.lineTo(cx, cy);
    }
  });
  ctx.closePath();
  ctx.strokeStyle = 'rgba(150, 150, 150, 0.6)';
  ctx.lineWidth = 6;
  ctx.stroke();
}

function drawCar(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  driver: number,
  colour: string,
  followed: boolean,
): void {
  ctx.beginPath();
  ctx.arc(x, y, followed ? 8 : 6, 0, Math.PI * 2);
  ctx.fillStyle = colour;
  ctx.fill();
  if (followed) {
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();
  }
  ctx.fillStyle = '#ffffff';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(String(driver), x, y - 10);
}
