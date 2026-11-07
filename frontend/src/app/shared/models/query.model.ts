export type VisibilityStatus = 'visible' | 'not_visible' | 'unknown';

export interface DiscoveredQuery {
  query_uuid: string;
  profile_uuid: string;
  run_uuid: string;
  query_text: string;
  /** Google Ads keyword built from query_text. Null when the question cannot be measured. */
  search_keyword: string | null;
  estimated_search_volume: number | null;
  competitive_difficulty: number | null;
  opportunity_score: number | null;
  /** null when the visibility check failed; exposed by the API as status "unknown". */
  domain_visible: boolean | null;
  visibility_position: number | null;
  discovered_at: string;
}

export interface QueryFilters {
  min_score?: number | null;
  status?: VisibilityStatus | null;
  page?: number;
  per_page?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  /** The completed run the items belong to; null when the profile has no completed run. */
  run_uuid: string | null;
}

export type QueryPage = PaginatedResponse<DiscoveredQuery>;

export function visibilityStatus(query: DiscoveredQuery): VisibilityStatus {
  if (query.domain_visible === null) {
    return 'unknown';
  }
  return query.domain_visible ? 'visible' : 'not_visible';
}
