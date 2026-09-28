import { vi } from "vitest";
import type {
  CompanyRead,
  JobRead,
  JobSummary,
  ProvidersHealth,
  ResultRead,
  ValidationReport,
} from "../api/client";

/* ---------------- fixtures ---------------- */

export function company(overrides: Partial<CompanyRead> = {}): CompanyRead {
  return {
    id: "company-1",
    company_name: "Acme SaaS Pvt Ltd",
    normalized_name: "acme saas pvt ltd",
    website: "https://acme.example.com",
    normalized_domain: "acme.example.com",
    industry: "SaaS",
    country: "India",
    region: "Karnataka",
    city: "Bengaluru",
    address: "1 Main St, Bengaluru",
    phone: "+91-555-0101",
    phone_normalized: "+915550101",
    public_email: "hello@acme.example.com",
    linkedin_url: "https://linkedin.com/company/acme",
    source_url: "https://acme.example.com",
    source_provider: "demo",
    is_synthetic: true,
    created_at: "2026-09-28T10:00:00",
    updated_at: "2026-09-28T10:00:00",
    ...overrides,
  };
}

export function result(overrides: Partial<ResultRead> = {}): ResultRead {
  return {
    id: "result-1",
    job_id: "job-1",
    company: company(),
    quality_score: 92,
    score_factors: { has_website: 20, has_email: 15 },
    validation_status: "valid",
    validation_issues: [],
    verification_status: "unverified",
    ai_enriched: false,
    ai_fields: null,
    dedupe_status: "unique",
    duplicate_of_id: null,
    collected_at: "2026-09-28T10:05:00",
    ...overrides,
  };
}

export function jobRead(overrides: Partial<JobRead> = {}): JobRead {
  return {
    id: "job-1",
    industry: "SaaS",
    country: "India",
    region: null,
    city: null,
    keywords: null,
    requested_leads: 10,
    provider: "demo",
    enable_ai: false,
    demo_delay_ms: 0,
    status: "completed",
    stage: "DONE",
    progress_pct: 100,
    discovered: 10,
    processed: 10,
    accepted: 10,
    duplicates: 0,
    invalid: 0,
    error: null,
    created_at: "2026-09-28T10:00:00",
    completed_at: "2026-09-28T10:01:00",
    ...overrides,
  };
}

export function jobSummary(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: "job-1",
    industry: "SaaS",
    country: "India",
    region: null,
    requested_leads: 10,
    status: "completed",
    progress_pct: 100,
    accepted: 10,
    duplicates: 0,
    invalid: 0,
    created_at: "2026-09-28T10:00:00",
    completed_at: "2026-09-28T10:01:00",
    ...overrides,
  };
}

export function providersHealth(): ProvidersHealth {
  return {
    demo: { name: "DemoProvider", status: "available", detail: "Ready (offline synthetic data)." },
    http: { name: "HTTP provider", status: "not_configured", detail: "LEADFORGE_HTTP_BASE_URL is not set." },
    ai: { name: "AI provider", status: "disabled", detail: "AI enrichment disabled." },
    database: { name: "Database", status: "available", detail: "Connected (sqlite)." },
  };
}

export function validationReport(overrides: Partial<ValidationReport> = {}): ValidationReport {
  return {
    job_id: "job-1",
    total: 10,
    valid: 10,
    invalid: 0,
    duplicates: 0,
    issues_by_field: {},
    ...overrides,
  };
}

/* ---------------- fetch mocking ---------------- */

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function mockFetch(
  handler: (url: string, init?: RequestInit) => Response | Promise<Response>,
) {
  const spy = vi.fn(async (url: string, init?: RequestInit) => handler(url, init));
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Route-based mock: match on URL substring. */
export function mockRoutes(routes: [string, unknown | ((url: string, init?: RequestInit) => unknown)][], fallbackStatus = 404) {
  return mockFetch((url, init) => {
    for (const [match, body] of routes) {
      if (url.includes(match)) {
        const resolved = typeof body === "function" ? body(url, init) : body;
        if (resolved instanceof Response) return resolved;
        return jsonResponse(resolved);
      }
    }
    return jsonResponse({ detail: "Not found", code: "not_found" }, fallbackStatus);
  });
}

export function lastFetchUrl(spy: ReturnType<typeof mockFetch>): string {
  return String(spy.mock.calls[spy.mock.calls.length - 1][0]);
}
