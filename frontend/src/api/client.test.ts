import { describe, expect, it } from "vitest";
import { ApiError, api } from "../api/client";
import { jsonResponse, lastFetchUrl, mockFetch, mockRoutes } from "../test/helpers";

describe("api client", () => {
  it("returns parsed JSON on success", async () => {
    mockRoutes([["/health", { status: "ok", version: "1.0.0" }]]);
    const h = await api.health();
    expect(h).toEqual({ status: "ok", version: "1.0.0" });
  });

  it("surfaces backend {detail, code} errors as ApiError", async () => {
    mockFetch(() => jsonResponse({ detail: "Research job not found", code: "job_not_found" }, 404));
    await expect(api.getJob("missing")).rejects.toMatchObject({
      name: "ApiError",
      message: "Research job not found",
      code: "job_not_found",
      status: 404,
    });
  });

  it("wraps network failures as ApiError with code network_error", async () => {
    mockFetch(() => {
      throw new TypeError("fetch failed");
    });
    const err = await api.listJobs().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("network_error");
    expect(err.status).toBe(0);
  });

  it("resolves undefined on 204 (delete)", async () => {
    mockFetch(() => new Response(null, { status: 204 }));
    await expect(api.deleteResult("job-1", "res-1")).resolves.toBeUndefined();
  });

  it("posts JSON on createJob and returns the job", async () => {
    const spy = mockFetch((_url, init) => {
      expect(init?.method).toBe("POST");
      expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
      const body = JSON.parse(String(init?.body));
      expect(body.industry).toBe("SaaS");
      return jsonResponse({ id: "job-9", status: "queued" }, 202);
    });
    const job = await api.createJob({
      industry: "SaaS",
      country: "India",
      requested_leads: 10,
    });
    expect(job.id).toBe("job-9");
    expect(lastFetchUrl(spy)).toContain("/api/research/jobs");
  });

  it("encodes results query params", async () => {
    const spy = mockRoutes([["/results", { items: [], total: 0, page: 1, page_size: 20 }]]);
    await api.listResults("job-1", {
      search: "acme",
      min_score: 70,
      sort: "quality_score",
      order: "desc",
      page: 2,
      page_size: 20,
    });
    const url = lastFetchUrl(spy);
    expect(url).toContain("/api/research/jobs/job-1/results?");
    expect(url).toContain("search=acme");
    expect(url).toContain("min_score=70");
    expect(url).toContain("sort=quality_score");
    expect(url).toContain("order=desc");
    expect(url).toContain("page=2");
  });

  it("omits empty query params", async () => {
    const spy = mockRoutes([["/results", { items: [], total: 0, page: 1, page_size: 20 }]]);
    await api.listResults("job-1", { search: "", min_score: undefined });
    expect(lastFetchUrl(spy)).not.toContain("search=");
    expect(lastFetchUrl(spy)).not.toContain("min_score=");
  });

  it("fetches the validation report", async () => {
    mockRoutes([["/validation-report", { job_id: "job-1", total: 5, valid: 4, invalid: 1, duplicates: 0, issues_by_field: { MISSING_WEBSITE: 1 } }]]);
    const r = await api.validationReport("job-1");
    expect(r.valid).toBe(4);
    expect(r.issues_by_field).toEqual({ MISSING_WEBSITE: 1 });
  });
});
