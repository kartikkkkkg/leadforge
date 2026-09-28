import { useEffect, useState } from "react";
import { api, type DemoResetResponse, type ProvidersHealth } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import SyntheticBadge from "../components/SyntheticBadge";
import { ErrorBox, Loading } from "../components/Feedback";

const ORDER: (keyof ProvidersHealth)[] = ["demo", "http", "ai", "database"];

type ConfirmKind = "reset" | "reseed" | null;

function resetSummary(r: DemoResetResponse): string {
  const parts = [
    `${r.jobs_deleted} job${r.jobs_deleted === 1 ? "" : "s"}`,
    `${r.results_deleted} result${r.results_deleted === 1 ? "" : "s"}`,
    `${r.rejected_records_deleted} rejected record${r.rejected_records_deleted === 1 ? "" : "s"}`,
    `${r.companies_deleted} ${r.companies_deleted === 1 ? "company" : "companies"}`,
  ];
  let msg = `Reset complete — deleted ${parts.join(", ")}.`;
  if (r.reseeded) msg += ` Re-seeded ${r.companies} synthetic companies.`;
  return msg;
}

function DemoControls() {
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmKind>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function run(kind: "seed" | "reset" | "reseed") {
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      if (kind === "seed") {
        const r = await api.seedDemo();
        setMessage(`Seeded ${r.companies} synthetic companies into the demo dataset.`);
      } else {
        const r = await api.resetDemo(kind === "reseed");
        setMessage(resetSummary(r));
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
      setConfirm(null);
    }
  }

  return (
    <section className="card" aria-label="Demo data">
      <h2>Demo data</h2>
      <p className="muted">
        Manage the synthetic demo dataset. All demo data is <SyntheticBadge /> — generated
        offline by a seeded generator, never real business data. Seeding replaces the demo
        dataset; it never touches research-job results. Resetting permanently deletes all
        research jobs, results, rejected records, and companies.
      </p>
      <div className="demo-controls">
        <button
          className="btn btn-secondary"
          disabled={busy !== null}
          onClick={() => run("seed")}
        >
          {busy === "seed" ? "Seeding…" : "Seed demo data"}
        </button>
        <button
          className="btn btn-danger"
          disabled={busy !== null}
          onClick={() => setConfirm("reset")}
        >
          Reset demo data
        </button>
        <button
          className="btn btn-danger"
          disabled={busy !== null}
          onClick={() => setConfirm("reseed")}
        >
          Reset + reseed
        </button>
      </div>
      {confirm && (
        <div className="confirm-box" role="alertdialog" aria-label="Confirm reset">
          <p>
            <strong>
              {confirm === "reseed"
                ? "Reset all demo data and re-seed the synthetic dataset?"
                : "Reset all demo data?"}
            </strong>
            <br />
            <span className="muted">
              This permanently deletes every research job, result, rejected record, and
              company. This cannot be undone.
            </span>
          </p>
          <div className="demo-controls">
            <button
              className="btn btn-danger"
              disabled={busy !== null}
              onClick={() => run(confirm)}
            >
              {busy ? "Resetting…" : "Yes, reset"}
            </button>
            <button
              className="btn btn-secondary"
              disabled={busy !== null}
              onClick={() => setConfirm(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {message && (
        <p className="demo-message" role="status">
          {message}
        </p>
      )}
      {error ? <ErrorBox error={error} onRetry={() => setError(null)} /> : null}
    </section>
  );
}

export default function Settings() {
  const [health, setHealth] = useState<ProvidersHealth | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .providersHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <div className="page-head">
        <h1>Settings</h1>
      </div>

      <section className="card" aria-label="Provider health">
        <h2>Provider health</h2>
        <p className="muted">
          Live status from <code>GET /api/providers/health</code>. “Not configured” means the
          provider has no credentials on this server — it is not an error and not “offline”.
        </p>
        {error ? (
          <ErrorBox error={error} onRetry={() => window.location.reload()} />
        ) : !health ? (
          <Loading label="Checking providers…" />
        ) : (
          <div className="provider-grid">
            {ORDER.map((k) => {
              const p = health[k];
              return (
                <div key={k} className="provider-card">
                  <div className="provider-head">
                    <strong>{p.name}</strong>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="muted">{p.detail}</p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <DemoControls />

      <section className="card" aria-label="About">
        <h2>About</h2>
        <p className="muted">
          LeadForge runs research jobs through a six-stage pipeline — discover, normalize,
          validate, deduplicate, score, store — and exposes results through this API. Demo
          provider data is fully synthetic, generated offline, and always labeled as such.
        </p>
      </section>
    </div>
  );
}
