import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  BusinessProfile,
  CreateProfileRequest,
  PlatformStats,
  ProfileListResponse,
} from '../../shared/models/profile.model';
import { RecommendationListResponse } from '../../shared/models/recommendation.model';
import { rethrowApiError } from './api-error';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/api/v1`;

  createProfile(payload: CreateProfileRequest): Observable<BusinessProfile> {
    return this.http
      .post<BusinessProfile>(`${this.baseUrl}/profiles`, payload)
      .pipe(catchError(rethrowApiError));
  }

  getProfiles(): Observable<BusinessProfile[]> {
    return this.http.get<ProfileListResponse>(`${this.baseUrl}/profiles`).pipe(
      map((response) => response.items),
      catchError(rethrowApiError),
    );
  }

  getProfile(profileUuid: string): Observable<BusinessProfile> {
    return this.http
      .get<BusinessProfile>(`${this.baseUrl}/profiles/${profileUuid}`)
      .pipe(catchError(rethrowApiError));
  }

  getRecommendations(profileUuid: string): Observable<RecommendationListResponse> {
    return this.http
      .get<RecommendationListResponse>(`${this.baseUrl}/profiles/${profileUuid}/recommendations`)
      .pipe(catchError(rethrowApiError));
  }

  getStats(): Observable<PlatformStats> {
    return this.http
      .get<PlatformStats>(`${this.baseUrl}/stats`)
      .pipe(catchError(rethrowApiError));
  }
}
