import { Link } from "react-router-dom";
import type { ResultDetail } from "../api/client";
import ScoreBadge from "./ScoreBadge";
import StatusBadge from "./StatusBadge";
import SyntheticBadge from "./SyntheticBadge";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{value ?? <span className="muted">—</span>}</dd>
    </div>
  );
}

/** Full record detail. Sections keep RAW / NORMALIZED / DERIVED data apart. */
export default function DetailDrawer({ result }: { result: ResultDetail }) {
  const c = result.company;
  const location = [c.city, c.region, c.country].filter(Boolean).join(", ");
  const factors = result.score_factors
    ? Object.entries(result.score_factors).sort((a, b) => b[1] - a[1])
    : [];
  return (
    <div className="detail">
      <div className="detail-head">
        <h2>{c.company_name}</h2>
        <div className="detail-badges">
          {c.is_synthetic ? <SyntheticBadge /> : null}
          <ScoreBadge score={result.quality_score} />
          <StatusBadge status={result.dedupe_status} />
        </div>
      </div>

      <section aria-label="Company information">
        <h3>Company</h3>
        <dl className="fields">
          <Field label="Website" value={c.website} />
          <Field label="Industry" value={c.industry} />
          <Field label="Location" value={location || null} />
          <Field label="Address" value={c.address} />
          <Field label="Phone" value={c.phone} />
          <Field label="Public email" value={c.public_email} />
          <Field label="LinkedIn" value={c.linkedin_url} />
          <Field label="Source URL" value={c.source_url} />
          <Field label="Source provider" value={c.source_provider} />
        </dl>
      </section>

      <section aria-label="Normalized data">
        <h3>Normalized</h3>
        <dl className="fields">
          <Field label="Normalized name" value={c.normalized_name} />
          <Field label="Normalized domain" value={c.normalized_domain} />
          <Field label="Normalized phone" value={c.phone_normalized} />
        </dl>
      </section>

      <section aria-label="Derived data">
        <h3>Derived</h3>
        <dl className="fields">
          <Field label="Completeness score" value={`${result.quality_score} / 100`} />
          <Field label="Validation status" value={<StatusBadge status={result.validation_status} />} />
          <Field
            label="Verification status"
            value={
              <>
                <StatusBadge status={result.verification_status} />
                <span className="muted"> — validation is not verification</span>
              </>
            }
          />
          <Field label="Dedupe status" value={<StatusBadge status={result.dedupe_status} />} />
          <Field label="Collected at" value={new Date(result.collected_at).toLocaleString()} />
        </dl>
        {factors.length > 0 ? (
          <>
            <h4>Score factors</h4>
            <ul className="factors">
              {factors.map(([name, pts]) => (
                <li key={name}>
                  <span>{name.replace(/_/g, " ")}</span>
                  <span className="num">+{pts}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {result.validation_issues && result.validation_issues.length > 0 ? (
          <>
            <h4>Validation issues</h4>
            <ul className="issues">
              {result.validation_issues.map((i, n) => (
                <li key={n}>
                  <code>{i.code}</code> — {i.field}: {i.message}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <p className="detail-back">
        <Link to={`/results/${result.job_id}`}>← Back to results</Link>
      </p>
    </div>
  );
}
