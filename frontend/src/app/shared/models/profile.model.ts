export type ProfileStatus = 'created' | 'running' | 'completed' | 'failed';
export type RunStatus = 'running' | 'completed' | 'failed';

export interface BusinessProfile {
  profile_uuid: string;
  name: string;
  domain: string;
  industry: string;
  description: string;
  competitors: string[];
  status: ProfileStatus;
  created_at: string;
  updated_at: string;
}

export interface CreateProfileRequest {
  name: string;
  domain: string;
  industry: string;
  description: string;
  competitors: string[];
}

export interface ProfileListResponse {
  items: BusinessProfile[];
  total: number;
}

export interface PipelineRun {
  run_uuid: string;
  profile_uuid: string;
  status: RunStatus;
  queries_discovered: number;
  queries_scored: number;
  tokens_used: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  /** Present on GET /runs and GET /runs/{uuid}; absent on the POST /run response. */
  profile_name?: string;
  profile_domain?: string;
}

export interface RunListResponse {
  items: PipelineRun[];
  total: number;
}

export interface PlatformStats {
  total_profiles: number;
  total_queries_discovered: number;
  avg_opportunity_score: number | null;
}
