import { describe, expect, it, vi } from "vitest";
import { ApiError, api, downloadExportFile } from "../api/client";
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

describe("api.exportJob", () => {
  function blobResponse(
    body: BodyInit,
    contentType: string,
    filename?: string,
    status = 200,
  ): Response {
    const headers: Record<string, string> = { "Content-Type": contentType };
    if (filename) headers["Content-Disposition"] = `attachment; filename="${filename}"`;
    return new Response(body, { status, headers });
  }

  it("posts to the export endpoint and returns blob + server filename", async () => {
    const spy = mockFetch(() =>
      blobResponse("a,b\n1,2\n", "text/csv; charset=utf-8", "leadforge_saas_ab12cd34.csv"),
    );
    const dl = await api.exportJob("job-1", "csv");
    const url = lastFetchUrl(spy);
    expect(url).toContain("/api/research/jobs/job-1/export?format=csv");
    expect(spy.mock.calls[0][1]?.method).toBe("POST");
    expect(dl.filename).toBe("leadforge_saas_ab12cd34.csv");
    expect(await dl.blob.text()).toBe("a,b\n1,2\n");
  });

  it("returns binary XLSX bytes untouched (never parsed as JSON)", async () => {
    const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x14, 0x00]);
    mockFetch(() =>
      blobResponse(
        bytes,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "leadforge_saas_ab12cd34.xlsx",
      ),
    );
    const dl = await api.exportJob("job-1", "xlsx");
    expect(dl.filename).toBe("leadforge_saas_ab12cd34.xlsx");
    expect(new Uint8Array(await dl.blob.arrayBuffer())).toEqual(bytes);
  });

  it("falls back to a default filename without Content-Disposition", async () => {
    mockFetch(() => blobResponse("a,b", "text/csv; charset=utf-8"));
    const dl = await api.exportJob("job-1", "csv");
    expect(dl.filename).toBe("leadforge_export");
  });

  it("surfaces export errors as ApiError with the backend code", async () => {
    mockFetch(() =>
      jsonResponse({ detail: "job 'job-1' is 'queued'", code: "job_not_runnable" }, 409),
    );
    await expect(api.exportJob("job-1", "csv")).rejects.toMatchObject({
      code: "job_not_runnable",
      status: 409,
    });
  });

  it("surfaces a 404 for unknown jobs", async () => {
    mockFetch(() => jsonResponse({ detail: "no research job 'nope'", code: "job_not_found" }, 404));
    await expect(api.exportJob("nope", "xlsx")).rejects.toMatchObject({
      code: "job_not_found",
      status: 404,
    });
  });
});

describe("downloadExportFile", () => {
  it("triggers a browser download with the server-provided filename", async () => {
    const createObjectURL = vi.fn(() => "blob:mock-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    let clicked: HTMLAnchorElement | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked = this;
    });
    mockFetch(() =>
      new Response("a,b\n1,2\n", {
        status: 200,
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": 'attachment; filename="leadforge_saas_ab12cd34.csv"',
        },
      }),
    );

    const filename = await downloadExportFile("job-1", "csv");

    expect(filename).toBe("leadforge_saas_ab12cd34.csv");
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clicked).not.toBeNull();
    expect(clicked!.download).toBe("leadforge_saas_ab12cd34.csv");
    expect(clicked!.href).toBe("blob:mock-url");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("propagates export failures instead of downloading", async () => {
    const createObjectURL = vi.fn(() => "blob:mock-url");
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    mockFetch(() =>
      jsonResponse({ detail: "job 'job-1' is 'queued'", code: "job_not_runnable" }, 409),
    );
    await expect(downloadExportFile("job-1", "csv")).rejects.toMatchObject({
      code: "job_not_runnable",
    });
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(click).not.toHaveBeenCalled();
  });
});
