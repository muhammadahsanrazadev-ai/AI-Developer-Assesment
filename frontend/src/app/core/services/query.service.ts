import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { DiscoveredQuery, QueryFilters, QueryPage } from '../../shared/models/query.model';
import { rethrowApiError } from './api-error';

@Injectable({ providedIn: 'root' })
export class QueryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/api/v1`;

  getQueries(profileUuid: string, filters: QueryFilters = {}): Observable<QueryPage> {
    let params = new HttpParams();
    if (filters.min_score !== null && filters.min_score !== undefined && filters.min_score > 0) {
      params = params.set('min_score', filters.min_score);
    }
    if (filters.status) {
      params = params.set('status', filters.status);
    }
    if (filters.page) {
      params = params.set('page', filters.page);
    }
    if (filters.per_page) {
      params = params.set('per_page', filters.per_page);
    }
    return this.http
      .get<QueryPage>(`${this.baseUrl}/profiles/${profileUuid}/queries`, { params })
      .pipe(catchError(rethrowApiError));
  }

  recheckQuery(queryUuid: string): Observable<DiscoveredQuery> {
    return this.http
      .post<DiscoveredQuery>(`${this.baseUrl}/queries/${queryUuid}/recheck`, {})
      .pipe(catchError(rethrowApiError));
  }
}
