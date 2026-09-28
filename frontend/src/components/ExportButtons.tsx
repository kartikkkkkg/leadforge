import { useState } from "react";
import { ApiError, downloadExportFile, type ExportFormat } from "../api/client";

interface Props {
  jobId: string;
  /** Only completed jobs are exportable — the buttons stay hidden otherwise. */
  exportable: boolean;
}

/**
 * Download CSV / Download Excel buttons for a research job.
 *
 * Calls the real backend export endpoint and triggers an actual browser
 * download with the server-provided filename. The buttons are hidden unless
 * the job is in an exportable (completed) state; while a download is in
 * flight both buttons are disabled, and export failures surface inline.
 */
export default function ExportButtons({ jobId, exportable }: Props) {
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!exportable) return null;

  async function onExport(format: ExportFormat) {
    setExporting(format);
    setError(null);
    try {
      await downloadExportFile(jobId, format);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Export failed. Please try again.",
      );
    } finally {
      setExporting(null);
    }
  }

  const busy = exporting !== null;

  return (
    <span className="export-buttons">
      <button
        type="button"
        className="btn btn-secondary"
        disabled={busy}
        onClick={() => onExport("csv")}
      >
        {exporting === "csv" ? "Preparing…" : "Download CSV"}
      </button>{" "}
      <button
        type="button"
        className="btn btn-secondary"
        disabled={busy}
        onClick={() => onExport("xlsx")}
      >
        {exporting === "xlsx" ? "Preparing…" : "Download Excel"}
      </button>
      {error ? (
        <span className="export-error" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
