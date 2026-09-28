const TONE: Record<string, string> = {
  queued: "tone-neutral",
  running: "tone-info",
  completed: "tone-ok",
  failed: "tone-bad",
  available: "tone-ok",
  configured: "tone-info",
  not_configured: "tone-warn",
  disabled: "tone-neutral",
  error: "tone-bad",
  unique: "tone-ok",
  needs_review: "tone-warn",
  valid: "tone-ok",
  invalid: "tone-bad",
  unverified: "tone-neutral",
};

const LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  available: "Available",
  configured: "Configured",
  not_configured: "Not configured",
  disabled: "Disabled",
  error: "Error",
  unique: "Unique",
  needs_review: "Needs review",
  valid: "Valid",
  invalid: "Invalid",
  unverified: "Unverified",
};

/** Status pill. Never reinterprets backend states (e.g. not_configured stays "Not configured"). */
export default function StatusBadge({ status }: { status: string }) {
  const tone = TONE[status] ?? "tone-neutral";
  const label = LABEL[status] ?? status;
  return <span className={`badge ${tone}`}>{label}</span>;
}
