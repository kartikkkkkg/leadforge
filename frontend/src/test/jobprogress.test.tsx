import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import JobProgress from "../pages/JobProgress";
import { jsonResponse, jobRead, mockFetch } from "./helpers";

function setup() {
  return render(
    <MemoryRouter initialEntries={["/research/job-1"]}>
      <Routes>
        <Route path="/research/:id" element={<JobProgress />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("JobProgress", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows counters and a link to results when completed", async () => {
    mockFetch(() => jsonResponse(jobRead()));
    setup();
    await waitFor(() => expect(screen.getByText("View Results")).toBeInTheDocument());
    expect(screen.getByText("Completed")).toBeInTheDocument();
    const accepted = screen.getByText("Accepted").closest(".stat-card");
    expect(accepted?.querySelector(".stat-value")?.textContent).toBe("10");
    expect(screen.queryByText(/Research in progress/)).not.toBeInTheDocument();
  });

  it("polls until a terminal state, then stops", async () => {
    vi.useFakeTimers();
    let calls = 0;
    const spy = mockFetch(() => {
      calls += 1;
      return jsonResponse(
        calls === 1
          ? jobRead({ status: "running", stage: "VALIDATE", progress_pct: 40 })
          : jobRead(),
      );
    });
    setup();
    await act(async () => {});
    expect(calls).toBe(1);
    expect(screen.getByText("Running")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await act(async () => {});
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(calls).toBe(2);

    await act(async () => {
      vi.advanceTimersByTime(30000);
    });
    await act(async () => {});
    expect(calls).toBe(2); // polling stopped at terminal state
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("shows the failure message when the job failed", async () => {
    mockFetch(() =>
      jsonResponse(jobRead({ status: "failed", stage: "STORE", progress_pct: 80, error: "disk full" })),
    );
    setup();
    await waitFor(() => expect(screen.getByText("Job failed")).toBeInTheDocument());
    expect(screen.getByText("disk full")).toBeInTheDocument();
    expect(screen.queryByText("View Results")).not.toBeInTheDocument();
  });

  it("shows a not-found error for unknown jobs", async () => {
    mockFetch(() => jsonResponse({ detail: "Research job not found", code: "job_not_found" }, 404));
    setup();
    await waitFor(() => expect(screen.getByText("Research job not found")).toBeInTheDocument());
    expect(screen.getByText("Error code: job_not_found")).toBeInTheDocument();
  });
});
