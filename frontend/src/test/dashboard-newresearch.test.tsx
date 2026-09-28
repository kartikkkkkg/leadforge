import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Dashboard from "../pages/Dashboard";
import NewResearch from "../pages/NewResearch";
import { jsonResponse, mockFetch, mockRoutes, providersHealth, jobSummary } from "./helpers";
import { Route, Routes } from "react-router-dom";

describe("Dashboard", () => {
  function statValue(label: string): string {
    const cards = Array.from(document.querySelectorAll(".stat-grid .stat-card"));
    const card = cards.find((c) => c.querySelector(".stat-label")?.textContent === label);
    return card?.querySelector(".stat-value")?.textContent ?? "";
  }

  it("shows stats aggregated from real API data", async () => {
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/research/jobs",
        {
          items: [
            jobSummary(),
            jobSummary({ id: "job-2", industry: "Logistics", status: "running", accepted: 5, duplicates: 2, invalid: 1 }),
          ],
          total: 2,
          page: 1,
          page_size: 20,
        },
      ],
    ]);
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Research jobs")).toBeInTheDocument());
    expect(statValue("Research jobs")).toBe("2");
    expect(statValue("Completed")).toBe("1");
    expect(statValue("Leads accepted")).toBe("15");
    expect(statValue("Duplicates removed")).toBe("2");
    expect(statValue("Invalid records")).toBe("1");
    expect(screen.getByText("Logistics")).toBeInTheDocument();
    expect(screen.getByText("DemoProvider:")).toBeInTheDocument();
  });

  it("shows an empty state when there are no jobs", async () => {
    mockRoutes([
      ["/providers/health", providersHealth()],
      ["/research/jobs", { items: [], total: 0, page: 1, page_size: 20 }],
    ]);
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("No research jobs yet")).toBeInTheDocument());
  });

  it("shows an error state with retry when the API fails", async () => {
    mockFetch(() => jsonResponse({ detail: "boom", code: "internal_error" }, 500));
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Couldn't load this view")).toBeInTheDocument());
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.getByText("Error code: internal_error")).toBeInTheDocument();
  });
});

describe("NewResearch", () => {
  it("validates required fields before submitting", async () => {
    const spy = mockRoutes([["/providers/health", providersHealth()]]);
    render(
      <MemoryRouter>
        <NewResearch />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    expect(await screen.findByText("Industry is required.")).toBeInTheDocument();
    expect(screen.getByText("Country is required.")).toBeInTheDocument();
    expect(spy.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);
  });

  it("creates the job and navigates to its progress page on 202", async () => {
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/research/jobs",
        (_url: string, init?: RequestInit) => {
          expect(init?.method).toBe("POST");
          return jsonResponse(
            { id: "job-9", status: "queued", progress_pct: 0, stage: null, industry: "SaaS" },
            202,
          );
        },
      ],
    ]);
    render(
      <MemoryRouter initialEntries={["/research/new"]}>
        <Routes>
          <Route path="/research/new" element={<NewResearch />} />
          <Route path="/research/:id" element={<div>JOB PAGE</div>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/Industry/), { target: { value: "SaaS" } });
    fireEvent.change(screen.getByLabelText(/Country/), { target: { value: "India" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    await waitFor(() => expect(screen.getByText("JOB PAGE")).toBeInTheDocument());
  });

  it("shows API errors (e.g. provider not configured)", async () => {
    mockFetch((url) => {
      if (url.includes("/providers/health")) return jsonResponse(providersHealth());
      return jsonResponse({ detail: "Provider 'http' is not configured", code: "provider_not_configured" }, 400);
    });
    render(
      <MemoryRouter>
        <NewResearch />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/Industry/), { target: { value: "SaaS" } });
    fireEvent.change(screen.getByLabelText(/Country/), { target: { value: "India" } });
    fireEvent.change(screen.getByLabelText(/Provider/), { target: { value: "http" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    await waitFor(() =>
      expect(screen.getByText("Provider 'http' is not configured")).toBeInTheDocument(),
    );
    expect(screen.getByText("Error code: provider_not_configured")).toBeInTheDocument();
  });
});
