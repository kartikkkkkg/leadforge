import { ApiError } from "../api/client";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBox({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : "Something went wrong.";
  const code = error instanceof ApiError ? error.code : undefined;
  return (
    <div className="error-box" role="alert">
      <div className="error-title">Couldn&apos;t load this view</div>
      <p className="error-message">{message}</p>
      {code ? <p className="error-code">Error code: {code}</p> : null}
      {onRetry ? (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
