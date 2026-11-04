import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { BusinessProfile, CreateProfileRequest } from '../../shared/models/profile.model';
import { ContentRecommendation } from '../../shared/models/recommendation.model';
import { ApiError } from './api-error';
import { ProfileService } from './profile.service';

const API = `${environment.apiUrl}/api/v1`;

const profileFixture: BusinessProfile = {
  profile_uuid: 'p-1',
  name: 'Surfer SEO',
  domain: 'surferseo.com',
  industry: 'SEO Software',
  description: 'AI-powered SEO content optimization tool',
  competitors: ['clearscope.io', 'frase.io'],
  status: 'created',
  created_at: '2026-11-04T18:44:39+00:00',
  updated_at: '2026-11-04T18:44:39+00:00',
};

describe('ProfileService', () => {
  let service: ProfileService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProfileService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates a profile with a POST to /profiles', () => {
    const payload: CreateProfileRequest = {
      name: 'Surfer SEO',
      domain: 'surferseo.com',
      industry: 'SEO Software',
      description: 'AI-powered SEO content optimization tool',
      competitors: ['clearscope.io', 'frase.io'],
    };
    let created: BusinessProfile | undefined;

    service.createProfile(payload).subscribe((profile) => (created = profile));

    const req = httpMock.expectOne(`${API}/profiles`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    req.flush(profileFixture, { status: 201, statusText: 'Created' });
    expect(created?.profile_uuid).toBe('p-1');
  });

  it('unwraps the items of GET /profiles', () => {
    let profiles: BusinessProfile[] = [];

    service.getProfiles().subscribe((items) => (profiles = items));

    httpMock.expectOne(`${API}/profiles`).flush({ items: [profileFixture], total: 1 });
    expect(profiles).toEqual([profileFixture]);
  });

  it('fetches a single profile by uuid', () => {
    let profile: BusinessProfile | undefined;

    service.getProfile('p-1').subscribe((item) => (profile = item));

    const req = httpMock.expectOne(`${API}/profiles/p-1`);
    expect(req.request.method).toBe('GET');
    req.flush(profileFixture);
    expect(profile?.domain).toBe('surferseo.com');
  });

  it('unwraps the items of GET /profiles/{uuid}/recommendations', () => {
    const recommendation: ContentRecommendation = {
      recommendation_uuid: 'r-1',
      target_query_uuid: 'q-1',
      profile_uuid: 'p-1',
      content_type: 'blog_post',
      title: 'Best AI SEO tools compared',
      rationale: 'The domain is not mentioned for this high-volume query.',
      target_keywords: ['ai seo tools'],
      priority: 'high',
      created_at: '2026-11-04T18:45:00+00:00',
    };
    let items: ContentRecommendation[] = [];

    service.getRecommendations('p-1').subscribe((result) => (items = result));

    httpMock
      .expectOne(`${API}/profiles/p-1/recommendations`)
      .flush({ items: [recommendation], total: 1, run_uuid: 'run-1' });
    expect(items).toEqual([recommendation]);
  });

  it('maps the backend error envelope to a typed ApiError', () => {
    let error: ApiError | undefined;

    service.createProfile({ ...profileFixture, domain: 'https://x.com' }).subscribe({
      error: (err: ApiError) => (error = err),
    });

    httpMock.expectOne(`${API}/profiles`).flush(
      {
        error: {
          code: 'validation_error',
          message: 'Some fields are invalid.',
          details: { domain: 'Enter the domain only, without http:// or https:// (e.g. example.com).' },
        },
      },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(error).toEqual({
      status: 400,
      code: 'validation_error',
      message: 'Some fields are invalid.',
      details: { domain: 'Enter the domain only, without http:// or https:// (e.g. example.com).' },
    });
  });

  it('reports a friendly message when the API is unreachable', () => {
    let error: ApiError | undefined;

    service.getStats().subscribe({ error: (err: ApiError) => (error = err) });

    httpMock.expectOne(`${API}/stats`).error(new ProgressEvent('error'), { status: 0 });
    expect(error?.code).toBe('network_error');
    expect(error?.message).toContain(environment.apiUrl);
  });
});
