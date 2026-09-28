import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import RecordDetail from "../pages/RecordDetail";
import Settings from "../pages/Settings";
import { jsonResponse, mockFetch, mockRoutes, providersHealth, result } from "./helpers";

describe("RecordDetail", () => {
  function setup() {
    return render(
      <MemoryRouter initialEntries={["/results/job-1/record/result-1"]}>
        <Routes>
          <Route path="/results/:id" element={<div>RESULTS</div>} />
          <Route path="/results/:id/record/:resultId" element={<RecordDetail />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("separates raw, normalized and derived data", async () => {
    mockRoutes([
      [
        "/results/result-1",
        result({
          validation_issues: [{ field: "website", code: "MISSING_WEBSITE", message: "No website" }],
        }),
      ],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Company" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Normalized" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Derived" })).toBeInTheDocument();
    expect(screen.getByText("acme.example.com")).toBeInTheDocument();
    expect(screen.getByText("has website")).toBeInTheDocument();
    expect(screen.getByText("MISSING_WEBSITE")).toBeInTheDocument();
    expect(screen.getByText(/validation is not verification/)).toBeInTheDocument();
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
  });

  it("shows an error for unknown results", async () => {
    mockFetch(() => jsonResponse({ detail: "Result not found", code: "result_not_found" }, 404));
    setup();
    await waitFor(() => expect(screen.getByText("Result not found")).toBeInTheDocument());
    expect(screen.getByText("Error code: result_not_found")).toBeInTheDocument();
  });

  it("renders the AI-derived section with tagged fields when enriched", async () => {
    mockRoutes([
      [
        "/results/result-1",
        result({
          ai_enriched: true,
          ai_fields: {
            summary: { value: "An AI-generated summary.", ai_derived: true },
            industry_suggestion: { value: "Jewelry Stores", ai_derived: true },
          },
        }),
      ],
    ]);
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: /AI-derived/ })).toBeInTheDocument();
    expect(screen.getByText("not verified")).toBeInTheDocument();
    expect(screen.getByText("An AI-generated summary.")).toBeInTheDocument();
    expect(screen.getAllByText("AI")).not.toHaveLength(0);
  });

  it("hides the AI-derived section when not enriched", async () => {
    mockRoutes([["/results/result-1", result({ ai_enriched: false, ai_fields: null })]]);
    setup();
    await waitFor(() => expect(screen.getByText("Acme SaaS Pvt Ltd")).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: /AI-derived/ })).not.toBeInTheDocument();
  });
});

describe("Settings", () => {
  it("renders provider health without reinterpreting states", async () => {
    mockRoutes([["/providers/health", providersHealth()]]);
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("DemoProvider")).toBeInTheDocument());
    expect(screen.getAllByText("Available")).toHaveLength(2); // demo + database
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(screen.getAllByText("Disabled")).toHaveLength(2); // ai badge + AI enrichment indicator
    expect(screen.getByText(/AI enrichment:/)).toHaveTextContent(/Disabled/);
    // never shows credentials
    expect(document.body.textContent).not.toMatch(/LEADFORGE_HTTP_API_KEY/i);
  });

  it("shows the AI enrichment indicator as Enabled when configured", async () => {
    mockRoutes([
      [
        "/providers/health",
        providersHealth({
          ai: { name: "AI provider", status: "configured", detail: "Key set." },
        }),
      ],
    ]);
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/AI enrichment:/)).toBeInTheDocument());
    expect(screen.getByText(/AI enrichment:/)).toHaveTextContent(/Enabled/);
  });

  it("shows an error state when health check fails", async () => {
    mockFetch(() => {
      throw new TypeError("fetch failed");
    });
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Couldn't load this view")).toBeInTheDocument());
    expect(screen.getByText("Error code: network_error")).toBeInTheDocument();
  });
});

describe("Settings demo controls", () => {
  const resetResponse = {
    jobs_deleted: 2,
    results_deleted: 18,
    rejected_records_deleted: 3,
    companies_deleted: 25,
    reseeded: false,
    companies: 0,
  };

  function setupDemo(routes: [string, unknown][] = []) {
    const spy = mockRoutes([
      ["/providers/health", providersHealth()],
      ["/demo/seed", { companies: 100 }],
      ["/demo/reset", resetResponse],
      ...routes,
    ]);
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    return spy;
  }

  it("seeds the demo dataset and shows the resulting count", async () => {
    const spy = setupDemo();
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Seed demo data" }));
    await waitFor(() =>
      expect(
        screen.getByText("Seeded 100 synthetic companies into the demo dataset."),
      ).toBeInTheDocument(),
    );
    const seedCalls = spy.mock.calls.filter(
      ([url, init]) => String(url).includes("/demo/seed") && init?.method === "POST",
    );
    expect(seedCalls).toHaveLength(1);
  });

  it("requires confirmation before resetting, then shows deletion counts", async () => {
    const spy = setupDemo();
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Reset demo data" }));
    // no request yet — confirmation first
    expect(
      spy.mock.calls.some(([url]) => String(url).includes("/demo/reset")),
    ).toBe(false);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes, reset" }));
    await waitFor(() =>
      expect(
        screen.getByText(/Reset complete — deleted 2 jobs, 18 results, 3 rejected records/),
      ).toBeInTheDocument(),
    );
  });

  it("cancels the reset without calling the API", async () => {
    const spy = setupDemo();
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Reset demo data" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(
      spy.mock.calls.some(([url]) => String(url).includes("/demo/reset")),
    ).toBe(false);
  });

  it("supports reset + reseed", async () => {
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/demo/reset",
        { ...resetResponse, reseeded: true, companies: 100 },
      ],
    ]);
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Reset + reseed" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, reset" }));
    await waitFor(() =>
      expect(screen.getByText(/Re-seeded 100 synthetic companies/)).toBeInTheDocument(),
    );
  });

  it("shows an error state when seeding fails", async () => {
    mockRoutes([
      ["/providers/health", providersHealth()],
      ["/demo/seed", jsonResponse({ detail: "DB unavailable", code: "internal_error" }, 500)],
    ]);
    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Seed demo data" }));
    await waitFor(() => expect(screen.getByText("DB unavailable")).toBeInTheDocument());
    expect(screen.getByText("Error code: internal_error")).toBeInTheDocument();
  });

  it("labels demo data as synthetic", async () => {
    setupDemo();
    await waitFor(() => expect(screen.getByText("Demo data")).toBeInTheDocument());
    const section = screen.getByRole("region", { name: "Demo data" });
    expect(section.textContent).toMatch(/synthetic/i);
  });
});
