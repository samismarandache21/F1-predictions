import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  GeometryOut,
  RaceStateOut,
  ReplayControlRequest,
  ReplayCreateRequest,
  ReplayCreateResponse,
  SessionOut,
} from './api-types';
import { API_BASE_URL } from './api.config';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  listSessions(filter?: { year?: number; sessionType?: string }): Observable<SessionOut[]> {
    let params = new HttpParams();
    if (filter?.year != null) {
      params = params.set('year', filter.year);
    }
    if (filter?.sessionType) {
      params = params.set('session_type', filter.sessionType);
    }
    return this.http.get<SessionOut[]>(`${API_BASE_URL}/sessions`, { params });
  }

  getSession(sessionKey: number): Observable<SessionOut> {
    return this.http.get<SessionOut>(`${API_BASE_URL}/sessions/${sessionKey}`);
  }

  getGeometry(circuitId: string): Observable<GeometryOut> {
    return this.http.get<GeometryOut>(`${API_BASE_URL}/circuits/${circuitId}/geometry`);
  }

  createReplay(request: ReplayCreateRequest): Observable<ReplayCreateResponse> {
    return this.http.post<ReplayCreateResponse>(`${API_BASE_URL}/replays`, request);
  }

  controlReplay(liveId: string, request: ReplayControlRequest): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(
      `${API_BASE_URL}/replays/${liveId}/control`,
      request,
    );
  }

  getLiveState(liveId: string): Observable<RaceStateOut> {
    return this.http.get<RaceStateOut>(`${API_BASE_URL}/live/${liveId}/state`);
  }
}
