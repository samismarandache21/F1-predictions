/**
 * Hand-authored types mirroring backend/f1api/src/f1api/schemas.py.
 *
 * This is a stand-in for `make types`'s generated output
 * (openapi-typescript against the FastAPI OpenAPI schema — see
 * docs/f1-strategy-foundation.md §7): Node isn't installed in this
 * environment, so the real generation step (`make types`) has not been
 * run. Once it is, this file should be deleted in favour of the generated
 * one, and importers updated — the shapes below were written to match
 * f1api/schemas.py field-for-field, but only the generated types are
 * guaranteed to stay in sync automatically.
 */

export interface SessionOut {
  session_key: number;
  season: number;
  round: number | null;
  circuit_id: string | null;
  session_type: string;
  session_name: string;
  date_start: string; // ISO 8601
  date_end: string | null;
  total_laps: number | null;
}

export interface PitStopRecordOut {
  lap: number;
  lane_time_s: number | null;
  stationary_time_s: number | null;
}

export interface CarStateOut {
  driver: number;
  team: string | null;
  team_colour: string | null;
  position: number | null;
  gap_to_leader_s: number | null;
  interval_s: number | null;
  compound: string | null;
  tyre_age_laps: number | null;
  stint_number: number;
  compounds_used: string[];
  pit_stops: number;
  pit_history: PitStopRecordOut[];
  in_pit: boolean;
  retired: boolean;
  last_lap: number | null;
  last_lap_time_s: number | null;
}

export interface RaceStateOut {
  session_key: number;
  circuit_id: string | null;
  lap: number;
  total_laps: number | null;
  track_status: string; // GREEN | YELLOW | SC | VSC | RED
  track_temp_c: number | null;
  air_temp_c: number | null;
  rainfall: boolean | null;
  cars: Record<number, CarStateOut>;
  state_version: number;
}

export interface PositionOut {
  x: number;
  y: number;
}

export interface LiveFrameOut {
  state: RaceStateOut;
  positions: Record<number, PositionOut>;
}

export interface GeometryOut {
  circuit_id: string;
  version: number;
  length_m: number;
  x: number[];
  y: number[];
  s: number[];
  sector_boundaries_s: [number, number];
  rotation_deg: number;
  pit_lane_x: number[] | null;
  pit_lane_y: number[] | null;
  pit_lane_s: number[] | null;
}

export interface ReplayCreateRequest {
  session_key: number;
  speed: number;
}

export interface ReplayCreateResponse {
  live_id: string;
}

export type ReplayControlAction = 'play' | 'pause' | 'seek' | 'speed';

export interface ReplayControlRequest {
  action: ReplayControlAction;
  speed?: number;
  seek_ts?: string; // ISO 8601
}
