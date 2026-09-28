import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type JobRead } from "../api/client";
import PipelineStages from "../components/PipelineStages";
import StatusBadge from "../components/StatusBadge";
import StatCard from "../components/StatCard";
import EmptyState from "../components/EmptyState";
import { ErrorBox, Loading } from "../components/Feedback";

const TERMINAL = new Set(["completed", "failed"]);

export default function JobProgress() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobRead | null>(null);
  const [error, setError] = useState<unknown>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const fetchJob = async () => {
      try {
        const j = await api.getJob(id);
        if (cancelled) return;
        setJob(j);
        if (TERMINAL.has(j.status) && timer.current) {
          window.clearInterval(timer.current);
          timer.current = null;
        }
      } catch (e) {
        if (!cancelled) {
          setError(e);
          if (timer.current) {
            window.clearInterval(timer.current);
            timer.current = null;
          }
        }
      }
    };

    fetchJob();
    timer.current = window.setInterval(fetchJob, 2000);
    return () => {
      cancelled = true;
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [id]);

  if (!id) {
    return (
      <div className="page">
        <h1>Research job</h1>
        <EmptyState title="No job selected" hint="Start a new research run to see progress here." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <h1>Research job</h1>
        <ErrorBox error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="page">
        <h1>Research job</h1>
        <Loading label="Loading job…" />
      </div>
    );
  }

  const terminal = TERMINAL.has(job.status);

  return (
    <div className="page">
      <div className="page-head">
        <h1>
          Research: {job.industry} <span className="muted">· {job.country}</span>
        </h1>
        <div className="page-actions">
          {job.status === "completed" ? (
            <Link to={`/results/${job.id}`} className="btn btn-primary">
              View Results
            </Link>
          ) : null}
          <Link to="/dashboard" className="btn btn-secondary">
            Dashboard
          </Link>
        </div>
      </div>

      <section className="card" aria-label="Job status">
        <div className="job-meta">
          <StatusBadge status={job.status} />
          <span className="muted">Provider: {job.provider}</span>
          <span className="muted">Requested: {job.requested_leads} leads</span>
          <span className="muted" title={job.id}>
            Job {job.id.slice(0, 8)}…
          </span>
        </div>

        <PipelineStages stage={job.stage} status={job.status} />

        <div className="progress-row">
          <div className="progress-bar" role="progressbar" aria-valuenow={job.progress_pct} aria-valuemin={0} aria-valuemax={100} aria-label="Pipeline progress">
            <div className="progress-fill" style={{ width: `${job.progress_pct}%` }} />
          </div>
          <span className="num">{job.progress_pct}%</span>
        </div>
        <p className="muted small">
          Progress reflects the current pipeline stage — it is a coarse milestone, not an exact
          time-based completion estimate.
        </p>

        {job.status === "failed" && job.error ? (
          <div className="error-box" role="alert">
            <div className="error-title">Job failed</div>
            <p className="error-message">{job.error}</p>
          </div>
        ) : null}

        {!terminal ? <Loading label="Research in progress — updating…" /> : null}
      </section>

      <section className="card" aria-label="Counters">
        <h2>Counters</h2>
        <div className="stat-grid">
          <StatCard label="Discovered" value={job.discovered} />
          <StatCard label="Processed" value={job.processed} />
          <StatCard label="Accepted" value={job.accepted} />
          <StatCard label="Duplicates" value={job.duplicates} />
          <StatCard label="Invalid" value={job.invalid} />
        </div>
      </section>
    </div>
  );
}
