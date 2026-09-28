import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import ExportButtons from "../components/ExportButtons";
import JobProgress from "../pages/JobProgress";
import Results from "../pages/Results";
import {
  jobRead,
  jsonResponse,
  mockFetch,
  mockRoutes,
  result,
  validationReport,
} from "./helpers";

function csvExportResponse(): Response {
  return new Response("company_name,quality_score\nAcme,92\n", {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="leadforge_saas_job1.csv"',
    },
  });
}

/** Stub the browser download machinery; returns spies. */
function stubDownload() {
  const createObjectURL = vi.fn(() => "blob:mock-url");
  const revokeObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  let clicked: HTMLAnchorElement | null = null;
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked = this;
  });
  return { createObjectURL, revokeObjectURL, clicked: () => clicked };
}

function renderJobProgress() {
  return render(
    <MemoryRouter initialEntries={["/research/job-1"]}>
      <Routes>
        <Route path="/research/:id" element={<JobProgress />} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderResults() {
  return render(
    <MemoryRouter initialEntries={["/results/job-1"]}>
      <Routes>
        <Route path="/results/:id" element={<Results />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ExportButtons", () => {
  it("renders CSV and Excel buttons when the job is exportable", () => {
    render(<ExportButtons jobId="job-1" exportable />);
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download Excel" })).toBeInTheDocument();
  });

  it("is hidden when the job is not exportable", () => {
    render(<ExportButtons jobId="job-1" exportable={false} />);
    expect(screen.queryByRole("button", { name: "Download CSV" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download Excel" })).not.toBeInTheDocument();
  });

  it("calls the real export endpoint and downloads with the server filename", async () => {
    const dl = stubDownload();
    const spy = mockFetch(() => csvExportResponse());
    render(<ExportButtons jobId="job-1" exportable />);

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    await waitFor(() => expect(dl.createObjectURL).toHaveBeenCalled());
    const url = String(spy.mock.calls[0][0]);
    expect(url).toContain("/api/research/jobs/job-1/export?format=csv");
    expect(spy.mock.calls[0][1]?.method).toBe("POST");
    expect(dl.clicked()?.download).toBe("leadforge_saas_job1.csv");
    expect(dl.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("requests xlsx for the Excel button", async () => {
    stubDownload();
    const spy = mockFetch(() => csvExportResponse());
    render(<ExportButtons jobId="job-1" exportable />);

    fireEvent.click(screen.getByRole("button", { name: "Download Excel" }));

    await waitFor(() =>
      expect(String(spy.mock.calls[0][0])).toContain("format=xlsx"),
    );
  });

  it("shows a loading state and disables both buttons while downloading", async () => {
    stubDownload();
    let resolveFetch!: (r: Response) => void;
    mockFetch(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    render(<ExportButtons jobId="job-1" exportable />);

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Preparing…" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Preparing…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Download Excel" })).toBeDisabled();

    await act(async () => {
      resolveFetch(csvExportResponse());
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument(),
    );
  });

  it("shows a useful error when the export fails", async () => {
    stubDownload();
    mockFetch(() =>
      jsonResponse({ detail: "job 'job-1' is 'queued'", code: "job_not_runnable" }, 409),
    );
    render(<ExportButtons jobId="job-1" exportable />);

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("job 'job-1' is 'queued'"),
    );
    // Buttons recover after the failure.
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeEnabled();
  });
});

describe("JobProgress export buttons", () => {
  it("shows download buttons for a completed job", async () => {
    mockFetch(() => jsonResponse(jobRead()));
    renderJobProgress();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Download Excel" })).toBeInTheDocument();
  });

  it("hides download buttons while the job is running", async () => {
    mockFetch(() => jsonResponse(jobRead({ status: "running", stage: "VALIDATE" })));
    renderJobProgress();
    await waitFor(() => expect(screen.getByText("Running")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Download CSV" })).not.toBeInTheDocument();
  });

  it("hides download buttons for a failed job", async () => {
    mockFetch(() =>
      jsonResponse(jobRead({ status: "failed", error: "provider exploded" })),
    );
    renderJobProgress();
    await waitFor(() => expect(screen.getByText("Failed")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Download CSV" })).not.toBeInTheDocument();
  });
});

describe("Results export buttons", () => {
  it("shows download buttons for a completed job", async () => {
    mockRoutes([
      ["/validation-report", validationReport()],
      ["/results", { items: [result()], total: 1, page: 1, page_size: 20 }],
      ["/research/jobs/", jobRead()],
    ]);
    renderResults();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Download Excel" })).toBeInTheDocument();
    // The existing results table still renders.
    expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument();
  });

  it("hides download buttons when the job is not completed", async () => {
    mockRoutes([
      ["/validation-report", validationReport()],
      ["/results", { items: [result()], total: 1, page: 1, page_size: 20 }],
      ["/research/jobs/", jobRead({ status: "running" })],
    ]);
    renderResults();
    await waitFor(() =>
      expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: "Download CSV" })).not.toBeInTheDocument();
  });
});
