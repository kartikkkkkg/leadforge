import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  api,
  type ResultRead,
  type ResultsPage,
  type ResultsQuery,
  type ValidationReport,
} from "../api/client";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ScoreBadge from "../components/ScoreBadge";
import StatusBadge from "../components/StatusBadge";
import SyntheticBadge from "../components/SyntheticBadge";
import { ErrorBox, Loading } from "../components/Feedback";

const PAGE_SIZE = 20;

interface Filters {
  search: string;
  industry: string;
  region: string;
  city: string;
  min_score: string;
  max_score: string;
  validation_status: string;
  verification_status: string;
  sort: "quality_score" | "company_name" | "created_at";
  order: "asc" | "desc";
  page: number;
}

const INITIAL: Filters = {
  search: "",
  industry: "",
  region: "",
  city: "",
  min_score: "",
  max_score: "",
  validation_status: "",
  verification_status: "",
  sort: "quality_score",
  order: "desc",
  page: 1,
};

function toQuery(f: Filters): ResultsQuery {
  return {
    search: f.search || undefined,
    industry: f.industry || undefined,
    region: f.region || undefined,
    city: f.city || undefined,
    min_score: f.min_score ? Number(f.min_score) : undefined,
    max_score: f.max_score ? Number(f.max_score) : undefined,
    validation_status: f.validation_status || undefined,
    verification_status: f.verification_status || undefined,
    sort: f.sort,
    order: f.order,
    page: f.page,
    page_size: PAGE_SIZE,
  };
}

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const [filters, setFilters] = useState<Filters>(INITIAL);
  const [applied, setApplied] = useState<Filters>(INITIAL);
  const [page, setPage] = useState<ResultsPage | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(
    async (f: Filters) => {
      if (!id) return;
      setLoading(true);
      setError(null);
      try {
        const [p, r] = await Promise.all([
          api.listResults(id, toQuery(f)),
          f.page === 1 ? api.validationReport(id) : Promise.resolve(report),
        ]);
        setPage(p);
        setReport(r);
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    },
    [id, report],
  );

  useEffect(() => {
    load(applied);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied, id]);

  function applyFilters(e?: React.FormEvent) {
    e?.preventDefault();
    setApplied({ ...filters, page: 1 });
  }

  function resetFilters() {
    setFilters(INITIAL);
    setApplied(INITIAL);
  }

  function toggleSort(col: Filters["sort"]) {
    setFilters((f) => ({
      ...f,
      sort: col,
      order: f.sort === col && f.order === "desc" ? "asc" : "desc",
      page: 1,
    }));
    setApplied((f) => ({
      ...f,
      sort: col,
      order: f.sort === col && f.order === "desc" ? "asc" : "desc",
      page: 1,
    }));
  }

  async function onDelete(result: ResultRead) {
    if (!id) return;
    if (!window.confirm(`Delete “${result.company.company_name}” from these results?`)) return;
    setDeleting(result.id);
    try {
      await api.deleteResult(id, result.id);
      await load(applied);
    } catch (e) {
      setError(e);
    } finally {
      setDeleting(null);
    }
  }

  if (!id) {
    return (
      <div className="page">
        <h1>Results</h1>
        <EmptyState title="No job selected" />
      </div>
    );
  }

  const totalPages = page ? Math.max(1, Math.ceil(page.total / PAGE_SIZE)) : 1;
  const sortArrow = (col: Filters["sort"]) =>
    applied.sort === col ? (applied.order === "desc" ? " ↓" : " ↑") : "";

  const input = (name: keyof Filters, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div className="form-field inline">
      <label htmlFor={`f-${name}`}>{label}</label>
      <input
        id={`f-${name}`}
        value={filters[name] as string}
        onChange={(e) => setFilters((f) => ({ ...f, [name]: e.target.value }))}
        {...props}
      />
    </div>
  );

  return (
    <div className="page">
      <div className="page-head">
        <h1>Results</h1>
        <Link to={`/research/${id}`} className="btn btn-secondary">
          Job Progress
        </Link>
      </div>

      {report ? (
        <section className="card" aria-label="Validation report">
          <h2>Validation report</h2>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-label">Total</div>
              <div className="stat-value">{report.total}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Valid</div>
              <div className="stat-value">{report.valid}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Invalid</div>
              <div className="stat-value">{report.invalid}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Duplicates</div>
              <div className="stat-value">{report.duplicates}</div>
            </div>
          </div>
          {Object.keys(report.issues_by_field).length > 0 ? (
            <>
              <h3>Issue codes</h3>
              <ul className="issues">
                {Object.entries(report.issues_by_field)
                  .sort((a, b) => b[1] - a[1])
                  .map(([code, n]) => (
                    <li key={code}>
                      <code>{code}</code> <span className="num">× {n}</span>
                    </li>
                  ))}
              </ul>
            </>
          ) : (
            <p className="muted">No validation issues — all records passed validation.</p>
          )}
        </section>
      ) : null}

      <section className="card" aria-label="Filter results">
        <form onSubmit={applyFilters}>
          <div className="filter-grid">
            {input("search", "Search", { placeholder: "Company, domain, email…", type: "search" })}
            {input("industry", "Industry", { placeholder: "e.g. SaaS" })}
            {input("region", "Region", { placeholder: "e.g. Karnataka" })}
            {input("city", "City", { placeholder: "e.g. Bengaluru" })}
            {input("min_score", "Min score", { type: "number", min: 0, max: 100 })}
            {input("max_score", "Max score", { type: "number", min: 0, max: 100 })}
            <div className="form-field inline">
              <label htmlFor="f-validation_status">Validation</label>
              <select
                id="f-validation_status"
                value={filters.validation_status}
                onChange={(e) => setFilters((f) => ({ ...f, validation_status: e.target.value }))}
              >
                <option value="">Any</option>
                <option value="valid">Valid</option>
                <option value="invalid">Invalid</option>
              </select>
            </div>
            <div className="form-field inline">
              <label htmlFor="f-verification_status">Verification</label>
              <select
                id="f-verification_status"
                value={filters.verification_status}
                onChange={(e) => setFilters((f) => ({ ...f, verification_status: e.target.value }))}
              >
                <option value="">Any</option>
                <option value="unverified">Unverified</option>
              </select>
            </div>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              Apply filters
            </button>
            <button type="button" className="btn btn-secondary" onClick={resetFilters}>
              Reset
            </button>
          </div>
        </form>
      </section>

      <section className="card" aria-label="Results table">
        {error ? (
          <ErrorBox error={error} onRetry={() => load(applied)} />
        ) : loading || !page ? (
          <Loading label="Loading results…" />
        ) : page.items.length === 0 ? (
          <EmptyState
            title="No results match"
            hint="Try widening the filters — the backend filters server-side."
          />
        ) : (
          <>
            <DataTable<ResultRead>
              columns={[
                {
                  key: "company",
                  header: (
                    <button type="button" className="th-sort" onClick={() => toggleSort("company_name")}>
                      Company{sortArrow("company_name")}
                    </button>
                  ),
                  render: (r) => (
                    <>
                      <div className="cell-main">
                        <Link to={`/results/${id}/record/${r.id}`}>{r.company.company_name}</Link>
                      </div>
                      <div>{r.company.is_synthetic ? <SyntheticBadge /> : null}</div>
                    </>
                  ),
                },
                {
                  key: "domain",
                  header: "Domain",
                  render: (r) => r.company.normalized_domain ?? <span className="muted">—</span>,
                },
                {
                  key: "location",
                  header: "Location",
                  render: (r) =>
                    [r.company.city, r.company.country].filter(Boolean).join(", ") || (
                      <span className="muted">—</span>
                    ),
                },
                {
                  key: "phone",
                  header: "Phone",
                  render: (r) => r.company.phone ?? <span className="muted">—</span>,
                  className: "num",
                },
                {
                  key: "email",
                  header: "Public email",
                  render: (r) => r.company.public_email ?? <span className="muted">—</span>,
                },
                {
                  key: "source",
                  header: "Source",
                  render: (r) => r.company.source_provider,
                },
                {
                  key: "score",
                  header: (
                    <button type="button" className="th-sort" onClick={() => toggleSort("quality_score")}>
                      Score{sortArrow("quality_score")}
                    </button>
                  ),
                  render: (r) => <ScoreBadge score={r.quality_score} />,
                  className: "num",
                },
                {
                  key: "dedupe",
                  header: "Dedupe",
                  render: (r) => <StatusBadge status={r.dedupe_status} />,
                },
                {
                  key: "validation",
                  header: "Validation",
                  render: (r) => <StatusBadge status={r.validation_status} />,
                },
                {
                  key: "actions",
                  header: "",
                  render: (r) => (
                    <div className="row-actions">
                      <Link to={`/results/${id}/record/${r.id}`} className="btn btn-secondary btn-sm">
                        View
                      </Link>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        disabled={deleting === r.id}
                        onClick={() => onDelete(r)}
                      >
                        {deleting === r.id ? "…" : "Delete"}
                      </button>
                    </div>
                  ),
                },
              ]}
              rows={page.items}
            />
            <div className="pagination">
              <span className="muted">
                {page.total} result{page.total === 1 ? "" : "s"} · page {applied.page} of {totalPages}
              </span>
              <div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={applied.page <= 1}
                  onClick={() => setApplied((f) => ({ ...f, page: f.page - 1 }))}
                >
                  ← Prev
                </button>{" "}
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={applied.page >= totalPages}
                  onClick={() => setApplied((f) => ({ ...f, page: f.page + 1 }))}
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
        {error instanceof ApiError && error.code === "job_not_found" ? (
          <p className="form-note">This research job does not exist.</p>
        ) : null}
      </section>
    </div>
  );
}
