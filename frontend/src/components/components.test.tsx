import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScoreBadge, { completenessBand } from "./ScoreBadge";
import StatusBadge from "./StatusBadge";
import SyntheticBadge from "./SyntheticBadge";
import PipelineStages from "./PipelineStages";

describe("completenessBand", () => {
  it("matches backend thresholds: High >= 90, Medium >= 70, Low < 70", () => {
    expect(completenessBand(100)).toBe("High");
    expect(completenessBand(90)).toBe("High");
    expect(completenessBand(89)).toBe("Medium");
    expect(completenessBand(70)).toBe("Medium");
    expect(completenessBand(69)).toBe("Low");
    expect(completenessBand(0)).toBe("Low");
  });
});

describe("ScoreBadge", () => {
  it("shows score and band", () => {
    render(<ScoreBadge score={92} />);
    expect(screen.getByText("92 · High")).toBeInTheDocument();
  });

  it("uses the bad tone for low scores", () => {
    render(<ScoreBadge score={40} />);
    expect(screen.getByText("40 · Low")).toHaveClass("tone-bad");
  });
});

describe("StatusBadge", () => {
  it("labels job statuses", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("does not reinterpret not_configured", () => {
    render(<StatusBadge status="not_configured" />);
    const el = screen.getByText("Not configured");
    expect(el).toBeInTheDocument();
    expect(el).toHaveClass("tone-warn");
  });

  it("falls back to the raw status for unknown values", () => {
    render(<StatusBadge status="weird_state" />);
    expect(screen.getByText("weird_state")).toBeInTheDocument();
  });
});

describe("SyntheticBadge", () => {
  it("is labeled Synthetic", () => {
    render(<SyntheticBadge />);
    expect(screen.getByText("Synthetic")).toBeInTheDocument();
  });
});

describe("PipelineStages", () => {
  it("marks stages before the current one done and the current one active", () => {
    render(<PipelineStages stage="VALIDATE" status="running" />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(9); // 8 stages + DONE
    expect(items[0]).toHaveClass("is-done"); // DISCOVER
    expect(items[1]).toHaveClass("is-done"); // EXTRACT
    expect(items[2]).toHaveClass("is-done"); // NORMALIZE
    expect(items[3]).toHaveClass("is-current"); // VALIDATE
    expect(items[3]).toHaveAttribute("aria-current", "step");
    expect(items[4]).not.toHaveClass("is-done");
  });

  it("renders the ENRICH stage between DEDUPLICATE and SCORE", () => {
    render(<PipelineStages stage="ENRICH" status="running" />);
    const items = screen.getAllByRole("listitem");
    const labels = items.map((i) => i.querySelector(".stage-name")?.textContent);
    expect(labels).toEqual([
      "DISCOVER",
      "EXTRACT",
      "NORMALIZE",
      "VALIDATE",
      "DEDUPLICATE",
      "ENRICH",
      "SCORE",
      "STORE",
      "DONE",
    ]);
    expect(items[5]).toHaveClass("is-current");
  });

  it("marks everything done on completion", () => {
    render(<PipelineStages stage="DONE" status="completed" />);
    for (const item of screen.getAllByRole("listitem")) {
      expect(item).toHaveClass("is-done");
    }
  });

  it("flags the failed stage", () => {
    render(<PipelineStages stage="STORE" status="failed" />);
    const items = screen.getAllByRole("listitem");
    expect(items[7]).toHaveClass("is-failed");
  });
});
