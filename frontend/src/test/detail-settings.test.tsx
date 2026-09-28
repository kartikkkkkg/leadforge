import { render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    // never shows credentials
    expect(document.body.textContent).not.toMatch(/LEADFORGE_HTTP_API_KEY/i);
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
