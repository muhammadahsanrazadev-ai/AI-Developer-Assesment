import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, discardPeriodicTasks, fakeAsync, flushMicrotasks, tick } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { PipelineRun } from '../../shared/models/profile.model';
import { ApiError } from './api-error';
import { PipelineService, RUN_POLL_INTERVAL_MS } from './pipeline.service';

const API = `${environment.apiUrl}/api/v1`;

function run(overrides: Partial<PipelineRun> = {}): PipelineRun {
  return {
    run_uuid: 'run-1',
    profile_uuid: 'p-1',
    status: 'running',
    queries_discovered: 0,
    queries_scored: 0,
    tokens_used: 0,
    error_message: null,
    started_at: '2026-11-04T18:44:40+00:00',
    completed_at: null,
    ...overrides,
  };
}

describe('PipelineService', () => {
  let service: PipelineService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PipelineService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('starts a run with a POST to /profiles/{uuid}/run', () => {
    let started: PipelineRun | undefined;

    service.startRun('p-1').subscribe((result) => (started = result));

    const req = httpMock.expectOne(`${API}/profiles/p-1/run`);
    expect(req.request.method).toBe('POST');
    req.flush(run(), { status: 202, statusText: 'Accepted' });
    expect(started?.status).toBe('running');
  });

  it('passes the run list filters as params and unwraps items', () => {
    let runs: PipelineRun[] = [];

    service.getRuns({ profileUuid: 'p-1', limit: 1 }).subscribe((items) => (runs = items));

    const req = httpMock.expectOne((r) => r.url === `${API}/runs`);
    expect(req.request.params.get('profile_uuid')).toBe('p-1');
    expect(req.request.params.get('limit')).toBe('1');
    req.flush({ items: [run({ status: 'completed' })], total: 1 });
    expect(runs.length).toBe(1);
  });

  it('surfaces a 409 when a run is already in progress', () => {
    let error: ApiError | undefined;

    service.startRun('p-1').subscribe({ error: (err: ApiError) => (error = err) });

    httpMock.expectOne(`${API}/profiles/p-1/run`).flush(
      {
        error: {
          code: 'pipeline_already_running',
          message: 'A pipeline run is already in progress for this profile.',
          details: {},
        },
      },
      { status: 409, statusText: 'Conflict' },
    );
    expect(error?.status).toBe(409);
    expect(error?.code).toBe('pipeline_already_running');
  });

  it('polls until the run finishes, then completes and shares the finished run', fakeAsync(() => {
    const emitted: PipelineRun[] = [];
    let completed = false;

    service.pollRun('run-1').subscribe({
      next: (value) => emitted.push(value),
      complete: () => (completed = true),
    });

    httpMock.expectOne(`${API}/runs/run-1`).flush(run({ queries_discovered: 15 }));
    tick(RUN_POLL_INTERVAL_MS);
    httpMock.expectOne(`${API}/runs/run-1`).flush(run({ queries_discovered: 15, queries_scored: 8 }));
    expect(service.lastFinishedRun()).toBeNull();

    tick(RUN_POLL_INTERVAL_MS);
    const finished = run({ status: 'completed', queries_discovered: 15, queries_scored: 15, tokens_used: 10500 });
    httpMock.expectOne(`${API}/runs/run-1`).flush(finished);
    flushMicrotasks();

    expect(emitted.map((value) => value.queries_scored)).toEqual([0, 8, 15]);
    expect(completed).toBeTrue();
    expect(service.lastFinishedRun()).toEqual(finished);

    tick(RUN_POLL_INTERVAL_MS * 3);
    httpMock.expectNone(`${API}/runs/run-1`);
    discardPeriodicTasks();
  }));
});
