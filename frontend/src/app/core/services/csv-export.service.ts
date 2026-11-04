import { Injectable } from '@angular/core';

import { DiscoveredQuery } from '../../shared/models/query.model';

const COLUMNS = [
  'query_text',
  'estimated_search_volume',
  'competitive_difficulty',
  'opportunity_score',
  'domain_visible',
  'visibility_position',
] as const;

/** One request is enough: a run discovers at most 20 queries and the API allows 100 per page. */
export const CSV_EXPORT_PAGE_SIZE = 100;

export function queriesToCsv(queries: readonly DiscoveredQuery[]): string {
  const lines = [COLUMNS.join(',')];
  for (const query of queries) {
    lines.push(
      [
        query.query_text,
        query.estimated_search_volume,
        query.competitive_difficulty,
        query.opportunity_score,
        query.domain_visible,
        query.visibility_position,
      ]
        .map(csvCell)
        .join(','),
    );
  }
  return lines.join('\r\n');
}

function csvCell(value: string | number | boolean | null): string {
  if (value === null) {
    return '';
  }
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

@Injectable({ providedIn: 'root' })
export class CsvExportService {
  downloadQueries(queries: readonly DiscoveredQuery[], filename = 'queries.csv'): void {
    const blob = new Blob([queriesToCsv(queries)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
