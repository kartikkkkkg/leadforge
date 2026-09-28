import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, type JobCreate, type ProvidersHealth } from "../api/client";
import { ErrorBox, Loading } from "../components/Feedback";

const LEAD_COUNTS = [10, 50, 100, 500] as const;

export function validateResearchForm(values: {
  industry: string;
  country: string;
  requested_leads: number;
  demo_delay_ms?: string;
}): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!values.industry.trim()) errors.industry = "Industry is required.";
  if (!values.country.trim()) errors.country = "Country is required.";
  if (!LEAD_COUNTS.includes(values.requested_leads as (typeof LEAD_COUNTS)[number])) {
    errors.requested_leads = "Choose 10, 50, 100, or 500 leads.";
  }
  if (values.demo_delay_ms !== undefined) {
    const n = Number(values.demo_delay_ms);
    if (!Number.isInteger(n) || n < 0 || n > 5000) {
      errors.demo_delay_ms = "Demo delay must be a whole number of ms between 0 and 5000.";
    }
  }
  return errors;
}

export default function NewResearch() {
  const navigate = useNavigate();
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
  const [city, setCity] = useState("");
  const [keywords, setKeywords] = useState("");
  const [requestedLeads, setRequestedLeads] = useState<number>(50);
  const [provider, setProvider] = useState("demo");
  const [enableAi, setEnableAi] = useState(false);
  const [demoDelayMs, setDemoDelayMs] = useState("120");
  const [health, setHealth] = useState<ProvidersHealth | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.providersHealth().then((h) => {
      if (!cancelled) setHealth(h);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const providerOptions = [
    { value: "demo", label: "Demo provider (offline, synthetic data)" },
    { value: "http", label: "HTTP provider (external API)" },
  ];

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errors = validateResearchForm({
      industry,
      country,
      requested_leads: requestedLeads,
      demo_delay_ms: demoDelayMs,
    });
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload: JobCreate = {
        industry: industry.trim(),
        country: country.trim(),
        region: region.trim() || null,
        city: city.trim() || null,
        keywords: keywords.trim() || null,
        requested_leads: requestedLeads as JobCreate["requested_leads"],
        provider,
        enable_ai: enableAi,
        demo_delay_ms: Number(demoDelayMs),
      };
      const job = await api.createJob(payload);
      navigate(`/research/${job.id}`);
    } catch (err) {
      setSubmitError(err);
      setSubmitting(false);
    }
  }

  const field = (name: string, label: string, node: React.ReactNode, required = false) => (
    <div className="form-field">
      <label htmlFor={name}>
        {label} {required ? <span className="required" aria-hidden="true">*</span> : null}
      </label>
      {node}
      {fieldErrors[name] ? (
        <p className="field-error" role="alert">
          {fieldErrors[name]}
        </p>
      ) : null}
    </div>
  );

  return (
    <div className="page">
      <div className="page-head">
        <h1>New Research</h1>
      </div>

      <div className="two-col">
        <form className="card" onSubmit={onSubmit} noValidate aria-label="New research form">
          <h2>Research parameters</h2>

          {field(
            "industry",
            "Industry",
            <input
              id="industry"
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. SaaS, logistics, healthcare"
              autoComplete="off"
              aria-invalid={!!fieldErrors.industry}
            />,
            true,
          )}

          {field(
            "country",
            "Country",
            <input
              id="country"
              type="text"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="e.g. India, United States"
              autoComplete="off"
              aria-invalid={!!fieldErrors.country}
            />,
            true,
          )}

          {field(
            "region",
            "Region / State",
            <input
              id="region"
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="Optional"
              autoComplete="off"
            />,
          )}

          {field(
            "city",
            "City",
            <input
              id="city"
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Optional"
              autoComplete="off"
            />,
          )}

          {field(
            "keywords",
            "Keywords",
            <input
              id="keywords"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Optional — comma separated"
              autoComplete="off"
            />,
          )}

          {field(
            "requested_leads",
            "Lead count",
            <select
              id="requested_leads"
              value={requestedLeads}
              onChange={(e) => setRequestedLeads(Number(e.target.value))}
              aria-invalid={!!fieldErrors.requested_leads}
            >
              {LEAD_COUNTS.map((n) => (
                <option key={n} value={n}>
                  {n} leads
                </option>
              ))}
            </select>,
            true,
          )}

          {field(
            "provider",
            "Provider",
            <select id="provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providerOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>,
            true,
          )}
          {health && health[provider as keyof ProvidersHealth]?.status !== "available" ? (
            <p className="form-note warn">
              The {provider} provider is currently “
              {health[provider as keyof ProvidersHealth]?.status.replace(/_/g, " ")}” — the job may
              fail at discovery.
            </p>
          ) : null}

          {field(
            "demo_delay_ms",
            "Demo delay (ms)",
            <input
              id="demo_delay_ms"
              type="number"
              min={0}
              max={5000}
              step={10}
              value={demoDelayMs}
              onChange={(e) => setDemoDelayMs(e.target.value)}
              aria-invalid={!!fieldErrors.demo_delay_ms}
              aria-describedby="demo-delay-hint"
            />,
          )}
          <p className="form-note" id="demo-delay-hint">
            Only affects the demo provider: pauses the pipeline between stages so progress is
            visible. 0 disables the pause; tests and headless runs use 0.
          </p>

          <div className="form-field">
            <label htmlFor="enable_ai" className="check-label">
              <input
                id="enable_ai"
                type="checkbox"
                checked={enableAi}
                onChange={(e) => setEnableAi(e.target.checked)}
              />
              Enable AI enrichment (optional)
            </label>
            <p className="form-note" id="enable-ai-hint">
              {health?.ai?.status === "configured"
                ? "AI enrichment is configured on the server — this job will add AI-derived fields, clearly tagged and never treated as verified facts."
                : "AI enrichment is not configured on the server (no API key) — the job will run normally with no AI-derived fields."}
            </p>
          </div>

          {submitError ? (
            <ErrorBox error={submitError} />
          ) : submitting ? (
            <Loading label="Starting research…" />
          ) : null}

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? "Starting…" : "Start Research"}
            </button>
          </div>
          {submitError instanceof ApiError && submitError.code === "provider_not_configured" ? (
            <p className="form-note">
              Tip: the HTTP provider needs external API credentials. Use the demo provider to try
              LeadForge offline.
            </p>
          ) : null}
        </form>

        <aside className="card" aria-label="What will be collected">
          <h2>What we will collect</h2>
          <ul className="collect-list">
            <li>Company name</li>
            <li>Website</li>
            <li>Location (country, region, city)</li>
            <li>Phone</li>
            <li>Public email</li>
            <li>LinkedIn URL (if public)</li>
            <li>Source URL</li>
          </ul>
          <p className="muted">
            Every record is normalized, validated, deduplicated and scored for completeness.
            Completeness is an internal data-quality measure — it is not third-party verification.
          </p>
        </aside>
      </div>
    </div>
  );
}
