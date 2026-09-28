/** Typed client for the LeadForge FastAPI backend.
 *
 * Source of truth: `backend/leadforge/schemas.py` + `backend/leadforge/api.py`.
 * All errors surface as {@link ApiError} carrying the backend's `{detail, code}`
 * shape. No fake data anywhere — every function hits the real API.
 */

export const API_BASE = "/api";

/* ------------------------------------------------------------------ */
/* Types (mirror backend schemas.py)                                   */
/* ------------------------------------------------------------------ */

export interface JobCreate {
  industry: string;
  country: string;
  region?: string | null;
  city?: string | null;
  keywords?: string | null;
  requested_leads: 10 | 50 | 100 | 500;
  provider?: string;
  enable_ai?: boolean;
  demo_delay_ms?: number;
}

export interface JobRead {
  id: string;
  industry: string;
  country: string;
  region: string | null;
  city: string | null;
  keywords: string | null;
  requested_leads: number;
  provider: string;
  enable_ai: boolean;
  demo_delay_ms: number;
  status: "queued" | "running" | "completed" | "failed";
  stage: string | null;
  /** Coarse stage milestone — NOT an exact completion estimate. */
  progress_pct: number;
  discovered: number;
  processed: number;
  accepted: number;
  duplicates: number;
  invalid: number;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface JobSummary {
  id: string;
  industry: string;
  country: string;
  region: string | null;
  requested_leads: number;
  status: JobRead["status"];
  progress_pct: number;
  accepted: number;
  duplicates: number;
  invalid: number;
  created_at: string;
  completed_at: string | null;
}

export interface JobList {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface CompanyRead {
  id: string;
  company_name: string;
  normalized_name: string | null;
  website: string | null;
  normalized_domain: string | null;
  industry: string | null;
  country: string | null;
  region: string | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  phone_normalized: string | null;
  public_email: string | null;
  linkedin_url: string | null;
  source_url: string | null;
  source_provider: string;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
}

export interface ValidationIssue {
  field: string;
  code: string;
  message: string;
}

export interface ResultRead {
  id: string;
  job_id: string;
  company: CompanyRead;
  quality_score: number;
  score_factors: Record<string, number> | null;
  validation_status: string;
  validation_issues: ValidationIssue[] | null;
  verification_status: string;
  ai_enriched: boolean;
  ai_fields: Record<string, { value: string | null; ai_derived: boolean }> | null;
  dedupe_status: string;
  duplicate_of_id: string | null;
  collected_at: string;
}

export type ResultDetail = ResultRead;

export interface ResultsPage {
  items: ResultRead[];
  total: number;
  page: number;
  page_size: number;
}

export interface ResultsQuery {
  search?: string;
  industry?: string;
  region?: string;
  city?: string;
  min_score?: number;
  max_score?: number;
  validation_status?: string;
  verification_status?: string;
  sort?: "quality_score" | "company_name" | "created_at";
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface ValidationReport {
  job_id: string;
  total: number;
  valid: number;
  invalid: number;
  duplicates: number;
  /** Stable UPPER_SNAKE issue codes -> frequency. */
  issues_by_field: Record<string, number>;
}

export interface ProviderHealth {
  name: string;
  /** available | not_configured | disabled | configured | error */
  status: string;
  detail: string;
}

export interface ProvidersHealth {
  demo: ProviderHealth;
  http: ProviderHealth;
  ai: ProviderHealth;
  database: ProviderHealth;
}

export interface HealthResponse {
  status: "ok";
  version: string;
}

/* ------------------------------------------------------------------ */
/* Errors                                                              */
/* ------------------------------------------------------------------ */

export class ApiError extends Error {
  /** Backend error code, e.g. "job_not_found". "network_error" if no response. */
  readonly code: string;
  readonly status: number;

  constructor(detail: string, code: string, status: number) {
    super(detail);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    throw new ApiError(
      `Cannot reach the LeadForge API (${err instanceof Error ? err.message : "network failure"}). Is the backend running?`,
      "network_error",
      0,
    );
  }
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const b = (body ?? {}) as { detail?: unknown; code?: unknown };
    throw new ApiError(
      typeof b.detail === "string" ? b.detail : `Request failed (${res.status})`,
      typeof b.code === "string" ? b.code : "error",
      res.status,
    );
  }
  return body as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

/* ------------------------------------------------------------------ */
/* Endpoints                                                           */
/* ------------------------------------------------------------------ */

export const api = {
  health: () => request<HealthResponse>("/health"),

  providersHealth: () => request<ProvidersHealth>("/providers/health"),

  createJob: (payload: JobCreate) =>
    request<JobRead>("/research/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  listJobs: (page = 1, pageSize = 20) =>
    request<JobList>(`/research/jobs${query({ page, page_size: pageSize })}`),

  getJob: (jobId: string) => request<JobRead>(`/research/jobs/${jobId}`),

  listResults: (jobId: string, q: ResultsQuery = {}) =>
    request<ResultsPage>(
      `/research/jobs/${jobId}/results${query(q as Record<string, string | number | undefined>)}`,
    ),

  getResult: (jobId: string, resultId: string) =>
    request<ResultDetail>(`/research/jobs/${jobId}/results/${resultId}`),

  deleteResult: (jobId: string, resultId: string) =>
    request<void>(`/research/jobs/${jobId}/results/${resultId}`, { method: "DELETE" }),

  validationReport: (jobId: string) =>
    request<ValidationReport>(`/research/jobs/${jobId}/validation-report`),
};
