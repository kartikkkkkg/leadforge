# LeadForge — Automated B2B Lead Research & Data Enrichment Platform

> **Status:** Phase 2 — repository skeleton. Application logic lands in Phases 3–15
> per `DESIGN.md`. Nothing here runs end-to-end yet.

LeadForge automates the repeatable parts of B2B lead research: describe the companies you
want (industry, country, region, keywords), and it discovers, extracts, normalizes,
validates, deduplicates, scores, and exports structured company lead lists — with full
source and data-quality transparency.

**The problem:** sales teams spend hours manually researching companies and assembling
lead lists in spreadsheets.

**The solution:** a staged data pipeline (discover → extract → normalize → validate →
deduplicate → enrich → score → store → export) behind a clean dashboard, producing a
scored, exportable dataset (CSV/XLSX) instead of a hand-built spreadsheet.

## 60-second overview

- **What can I see?** Dashboard → research form → live pipeline → filterable results table →
  per-record explainability view → CSV / styled Excel export downloads.
- **How do I run it?** `scripts/dev.sh` (SQLite, zero setup) or `docker compose up`.
- **Demo?** `make seed-demo && make run-demo` — 100 synthetic companies, no API keys.
- **Stack:** FastAPI + SQLAlchemy + Pandas + openpyxl · React + TypeScript + Vite ·
  SQLite (default) / PostgreSQL · Docker.

## Documentation

- [`DESIGN.md`](DESIGN.md) — Phase 1 architecture, data model, API contract, interfaces
- [`docs/architecture.md`](docs/architecture.md) — system narrative
- [`docs/api.md`](docs/api.md) — API reference
- [`docs/demo-guide.md`](docs/demo-guide.md) — the canonical demo walkthrough
- [`docs/deployment.md`](docs/deployment.md) — deployment options
- [`docs/data-privacy.md`](docs/data-privacy.md) — data & privacy considerations
- [`docs/demo/`](docs/demo/) — demo video/screenshot capture checklist

## Quick start (once implemented)

```bash
cp .env.example .env        # optional; SQLite works with zero config
scripts/dev.sh              # backend on :8000, frontend on :5173
# or
docker compose up
```

## API

Serve the FastAPI backend locally:

```bash
cd backend && ../.venv/bin/python -m leadforge serve   # http://127.0.0.1:8000
```

Interactive docs: `http://127.0.0.1:8000/docs` (OpenAPI at `/openapi.json`).

Key endpoints (see `DESIGN.md` §2 for the full contract):

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness check |
| `GET /api/providers/health` | Demo / HTTP / AI / database status (honest: unconfigured ≠ healthy) |
| `POST /api/research/jobs` | Create a research job → `202` with the queued job; pipeline runs in the background |
| `GET /api/research/jobs` | List jobs (paginated, recent first) |
| `GET /api/research/jobs/{id}` | Job + live counters/stage (poll while running) |
| `GET /api/research/jobs/{id}/results` | Filterable, sortable, paginated results table |
| `GET /api/research/jobs/{id}/results/{result_id}` | Full record detail |
| `DELETE /api/research/jobs/{id}/results/{result_id}` | Delete a record → `204` |
| `GET /api/research/jobs/{id}/validation-report` | valid / invalid / duplicate counts + issue codes |

Errors use `{detail, code}` (`job_not_found`, `invalid_request`,
`provider_not_configured`, `job_not_runnable`, `internal_error`). `progress_pct`
is a coarse stage milestone, not an exact completion estimate.

## Demo mode

```bash
make seed-demo   # load 100 synthetic companies (clearly labeled SYNTHETIC)
make run-demo   # run the full pipeline headless
make reset-demo  # wipe demo data
```

Or use the UI: **Settings → Demo data** has *Seed demo data*, *Reset demo data*
(with confirmation), and *Reset + reseed*. Seeding is idempotent and never touches
research-job results; reset wipes jobs, results, rejected records, and companies.

The **New Research** form has a *Demo delay (ms)* field (default `120`, `0` disables):
it pauses between real pipeline stages so progress is visibly staged. Only the Demo
provider is affected; use `0` for tests/headless runs.

**Export** — completed jobs offer CSV and styled XLSX downloads via the backend
(`POST /api/research/jobs/{id}/export?format=csv|xlsx`), the CLI, and the
results-page download buttons. CSV uses UTF-8 with BOM; XLSX contains
Leads / Research Summary / Parameters sheets with formatting, filters, and
freeze panes.

## AI enrichment (optional)

The **New Research** form has an *Enable AI enrichment* checkbox (`enable_ai` in the API).
The pipeline then runs an 8-stage flow with EXTRACT and ENRICH:

`DISCOVER → EXTRACT → NORMALIZE → VALIDATE → DEDUPLICATE → ENRICH → SCORE → STORE`

- **No key, no AI:** the default `NullAIProvider` is disabled — ENRICH is a no-op and jobs
  complete normally with `ai_enriched: false`. The app is fully usable without any key.
- **With `LEADFORGE_LLM_API_KEY` set:** the LLM provider may add `ai_fields` to results.
  Every value is tagged `{"value": ..., "ai_derived": true}` and shown in the record detail
  under a clearly-labeled **AI-derived (not verified)** section.
- AI never modifies normalized records, validation, deduplication, or completeness scores;
  an AI failure never fails a job. Settings shows **AI enrichment: Enabled/Disabled** honestly.

All synthetic data uses reserved domains (`example.com`), fictional `555-01XX` phone
numbers, and role-based emails only. It is never presented as real. See
[`docs/demo-guide.md`](docs/demo-guide.md) for the canonical walkthrough.

## Frontend

React + TypeScript + Vite app in `frontend/` that talks to the real FastAPI backend
(no mock data).

```bash
cd frontend
npm install
npm test        # vitest suite (55 tests, mocked fetch)
npm run build   # tsc + production bundle
npm run dev     # vite dev server on :5173, proxies /api -> localhost:8000
```

Pages: `/dashboard` (job stats + provider health), `/research/new` (research form),
`/research/:id` (live pipeline progress, polls until terminal), `/results/:id`
(server-side search/filter/sort/paginate + validation report), `/results/:id/record/:resultId`
(record detail: normalized / derived data, synthetic badge, "validation is not verification"), `/settings`
(provider health + demo data seed/reset).

Run the backend first (`leadforge serve`, default `http://localhost:8000`); the dev
server proxies `/api` to it. Demo provider data is always badged SYNTHETIC.

## Project structure

See [`DESIGN.md`](DESIGN.md) §1 for the full annotated tree.

## Test status (Phase 11 — test hardening)

Full suite, measured 2026-09-28 — honest numbers, no thresholds chased:

| Suite | Tests | Coverage | Command |
|---|---|---|---|
| Backend (`pytest`) | **273 passed** | **98%** statements (`pytest-cov`) | `cd backend && ../.venv/bin/python -m pytest tests --cov=leadforge` |
| Frontend (`vitest`) | **55 passed** | **93.9%** statements / 85.6% branches (`@vitest/coverage-v8`) | `cd frontend && npx vitest run --coverage` |
| TypeScript | clean | — | `npx tsc --noEmit` |
| Production build | passes | — | `npx vite build` |

Backend gaps are defensive/unreachable lines (server entrypoint, lazy engine
singleton, logging branches, abstract-method stubs). Frontend entry shells
(`main.tsx`, `App.tsx`, `Layout.tsx`) are exercised via real-stack E2E, not unit
tests. Coverage reports are generated locally and never committed (see `.gitignore`).

## License

MIT — see [LICENSE](LICENSE).
