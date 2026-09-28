import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Results from "../pages/Results";
import {
  jsonResponse,
  mockFetch,
  mockRoutes,
  result,
  validationReport,
} from "./helpers";

function resultsPayload(items: ReturnType<typeof result>[], total = items.length) {
  return { items, total, page: 1, page_size: 20 };
}

/** Last fetch URL hitting the results endpoint (the report refetch fires after it). */
function lastResultsUrl(spy: ReturnType<typeof mockRoutes>): string {
  const urls = spy.mock.calls.map((c) => String(c[0])).filter((u) => u.includes("/results?"));
  return urls[urls.length - 1] ?? "";
}

function setup() {
  return render(
    <MemoryRouter initialEntries={["/results/job-1"]}>
      <Routes>
        <Route path="/results/:id" element={<Results />} />
        <Route path="/results/:id/record/:resultId" element={<div>RECORD</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Results", () => {
  it("renders the validation report and results table from the API", async () => {
    mockRoutes([
      ["/validation-report", validationReport({ issues_by_field: { MISSING_WEBSITE: 2 } })],
      ["/results", resultsPayload([result()])],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("Validation report")).toBeInTheDocument());
    expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument();
    expect(screen.getByText("92 · High")).toBeInTheDocument();
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
    expect(screen.getByText("MISSING_WEBSITE")).toBeInTheDocument();
  });

  it("sends filters to the backend (server-side filtering)", async () => {
    const spy = mockRoutes([
      ["/validation-report", validationReport()],
      ["/results", resultsPayload([result()])],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "acme" } });
    fireEvent.change(screen.getByLabelText("Min score"), { target: { value: "70" } });
    fireEvent.change(screen.getByLabelText("Validation"), { target: { value: "valid" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      const url = lastResultsUrl(spy);
      expect(url).toContain("search=acme");
      expect(url).toContain("min_score=70");
      expect(url).toContain("validation_status=valid");
    });
  });

  it("paginates server-side", async () => {
    const spy = mockRoutes([
      ["/validation-report", validationReport()],
      [
        "/results",
        (url: string) => {
          const page = new URL(url, "http://x").searchParams.get("page");
          return resultsPayload([result({ id: `result-${page}` })], 40);
        },
      ],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText(/page 1 of 2/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Next →" }));
    await waitFor(() => expect(lastResultsUrl(spy)).toContain("page=2"));
  });

  it("toggles sort order on the score column", async () => {
    const spy = mockRoutes([
      ["/validation-report", validationReport()],
      ["/results", resultsPayload([result()])],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Score/ }));
    await waitFor(() => expect(lastResultsUrl(spy)).toContain("order=asc"));
  });

  it("deletes a result after confirmation and reloads", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls: string[] = [];
    mockFetch((url, init) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if ((init?.method ?? "GET") === "DELETE") return new Response(null, { status: 204 });
      if (url.includes("/validation-report")) return jsonResponse(validationReport());
      return jsonResponse(resultsPayload([result()]));
    });
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(calls).toContain("DELETE /api/research/jobs/job-1/results/result-1"),
    );
    expect(window.confirm).toHaveBeenCalled();
  });

  it("shows an empty state when nothing matches", async () => {
    mockRoutes([
      ["/validation-report", validationReport()],
      ["/results", resultsPayload([], 0)],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("No results match")).toBeInTheDocument());
  });
});
