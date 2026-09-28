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

  it("sends the configured demo delay in the job payload", async () => {
    const bodies: unknown[] = [];
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/research/jobs",
        (_url: string, init?: RequestInit) => {
          bodies.push(JSON.parse(String(init?.body)));
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
    fireEvent.change(screen.getByLabelText(/Demo delay/), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    await waitFor(() => expect(screen.getByText("JOB PAGE")).toBeInTheDocument());
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ demo_delay_ms: 0 });
  });

  it("sends enable_ai in the job payload when the AI checkbox is checked", async () => {
    const bodies: unknown[] = [];
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/research/jobs",
        (_url: string, init?: RequestInit) => {
          bodies.push(JSON.parse(String(init?.body)));
          return jsonResponse(
            { id: "job-10", status: "queued", progress_pct: 0, stage: null, industry: "SaaS" },
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
    fireEvent.click(screen.getByLabelText(/Enable AI enrichment/));
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    await waitFor(() => expect(screen.getByText("JOB PAGE")).toBeInTheDocument());
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ enable_ai: true });
  });

  it("defaults enable_ai to false when the AI checkbox is untouched", async () => {
    const bodies: unknown[] = [];
    mockRoutes([
      ["/providers/health", providersHealth()],
      [
        "/research/jobs",
        (_url: string, init?: RequestInit) => {
          bodies.push(JSON.parse(String(init?.body)));
          return jsonResponse(
            { id: "job-11", status: "queued", progress_pct: 0, stage: null, industry: "SaaS" },
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
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ enable_ai: false });
  });

  it("explains the no-key behavior in the AI hint", async () => {
    mockRoutes([["/providers/health", providersHealth()]]); // ai: disabled
    render(
      <MemoryRouter>
        <NewResearch />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/AI enrichment is not configured on the server/)).toBeInTheDocument(),
    );
  });

  it("rejects an invalid lead count without submitting", async () => {
    const spy = mockRoutes([["/providers/health", providersHealth()]]);
    render(
      <MemoryRouter>
        <NewResearch />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/Industry/), { target: { value: "SaaS" } });
    fireEvent.change(screen.getByLabelText(/Country/), { target: { value: "India" } });
    fireEvent.change(screen.getByLabelText(/Lead count/), { target: { value: "999" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    expect(
      await screen.findByText("Choose 10, 50, 100, or 500 leads."),
    ).toBeInTheDocument();
    expect(spy.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);
  });

  it("rejects an out-of-range demo delay without submitting", async () => {
    const spy = mockRoutes([[ "/providers/health", providersHealth() ]]);
    render(
      <MemoryRouter>
        <NewResearch />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/Industry/), { target: { value: "SaaS" } });
    fireEvent.change(screen.getByLabelText(/Country/), { target: { value: "India" } });
    fireEvent.change(screen.getByLabelText(/Demo delay/), { target: { value: "99999" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Research" }));
    expect(
      await screen.findByText("Demo delay must be a whole number of ms between 0 and 5000."),
    ).toBeInTheDocument();
    expect(spy.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);
  });
});
