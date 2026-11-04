import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, catchError, interval, map, startWith, switchMap, takeUntil, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { PipelineRun, RunListResponse } from '../../shared/models/profile.model';
import { rethrowApiError } from './api-error';

export const RUN_POLL_INTERVAL_MS = 2000;

@Injectable({ providedIn: 'root' })
export class PipelineService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/api/v1`;

  /**
   * Shared state: the most recently finished run. Set when polling ends; the Queries,
   * Chart and Recommendations tabs watch it to reload their data.
   */
  readonly lastFinishedRun = signal<PipelineRun | null>(null);

  startRun(profileUuid: string): Observable<PipelineRun> {
    return this.http
      .post<PipelineRun>(`${this.baseUrl}/profiles/${profileUuid}/run`, {})
      .pipe(catchError(rethrowApiError));
  }

  getRun(runUuid: string): Observable<PipelineRun> {
    return this.http
      .get<PipelineRun>(`${this.baseUrl}/runs/${runUuid}`)
      .pipe(catchError(rethrowApiError));
  }

  getRuns(options: { profileUuid?: string; limit?: number } = {}): Observable<PipelineRun[]> {
    let params = new HttpParams();
    if (options.profileUuid) {
      params = params.set('profile_uuid', options.profileUuid);
    }
    if (options.limit) {
      params = params.set('limit', options.limit);
    }
    return this.http.get<RunListResponse>(`${this.baseUrl}/runs`, { params }).pipe(
      map((response) => response.items),
      catchError(rethrowApiError),
    );
  }

  /** Emits the run on every poll and completes after the first non-running status. */
  pollRun(runUuid: string): Observable<PipelineRun> {
    const finished$ = new Subject<void>();
    return interval(RUN_POLL_INTERVAL_MS).pipe(
      startWith(0),
      switchMap(() => this.getRun(runUuid)),
      tap((run) => {
        if (run.status !== 'running') {
          this.lastFinishedRun.set(run);
          queueMicrotask(() => finished$.next());
        }
      }),
      takeUntil(finished$),
    );
  }
}
