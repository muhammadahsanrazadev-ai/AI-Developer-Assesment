import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { DiscoveredQuery, QueryPage } from '../../shared/models/query.model';
import { ApiError } from './api-error';
import { QueryService } from './query.service';

const API = `${environment.apiUrl}/api/v1`;

const queryFixture: DiscoveredQuery = {
  query_uuid: 'q-1',
  profile_uuid: 'p-1',
  run_uuid: 'run-1',
  query_text: 'best ai seo tools',
  search_keyword: 'best ai seo tools',
  estimated_search_volume: 12000,
  competitive_difficulty: 60,
  opportunity_score: 0.72,
  domain_visible: false,
  visibility_position: null,
  discovered_at: '2026-11-04T18:45:00+00:00',
};

describe('QueryService', () => {
  let service: QueryService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(QueryService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('sends filters and pagination as query params', () => {
    let page: QueryPage | undefined;

    service
      .getQueries('p-1', { min_score: 0.5, status: 'not_visible', page: 2, per_page: 10 })
      .subscribe((result) => (page = result));

    const req = httpMock.expectOne((r) => r.url === `${API}/profiles/p-1/queries`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('min_score')).toBe('0.5');
    expect(req.request.params.get('status')).toBe('not_visible');
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('per_page')).toBe('10');
    req.flush({ items: [queryFixture], page: 2, per_page: 10, total: 11, total_pages: 2, run_uuid: 'run-1' });

    expect(page?.items[0].query_text).toBe('best ai seo tools');
    expect(page?.total_pages).toBe(2);
  });

  it('omits empty filters so the API applies its defaults', () => {
    service.getQueries('p-1', { min_score: 0, status: null }).subscribe();

    const req = httpMock.expectOne((r) => r.url === `${API}/profiles/p-1/queries`);
    expect(req.request.params.keys()).toEqual([]);
    req.flush({ items: [], page: 1, per_page: 20, total: 0, total_pages: 0, run_uuid: null });
  });

  it('rechecks a query with a POST and returns the updated row', () => {
    let updated: DiscoveredQuery | undefined;

    service.recheckQuery('q-1').subscribe((query) => (updated = query));

    const req = httpMock.expectOne(`${API}/queries/q-1/recheck`);
    expect(req.request.method).toBe('POST');
    req.flush({ ...queryFixture, domain_visible: true, visibility_position: 2, opportunity_score: 0.21 });
    expect(updated?.domain_visible).toBeTrue();
    expect(updated?.opportunity_score).toBe(0.21);
  });

  it('falls back to a readable message when the error body is not the API envelope', () => {
    let error: ApiError | undefined;

    service.recheckQuery('q-1').subscribe({ error: (err: ApiError) => (error = err) });

    httpMock
      .expectOne(`${API}/queries/q-1/recheck`)
      .flush('Bad Gateway', { status: 502, statusText: 'Bad Gateway' });
    expect(error?.status).toBe(502);
    expect(error?.message).toBe('The AI provider did not respond correctly. Please try again.');
  });
});
