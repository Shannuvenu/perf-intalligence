import type {
  PsiRun,
  Recommendation,
  RecommendationItem,
  RunTriggerResponse,
  Site,
  StabilizedMetric,
  StrengthsResponse,
  UrlCategory,
  UrlItem,
} from "@/types";

// Next.js inlines NEXT_PUBLIC_* vars at BUILD time, which the browser needs
// (it can only reach the backend via a published host port, e.g.
// http://localhost:8000). Server components, however, run inside the
// frontend's own container/process and - in Docker Compose - must reach the
// backend via its internal service name (e.g. http://backend:8000), which
// isn't known until the container actually starts. So: server-side code
// reads API_INTERNAL_BASE_URL (a normal, non-inlined runtime env var) first,
// falling back to the public URL; the browser only ever sees the public one.
const API_BASE_URL =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = res.statusText;

    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // Response wasn't JSON - fall back to statusText.
    }

    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  // ---------------------------------------------------------------------------
  // Sites
  // ---------------------------------------------------------------------------

  listSites: () =>
    request<Site[]>("/api/sites"),

  createSite: (name: string, base_url: string) =>
    request<Site>("/api/sites", {
      method: "POST",
      body: JSON.stringify({
        name,
        base_url,
      }),
    }),

  getSite: (siteId: number) =>
    request<Site>(`/api/sites/${siteId}`),

  // ---------------------------------------------------------------------------
  // URLs
  // ---------------------------------------------------------------------------

  listUrls: (siteId: number) =>
    request<UrlItem[]>(`/api/sites/${siteId}/urls`),

  getUrl: (urlId: number) =>
    request<UrlItem>(`/api/urls/${urlId}`),

  createUrl: (
    siteId: number,
    url: string,
    url_category: UrlCategory
  ) =>
    request<UrlItem>(`/api/sites/${siteId}/urls`, {
      method: "POST",
      body: JSON.stringify({
        url,
        url_category,
        enabled: true,
      }),
    }),

  // ---------------------------------------------------------------------------
  // Runs
  // ---------------------------------------------------------------------------

  triggerRun: (urlId: number) =>
    request<RunTriggerResponse>(
      `/api/urls/${urlId}/run`,
      {
        method: "POST",
      }
    ),

  runFullAnalysis: (urlId: number) =>
    request<{
      runs_completed: number;
      successful_runs: number;
      stabilized: boolean;
      analyzed: boolean;
      message: string;
    }>(
      `/api/urls/${urlId}/run-full-analysis`,
      {
        method: "POST",
      }
    ),

  listRuns: (urlId: number) =>
    request<PsiRun[]>(`/api/urls/${urlId}/runs`),

  // ---------------------------------------------------------------------------
  // Stabilization
  // ---------------------------------------------------------------------------

  stabilize: (urlId: number) =>
    request<StabilizedMetric>(
      `/api/urls/${urlId}/stabilize`,
      {
        method: "POST",
        body: JSON.stringify({}),
      }
    ),

  getStabilized: (urlId: number) =>
    request<StabilizedMetric>(
      `/api/urls/${urlId}/stabilized`
    ),

  // ---------------------------------------------------------------------------
  // Strengths
  // ---------------------------------------------------------------------------

  getStrengths: (urlId: number) =>
    request<StrengthsResponse>(
      `/api/urls/${urlId}/strengths`
    ),

  // ---------------------------------------------------------------------------
  // Recommendations
  // ---------------------------------------------------------------------------

  analyze: (urlId: number) =>
    request<Recommendation>(
      `/api/urls/${urlId}/analyze`,
      {
        method: "POST",
      }
    ),

  listRecommendations: (urlId: number) =>
    request<Recommendation[]>(
      `/api/urls/${urlId}/recommendations`
    ),

  // ---------------------------------------------------------------------------
  // Quick Analyze
  // ---------------------------------------------------------------------------

  quickAnalyze: (report: unknown) =>
    request<QuickAnalyzeResult>(
      "/api/quick-analyze",
      {
        method: "POST",
        body: JSON.stringify(report),
      }
    ),

  quickAnalyzeUrl: (url: string) =>
    request<QuickAnalyzeResult>(
      "/api/quick-analyze/url",
      {
        method: "POST",
        body: JSON.stringify({
          url,
        }),
      }
    ),

  // ---------------------------------------------------------------------------
  // Google Apps Script Monitoring
  // ---------------------------------------------------------------------------

  getMonitoringUrls: () =>
    request<MonitoringUrlsResponse>(
      "/api/monitoring/urls"
    ),
};

// -----------------------------------------------------------------------------
// Quick Analyze Types
// -----------------------------------------------------------------------------

export interface QuickAnalyzeResult {
  recommendations: RecommendationItem[];
  model_name: string;
  note: string | null;

  category_scores?: {
    performance?: number | null;
    accessibility?: number | null;
  } | null;

  core_web_vitals?: Record<
    string,
    number | null
  > | null;
}

// -----------------------------------------------------------------------------
// Google Apps Script Monitoring Types
// -----------------------------------------------------------------------------

export interface MonitoringUrl {
  brand: string;
  url_type: string;
  url: string;
  enabled: boolean;
}

export interface MonitoringUrlsResponse {
  success: boolean;
  count: number;
  urls: MonitoringUrl[];
}

// -----------------------------------------------------------------------------
// API Error
// -----------------------------------------------------------------------------

export { ApiError };