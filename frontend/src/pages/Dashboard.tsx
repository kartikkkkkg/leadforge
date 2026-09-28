import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type JobList, type ProvidersHealth } from "../api/client";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import { ErrorBox, Loading } from "../components/Feedback";

export default function Dashboard() {
  const [jobs, setJobs] = useState<JobList | null>(null);
  const [health, setHealth] = useState<ProvidersHealth | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listJobs(1, 10), api.providersHealth()])
      .then(([j, h]) => {
        if (!cancelled) {
          setJobs(j);
          setHealth(h);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="page">
        <h1>Dashboard</h1>
        <ErrorBox error={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }
  if (!jobs) {
    return (
      <div className="page">
        <h1>Dashboard</h1>
        <Loading label="Loading dashboard…" />
      </div>
    );
  }

  const completed = jobs.items.filter((j) => j.status === "completed").length;
  const accepted = jobs.items.reduce((n, j) => n + j.accepted, 0);
  const duplicates = jobs.items.reduce((n, j) => n + j.duplicates, 0);
  const invalid = jobs.items.reduce((n, j) => n + j.invalid, 0);

  return (
    <div className="page">
      <div className="page-head">
        <h1>Dashboard</h1>
        <Link to="/research/new" className="btn btn-primary">
          + New Research
        </Link>
      </div>

      <div className="stat-grid">
        <StatCard label="Research jobs" value={jobs.total} sub="all time" />
        <StatCard label="Completed" value={completed} sub="in recent list" />
        <StatCard label="Leads accepted" value={accepted} sub="in recent jobs" />
        <StatCard label="Duplicates removed" value={duplicates} sub="in recent jobs" />
        <StatCard label="Invalid records" value={invalid} sub="in recent jobs" />
      </div>

      {health ? (
        <section className="card" aria-label="Provider health">
          <h2>Provider health</h2>
          <div className="health-strip">
            {(Object.keys(health) as (keyof ProvidersHealth)[]).map((k) => (
              <span key={k} className="health-item">
                {health[k].name}: <StatusBadge status={health[k].status} />
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="card" aria-label="Recent research jobs">
        <h2>Recent research jobs</h2>
        {jobs.items.length === 0 ? (
          <EmptyState
            title="No research jobs yet"
            hint="Start your first lead research run — it takes seconds with the demo provider."
            action={
              <Link to="/research/new" className="btn btn-primary">
                Start Research
              </Link>
            }
          />
        ) : (
          <DataTable
            columns={[
              {
                key: "what",
                header: "Research",
                render: (j) => (
                  <>
                    <div className="cell-main">
                      <Link to={`/research/${j.id}`}>{j.industry}</Link>
                    </div>
                    <div className="muted">{[j.country, j.region].filter(Boolean).join(" · ")}</div>
                  </>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (j) => <StatusBadge status={j.status} />,
              },
              {
                key: "progress",
                header: "Progress",
                render: (j) => <span className="num">{j.progress_pct}%</span>,
                className: "num",
              },
              {
                key: "accepted",
                header: "Accepted",
                render: (j) => j.accepted,
                className: "num",
              },
              {
                key: "dup",
                header: "Duplicates",
                render: (j) => j.duplicates,
                className: "num",
              },
              {
                key: "invalid",
                header: "Invalid",
                render: (j) => j.invalid,
                className: "num",
              },
              {
                key: "created",
                header: "Created",
                render: (j) => new Date(j.created_at).toLocaleString(),
              },
              {
                key: "actions",
                header: "",
                render: (j) =>
                  j.status === "completed" ? (
                    <Link to={`/results/${j.id}`} className="btn btn-secondary btn-sm">
                      Results
                    </Link>
                  ) : (
                    <Link to={`/research/${j.id}`} className="btn btn-secondary btn-sm">
                      Progress
                    </Link>
                  ),
              },
            ]}
            rows={jobs.items}
          />
        )}
      </section>
    </div>
  );
}
