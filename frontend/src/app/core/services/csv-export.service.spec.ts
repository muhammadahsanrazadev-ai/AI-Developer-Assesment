import { DiscoveredQuery } from '../../shared/models/query.model';
import { queriesToCsv } from './csv-export.service';

function query(overrides: Partial<DiscoveredQuery> = {}): DiscoveredQuery {
  return {
    query_uuid: 'q1',
    profile_uuid: 'p1',
    run_uuid: 'r1',
    query_text: 'best seo tools',
    search_keyword: 'best seo tools',
    estimated_search_volume: 25000,
    competitive_difficulty: 70,
    opportunity_score: 0.6478,
    domain_visible: false,
    visibility_position: null,
    discovered_at: '2026-11-04T00:00:00Z',
    ...overrides,
  };
}

describe('queriesToCsv', () => {
  it('writes the query columns and leaves null fields empty', () => {
    const csv = queriesToCsv([query({ domain_visible: null, estimated_search_volume: null })]);

    expect(csv).toBe(
      'query_text,estimated_search_volume,competitive_difficulty,opportunity_score,domain_visible,visibility_position\r\n' +
        'best seo tools,,70,0.6478,,',
    );
  });

  it('quotes cells that contain commas, quotes or line breaks', () => {
    const csv = queriesToCsv([query({ query_text: 'best "seo", tools\n2026' })]);

    expect(csv.split('\r\n')[1]).toBe('"best ""seo"", tools\n2026",25000,70,0.6478,false,');
  });
});
