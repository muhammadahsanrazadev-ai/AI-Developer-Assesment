export type ContentType = 'blog_post' | 'landing_page' | 'faq';
export type Priority = 'high' | 'medium' | 'low';

export interface ContentRecommendation {
  recommendation_uuid: string;
  target_query_uuid: string;
  profile_uuid: string;
  content_type: ContentType;
  title: string;
  rationale: string;
  target_keywords: string[];
  priority: Priority;
  query_text: string;
  created_at: string;
}

export type RecommendationEmptyReason = 'no_completed_run' | 'all_visible' | 'generation_failed';

export interface RecommendationListResponse {
  items: ContentRecommendation[];
  total: number;
  run_uuid: string | null;
  empty_reason: RecommendationEmptyReason | null;
}

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  blog_post: 'Blog post',
  landing_page: 'Landing page',
  faq: 'FAQ',
};
