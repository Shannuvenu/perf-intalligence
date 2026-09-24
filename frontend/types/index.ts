export interface Site {
  site_id: number;
  name: string;
  base_url: string;
  created_at: string;
  url_count: number;
}

export type UrlCategory = "homepage" | "article" | "category" | "other";

export interface UrlItem {
  url_id: number;
  site_id: number;
  url: string;
  url_category: UrlCategory;
  enabled: boolean;
  created_at: string;
}

export interface CoreWebVitals {
  lcp_ms?: number | null;
  cls?: number | null;
  tbt_ms?: number | null;
  fcp_ms?: number | null;
  speed_index_ms?: number | null;
  total_bytes?: number | null;
}

export interface CategoryScores {
  performance?: number | null;
  accessibility?: number | null;
}

export interface PsiRun {
  run_id: number;
  url_id: number;
  run_timestamp: string;
  strategy: string;
  category_scores: CategoryScores;
  core_web_vitals: CoreWebVitals;
  run_status: "success" | "failed" | "running";
  error_message: string | null;
  created_at: string;
}

export interface RunTriggerResponse {
  run_id: number;
  run_status: "success" | "failed" | "running";
  message: string;
}

export interface StabilizedMetric {
  id: number;
  url_id: number;
  window_start: string;
  window_end: string;
  run_count: number;
  median_metrics: Record<string, number | null>;
  variability_metrics: Record<string, number>;
  flagged: boolean;
  created_at: string;
}

export type Impact = "high" | "medium" | "low";
export type Ease = "easy" | "medium" | "hard";
export type ValidationStatus = "valid" | "invalid" | "needs_review";

export interface RecommendationItem {
  candidate_id: string;
  root_cause: string;
  summary: string;
  problem_explanation?: string | null;
  user_impact?: string | null;
  fix_steps?: string[];
  evidence_refs: string[];
  evidence: string[];
  resources: string[];
  affected_audits: string[];
  impact: Impact;
  ease_of_fix: Ease;
  confidence: number;
  suggested_fix: string;
  priority: string | null;
}

export interface Recommendation {
  recommendation_id: number;
  url_id: number;
  generated_at: string;
  root_cause_groups: RecommendationItem[];
  priority_rank: string;
  source_run_ids: number[];
  model_name: string;
  prompt_version: string;
  validation_status: ValidationStatus;
  insufficient_evidence_note?: string | null;
}



export interface StrengthsResponse {
  url_id: number;
  strengths: string[];
}