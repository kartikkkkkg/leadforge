import { useEffect, useState } from "react";
import { api, type ProvidersHealth } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import { ErrorBox, Loading } from "../components/Feedback";

const ORDER: (keyof ProvidersHealth)[] = ["demo", "http", "ai", "database"];

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
