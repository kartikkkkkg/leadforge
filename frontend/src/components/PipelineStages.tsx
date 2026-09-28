/** Pipeline progress stepper. Stages mirror the backend runner:
 *  DISCOVER → NORMALIZE → VALIDATE → DEDUPLICATE → SCORE → STORE → DONE.
 */
const STAGES = [
  "DISCOVER",
  "NORMALIZE",
  "VALIDATE",
  "DEDUPLICATE",
  "SCORE",
  "STORE",
  "DONE",
] as const;

export default function PipelineStages({
  stage,
  status,
}: {
  stage: string | null;
  status: "queued" | "running" | "completed" | "failed";
}) {
  const currentIdx = stage ? STAGES.indexOf(stage as (typeof STAGES)[number]) : -1;
  const failed = status === "failed";
  return (
    <ol className="stages" aria-label="Pipeline progress">
      {STAGES.map((s, i) => {
        const done = currentIdx > i || status === "completed";
        const current = !failed && i === currentIdx && status !== "completed";
        const failedHere = failed && i === currentIdx;
        return (
          <li
            key={s}
            className={["stage", done ? "is-done" : "", current ? "is-current" : "", failedHere ? "is-failed" : ""]
              .join(" ")
              .trim()}
            aria-current={current ? "step" : undefined}
          >
            <span className="stage-dot" aria-hidden="true">
              {done ? "✓" : failedHere ? "!" : i + 1}
            </span>
            <span className="stage-name">{s}</span>
          </li>
        );
      })}
    </ol>
  );
}
