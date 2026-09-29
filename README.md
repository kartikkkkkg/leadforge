# LeadForge

**Automated B2B lead research and data-enrichment platform** that turns research criteria into normalized, validated, deduplicated, scored, and exportable company datasets.

> **Status:** Complete — all 15 build phases finished (staged research pipeline, FastAPI API, React/TypeScript UI, CSV/XLSX export, Docker + PostgreSQL, deterministic demo workflow, 25-point quality audit, final documentation). Runs end-to-end via `./scripts/dev.sh` or `docker compose up`.

## Demo

Research criteria → pipeline → results → record detail → CSV/XLSX export:

![LeadForge 60-second demo](docs/demo/demo-60s.gif)

| Create a job | Pipeline running | Results table |
|---|---|---|
| ![Create job](docs/demo/01-create-job.png) | ![Pipeline running](docs/demo/02-pipeline-running.png) | ![Results table](docs/demo/03-results-table.png) |

| Filtering | Record detail | Excel export |
|---|---|---|
| ![Filtering](docs/demo/04-filtering.png) | ![Record detail](docs/demo/05-record-detail.png) | ![Excel export](docs/demo/06-excel-export.png) |

More context in [`docs/demo/`](docs/demo/).

## What is LeadForge?

**The problem:** sales teams spend hours manually researching companies and assembling lead lists in spreadsheets — a process that is slow, inconsistent, and impossible to audit.

**The solution:** describe the companies you want (industry, country, region, keywords, lead count), and LeadForge runs a staged data pipeline behind a clean dashboard, producing a scored, exportable dataset (CSV/XLSX) instead of a hand-built spreadsheet.

**The pipeline** — every job flows through these stages in a single database transaction:

```
DISCOVER → EXTRACT → NORMALIZE → VALIDATE → DEDUPLICATE → ENRICH → SCORE → STORE → EXPORT
```

- **Discover/Extract** — pull raw company records from a research provider (deterministic synthetic demo provider by default).
- **Normalize** — standardize names, addresses, phones, URLs, emails.
- **Validate** — check every field against rules; each issue gets a stable `UPPER_SNAKE` issue code.
- **Deduplicate** — exact + fuzzy matching; ambiguous pairs are flagged `needs_review`, never silently merged.
- **Enrich** — optional AI enrichment (off by default; AI-derived fields are explicitly tagged and never overwrite source data).
- **Score** — transparent 0–100 completeness score with High/Medium/Low bands; score factors are visible per record.
- **Store** — SQLAlchemy persistence (SQLite default, PostgreSQL supported).
- **Export** — download accepted results as CSV or styled XLSX after the job completes.

**What you provide:** research criteria (industry, country, region, keywords, lead count).
**What you get:** a filterable, sortable, paginated dataset of validated company records with per-record explainability, a validation report, and one-click CSV/XLSX export.

## What can it do?

- **Research jobs** — create, monitor (live stage/progress), list, and delete jobs via UI, API, or CLI.
- **Deterministic demo provider** — 100 synthetic companies, seeded identically every time; no API key, works fully offline.
- **Provider abstraction** — `ResearchProvider` interface; `HttpApiProvider` skeleton for legitimate external business-data APIs.
- **Normalization** — names, addresses, phones, URLs, emails standardized deterministically.
- **Validation** — field rules with stable issue codes and a per-job validation report.
- **Exact + fuzzy deduplication** — duplicates flagged `needs_review`; merges require human approval.
- **Completeness scoring** — 0–100 with High/Medium/Low bands and visible score factors.
- **Result filtering / sorting / pagination** — by score band, validation status, dedupe state, text search.
- **Record-level explainability** — normalized vs. derived data, issue codes, dedupe candidates, score breakdown.
- **Optional AI enrichment** — disabled by default; AI-derived fields tagged `ai_derived`; AI failures never fail a job.
- **CSV export** — UTF-8 with BOM, 14 fixed columns.
- **XLSX export** — styled workbook with *Leads*, *Research Summary*, and *Parameters* sheets.
- **REST API** — FastAPI with interactive Swagger docs at `/docs`.
- **CLI** — seed, reset, run headless, export, serve.
- **SQLite** (zero-config default) and **PostgreSQL** (via `DATABASE_URL` or Docker).
- **Docker** — productionized Compose stack: backend, frontend (nginx), PostgreSQL, healthchecks.
- **Frontend dashboard** — React 18 + TypeScript + Vite: dashboard, research form, live pipeline progress, results, record detail, settings.
- **Demo seed/reset** — idempotent `seed-demo` / `reset-demo` / `run-demo` commands.
- **Health endpoints** — `/api/health` and `/api/providers/health`.

## Architecture

```mermaid
flowchart TD
    U[User] --> F[React + TypeScript frontend]
    U -->|optional| C[CLI: python -m leadforge]
    F -->|REST /api| A[FastAPI REST API]
    C -->|in-process| R[Pipeline Runner]
    A -->|BackgroundTasks, in-process| R
    R --> P[Provider layer]
    P --> D[DemoProvider: synthetic, offline]
    P --> H[HttpApiProvider: integration skeleton]
    R --> S[Processing stages: normalize → validate → dedupe → enrich → score]
    S --> O[SQLAlchemy ORM]
    O --> DB[(SQLite / PostgreSQL)]
    O --> RES[Results]
    RES --> F
    RES --> E[Export engine: CSV / XLSX]
    S -. optional .-> AI[AI enrichment: NullAIProvider default]
```

Key design decisions (see [`DESIGN.md`](DESIGN.md)):

- **No background worker, no queues, no Redis** — research jobs run in-process on the API server via FastAPI `BackgroundTasks`. Deliberate: simpler ops, single-transaction pipeline.
- **No CORS middleware** — the Vite dev server proxies `/api` to the backend locally, and the Docker frontend (nginx) proxies `/api/` to the backend container. Same-origin in both supported setups.
- **Provider abstraction** — the pipeline never talks to the network directly; all discovery goes through `ResearchProvider`.
- **AI is advisory only** — enrichment output is tagged `ai_derived` and can never modify normalized/validated/scored source fields.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12) |
| ORM / migrations | SQLAlchemy |
| Data processing | Pandas |
| Excel export | openpyxl |
| Frontend | React 18 + TypeScript |
| Build / dev server | Vite 5 |
| Database | SQLite (default) / PostgreSQL 16 |
| Containers | Docker / Docker Compose |
| Frontend serving (Docker) | nginx |
| Testing | Pytest / Vitest |
| AI | Optional provider abstraction (disabled by default) |

## Quick Start — Local Development

Tested with **Python 3.12**, **Node 20+**, **npm 10**, **Git**. Docker is only needed for the Docker path.

### 1. Clone

```bash
git clone https://github.com/kartikkkkkg/leadforge.git
cd leadforge
```

### 2. Create a Python virtual environment

```bash
python3.12 -m venv .venv
```

### 3. Activate it

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 4. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 5. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

### 6. Configure environment

No `.env` is required for local development — **SQLite works with zero configuration**. If you want to customize, copy the example:

```bash
cp .env.example .env
```

### 7. Start backend + frontend (easiest)

```bash
./scripts/dev.sh
```

This starts the FastAPI backend on `:8000` and the Vite frontend on `:5173`. Press `Ctrl+C` to stop both. (It auto-detects `.venv` at the repo root or `backend/.venv`, or falls back to `python3`.)

Or start each service manually:

```bash
# Terminal 1 — backend
cd backend && ../.venv/bin/python -m leadforge serve

# Terminal 2 — frontend
cd frontend && npm run dev
```

### 8. Open the application

- **UI:** http://localhost:5173
- **API:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs

## Run the Demo

LeadForge ships with a deterministic synthetic dataset — **no external API key required**, works fully offline. The data is labeled `SYNTHETIC` throughout; this is demonstration data, not live scraped business data.

### UI demo

1. Start the app (`./scripts/dev.sh`).
2. Open http://localhost:5173 → **New Research**.
3. Enter:
   - Industry: `Jewelry Stores`
   - Country: `United States`
   - Region: `California`
   - Requested leads: `100`
4. Watch the pipeline run, then browse results, open a record for explainability, and export CSV/XLSX.

Expected: **10 discovered, 10 processed, 10 accepted.**

### CLI / headless demo

```bash
cd backend
../.venv/bin/python -m leadforge seed-demo     # load the 100-company synthetic dataset
../.venv/bin/python -m leadforge run-demo --industry "Jewelry Stores" \
  --country "United States" --region California --leads 100
../.venv/bin/python -m leadforge reset-demo    # wipe demo data (jobs, companies, results)
```

Or via Make from the repo root: `make seed-demo`, `make run-demo`, `make reset-demo`.

## Docker

The Compose stack runs three services: **backend** (FastAPI), **frontend** (nginx serving the built UI, proxying `/api/` to backend), and **db** (PostgreSQL 16). From a fresh clone:

```bash
docker compose up --build
```

- **UI:** http://localhost:5173 (mapped from the frontend container's port 80)
- **API:** http://localhost:8000 (mapped from `BACKEND_PORT`)
- **PostgreSQL:** internal to the stack (volume `pgdata`); not published to the host by default.

Notes:

- `docker compose config --quiet` validates the configuration.
- Healthchecks gate startup: backend waits for PostgreSQL, frontend waits for backend.
- Data persists in the `pgdata` (PostgreSQL) and `backend-data` volumes.
- Stop: `docker compose down`
- Full reset (⚠️ **deletes all database data**): `docker compose down -v`
- The frontend talks to the backend through the nginx `/api/` proxy, so no CORS or extra configuration is needed.

## PostgreSQL

**SQLite is the default** — you do not need PostgreSQL for local development. PostgreSQL is supported for production-like deployments:

```bash
DATABASE_URL=postgresql+psycopg2://leadforge:leadforge@localhost:5432/leadforge
```

- In Docker, `DATABASE_URL` is wired automatically to the `db` service (`docker-compose.yml`).
- Locally, point `DATABASE_URL` at any reachable PostgreSQL 16 instance; the app creates tables on startup.
- PostgreSQL compatibility tests are opt-in — without `LEADFORGE_TEST_POSTGRES_URL` they are skipped (3 skipped in the suite):

```bash
LEADFORGE_TEST_POSTGRES_URL=postgresql+psycopg2://leadforge:leadforge@localhost:5432/leadforge \
  ../.venv/bin/python -m pytest backend/tests -q
```

## Real External Data / Provider Integration

### Demo provider (default)

- Built in, deterministic, synthetic — 100 companies generated from a fixed seed.
- No API key, no network, ideal for testing and demos.
- Every record is flagged `is_synthetic`.

### HTTP provider (integration skeleton)

Set `LEADFORGE_PROVIDER=http` and configure:

```bash
LEADFORGE_PROVIDER=http
LEADFORGE_HTTP_API_BASE_URL=https://api.example-provider.com
LEADFORGE_HTTP_API_KEY=<your key>
```

What is real today: configuration shape (base URL, API key, timeout), request/response plumbing with safe error handling, credential hygiene (never logged), and honest health reporting (`not_configured` / `available` / `error`).

What is **not** included: this is an integration skeleton, not a working provider. Attaching a real API requires implementing the marked integration points (`_search_path` / `_map_search_response`, `_details_path` / `_map_details_response`) for that API's endpoint contract. **It does not scrape Google/LinkedIn, does not bypass CAPTCHAs, does not bypass authentication, and does not evade anti-bot systems.** Legitimate APIs only.

## Optional AI Enrichment

- AI is **optional** — the application works fully without any LLM key.
- Default is `NullAIProvider` (disabled, offline, no credentials).
- Set `LEADFORGE_LLM_API_KEY` to select the `LLMProvider`; `LEADFORGE_LLM_PROVIDER` / `LEADFORGE_LLM_MODEL` are recorded for the wiring.
- Honest current state: `LLMProvider` defines the provider interface, provenance tagging, and graceful degradation, but the chat transport must be wired to a real LLM endpoint for live calls — with a key but no transport, it logs a warning and degrades instead of failing.
- AI-derived fields are tagged `ai_derived` and **can never modify normalized/validated/scored source data**.
- **AI failures never fail a job** — the pipeline completes with the non-AI results.

## HTTPS / Real Production Deployment

Local development uses plain HTTP (`http://localhost:5173`, `http://localhost:8000`). For real HTTPS on your own server/domain, TLS termination must be supplied by the deployment environment — typically a reverse proxy in front of the Docker stack:

```
Internet
  ↓ HTTPS :443
yourdomain.com (DNS A/AAAA → server IP)
  ↓
Reverse proxy (nginx / Caddy) — terminates TLS
  ↓ HTTP (internal)
Frontend container (nginx :80, proxies /api/ → backend)
  ↓
Backend container (:8000)
  ↓
PostgreSQL (volume pgdata)
```

LeadForge's repository provides the application/container stack; **HTTPS termination must be supplied by the deployment environment/reverse proxy** — it is not built into `scripts/dev.sh` or `docker compose`.

### Step-by-step: `https://yourdomain.com`

1. **Server** — a VPS/cloud VM (2 vCPU / 4 GB RAM is comfortable) with a public IP and Docker installed.
2. **Domain** — register `yourdomain.com`.
3. **DNS** — create an `A` record (and `AAAA` for IPv6) pointing `yourdomain.com` to the server's public IP.
4. **Firewall** — allow `22` (SSH), `80` (HTTP, for certificate issuance), `443` (HTTPS). Block everything else.
5. **Deploy the stack:**
   ```bash
   git clone https://github.com/kartikkkkkg/leadforge.git
   cd leadforge
   docker compose up --build -d
   ```
6. **Reverse proxy with TLS** — simplest robust option is Caddy (automatic Let's Encrypt):
   ```
   yourdomain.com {
       reverse_proxy localhost:5173
   }
   ```
   The frontend container already proxies `/api/` to the backend, so one upstream is enough. (With nginx + Certbot instead: proxy `location /` to `http://localhost:5173`, run `certbot --nginx -d yourdomain.com`.)
7. **HTTP → HTTPS redirect** — Caddy does this by default; with nginx, add a `:80` server block returning `301 https://$host$request_uri`.
8. **Secrets** — set real values in the environment, never in the repo: `POSTGRES_PASSWORD`, `LEADFORGE_LLM_API_KEY`, `LEADFORGE_HTTP_API_KEY`. A `.env` file next to `docker-compose.yml` is picked up automatically (see `.env.example`; never commit real secrets).
9. **PostgreSQL persistence** — data lives in the `pgdata` volume. Back it up regularly:
   ```bash
   docker compose exec db pg_dump -U leadforge leadforge > backup.sql
   ```
10. **Restart policy** — all services use `restart: unless-stopped`, so they survive reboots.
11. **Health checks** — `docker compose ps` shows health; the API health endpoint is `/api/health`.
12. **Logs** — `docker compose logs -f backend` / `docker compose logs -f frontend`.
13. **Updating** — `git pull && docker compose up --build -d`.
14. **Stopping/removing** — `docker compose down` (keeps data); `docker compose down -v` (⚠️ deletes database data).

## Environment Variables

Only variables that actually exist in `.env.example` / `config.py`:

| Variable | Required | Purpose | Example |
|---|---|---|---|
| `DATABASE_URL` | No | PostgreSQL URL; omit for zero-config SQLite | `postgresql+psycopg2://leadforge:leadforge@localhost:5432/leadforge` |
| `LEADFORGE_PROVIDER` | No | Research provider: `demo` (default) or `http` | `demo` |
| `LEADFORGE_HTTP_API_BASE_URL` | For `http` provider | Base URL of a legitimate company-data API | `https://api.example-provider.com` |
| `LEADFORGE_HTTP_API_KEY` | For `http` provider | API key (**secret**) | — |
| `LEADFORGE_HTTP_TIMEOUT_S` | No | HTTP provider timeout, seconds (default 10.0) | `10.0` |
| `LEADFORGE_AI_ENABLED` | No | AI enrichment flag (default `false`) | `false` |
| `LEADFORGE_LLM_PROVIDER` | No | LLM provider label for the wiring | `openai` |
| `LEADFORGE_LLM_API_KEY` | For AI | LLM API key (**secret**) | — |
| `LEADFORGE_LLM_MODEL` | No | LLM model label for the wiring | — |
| `LEADFORGE_DEMO_SEED` | No | Seed for deterministic demo data (default 42) | `42` |
| `LEADFORGE_DEMO_DELAY_MS` | No | Simulated per-stage delay in demo (default 120) | `120` |
| `LEADFORGE_ENV` | No | `development` / `production` | `development` |
| `LEADFORGE_LOG_LEVEL` | No | Log level (default `INFO`) | `INFO` |
| `BACKEND_PORT` | No | Local/dev backend port (default 8000) | `8000` |
| `FRONTEND_PORT` | No | Local/dev frontend port (default 5173) | `5173` |
| `VITE_API_URL` | No | Frontend API base URL override | `http://localhost:8000` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Docker | PostgreSQL credentials for `docker compose` (**secrets**) | `leadforge` |

## API

Interactive docs: http://localhost:8000/docs (Swagger/OpenAPI).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health + version |
| `GET` | `/api/providers/health` | Provider + AI configuration health |
| `POST` | `/api/research/jobs` | Create a research job |
| `GET` | `/api/research/jobs` | List jobs |
| `GET` | `/api/research/jobs/{job_id}` | Job status + progress |
| `GET` | `/api/research/jobs/{job_id}/results` | Filtered/sorted/paginated results |
| `GET` | `/api/research/jobs/{job_id}/results/{result_id}` | Record detail + explainability |
| `DELETE` | `/api/research/jobs/{job_id}/results/{result_id}` | Reject a result (human review) |
| `GET` | `/api/research/jobs/{job_id}/validation-report` | Per-job validation summary |
| `POST` | `/api/research/jobs/{job_id}/export?format=csv\|xlsx` | Download dataset (completed jobs only) |
| `POST` | `/api/demo/seed` | Load synthetic demo dataset |
| `POST` | `/api/demo/reset` | Wipe demo data |

Basic workflow:

```bash
# 1. Create a job
curl -s -X POST http://localhost:8000/api/research/jobs \
  -H 'Content-Type: application/json' \
  -d '{"industry":"Jewelry Stores","country":"United States","region":"California","requested_leads":100}'

# 2. Poll status until "completed"
curl -s http://localhost:8000/api/research/jobs/<job_id>

# 3. Browse results (filters: score_band, validation_status, dedupe_state, q)
curl -s "http://localhost:8000/api/research/jobs/<job_id>/results?score_band=High&page=1&page_size=20"

# 4. Export (completed jobs only)
curl -s -X POST "http://localhost:8000/api/research/jobs/<job_id>/export?format=xlsx" -o leads.xlsx
```

`requested_leads` must be one of `10`, `50`, `100`, `500`. Errors are structured as `{"detail": ..., "code": ...}`.

## CLI

Run from `backend/` with the project venv (`../.venv/bin/python -m leadforge …`):

| Command | Description |
|---|---|
| `seed-demo` | Load the 100-company synthetic dataset |
| `reset-demo` | Wipe demo data (jobs, companies, results) |
| `run-demo --industry … --country … --region … --leads …` | Run the research pipeline headless |
| `export --job <id> --format csv\|xlsx --out <file>` | Export a completed job's dataset |
| `serve [--host 127.0.0.1] [--port 8000]` | Run the API server |
| `worker` | Explains there is no worker process (jobs run in-process by design) |

## Export

**CSV** — UTF-8 with BOM, header row, one row per accepted result. 14 fixed columns:

`company_name, website, industry, country, region, city, address, phone, public_email, linkedin_url, source_url, quality_score, validation_status, is_synthetic`

**XLSX** — styled workbook with three sheets:

- **Leads** — the 14 base columns + `score_band`, `verification_status`, `collected_at`; filters, freeze panes, band color formatting.
- **Research Summary** — job parameters, stage counts, score-band distribution.
- **Parameters** — the research criteria that produced the dataset.

`is_synthetic` is always included so demo data can never be mistaken for real data.

## Testing

Measured 2026-09-28 — honest numbers, no thresholds chased:

| Suite | Result | Command |
|---|---|---|
| Backend (`pytest`) | **300 passed** (3 skipped: opt-in PostgreSQL) | `cd backend && ../.venv/bin/python -m pytest tests -q` |
| Frontend (`vitest`) | **73 passed** | `cd frontend && npx vitest run` |
| TypeScript | clean | `cd frontend && npx tsc --noEmit` |
| Production build | passes | `cd frontend && npx vite build` |
| Compose config | valid | `docker compose config --quiet` |

## Project Structure

```
backend/            FastAPI app (leadforge/): API, pipeline stages, providers,
                    AI abstraction, export engine, CLI; tests/
frontend/           React 18 + TypeScript + Vite SPA; nginx.conf + Dockerfile
docs/               api.md, architecture.md, deployment.md, data-privacy.md,
                    demo-guide.md, demo/ (screenshots + 60s GIF)
scripts/            dev.sh — local launcher (backend :8000 + frontend :5173)
sample_data/        Sample inputs/fixtures
docker-compose.yml  Backend + frontend + PostgreSQL 16 stack
Makefile            install / dev / test / demo / docker shortcuts
DESIGN.md           Architecture, pipeline stages, schema, decisions
CHANGELOG.md        Phase-by-phase history
```

## Security / Privacy

- **Synthetic demo data** — always flagged `is_synthetic`; never presented as real.
- **Public-business-data orientation** — designed around legitimate company-data sources, not personal data.
- **No private-data harvesting, no CAPTCHA bypass, no bot evasion, no auth bypass.**
- **Secret handling** — API keys come from the environment, are never logged, never appear in errors or `repr`.
- **AI provenance** — AI-derived fields are tagged `ai_derived`; the completeness score is a data-quality measure, not third-party verification.

See [`docs/data-privacy.md`](docs/data-privacy.md).

## Limitations

Be explicit — these are real and by design:

- The demo provider is **synthetic**; it contains no real business data.
- The HTTP provider is an **integration skeleton** — wiring a real API requires implementing the marked adapter points.
- **No scraping engine.** No CAPTCHA bypass, no anti-bot evasion, no login-wall bypassing.
- **No private-data harvesting** — the system is oriented toward public business data.
- The completeness score measures **data completeness/quality**, not verified business truth.
- AI-derived output is **never verified** and is explicitly tagged.
- AI enrichment currently requires a chat transport to be wired for live LLM calls (key alone degrades gracefully).

## Troubleshooting

| Problem | Fix |
|---|---|
| Port 8000 already in use | `lsof -ti:8000 \| xargs kill` (macOS/Linux), or `BACKEND_PORT=8001 ./scripts/dev.sh` |
| Port 5173 already in use | `lsof -ti:5173 \| xargs kill`, or `FRONTEND_PORT=5174 ./scripts/dev.sh` |
| `.venv` missing | `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt` |
| Wrong Python version | Use **Python 3.12** (tested); check with `python3 --version` |
| Frontend deps missing | `cd frontend && npm install` |
| Backend deps missing | `pip install -r backend/requirements.txt` from an activated venv |
| Database connection problems | Unset `DATABASE_URL` to fall back to zero-config SQLite; verify Postgres is reachable and credentials match |
| Docker not running | Start Docker Desktop / the Docker daemon, then retry `docker compose up` |
| PostgreSQL problems in Docker | `docker compose logs db`; `docker compose down -v` only if you accept **data loss** |
| `provider_not_configured` | Set `LEADFORGE_PROVIDER=demo`, or configure `LEADFORGE_HTTP_API_BASE_URL` + `LEADFORGE_HTTP_API_KEY` for the HTTP skeleton |
| AI not configured | Expected unless `LEADFORGE_LLM_API_KEY` is set; the app works fully without AI |
| Frontend can't reach backend | Locally, the Vite proxy handles `/api`; in Docker, nginx proxies `/api/` — check the backend is up at `:8000` |
| Stale process after dev | `Ctrl+C` in the `dev.sh` terminal; or kill leftovers: `pkill -f "leadforge serve"`, `pkill -f "vite"` |
| `scripts/dev.sh` permission denied | `chmod +x scripts/dev.sh` |

## Screenshots / Demo

All capture assets live in [`docs/demo/`](docs/demo/) (captured from the working app; see its README for honest limitations): `01-create-job.png` → `06-excel-export.png`, plus `demo-60s.gif`.

## Use Cases / Portfolio Value

What this project demonstrates, factually:

- **Data engineering** — an eight-stage deterministic pipeline (normalize → validate → dedupe → score) with stable issue codes and idempotent runs.
- **Backend/API development** — FastAPI REST API with structured errors, Swagger docs, health endpoints.
- **Automation** — criteria-in → dataset-out research workflow with live progress.
- **Data quality** — validation rules, exact+fuzzy dedupe with human review, transparent scoring, per-record explainability.
- **Database design** — SQLAlchemy models on SQLite/PostgreSQL, single-transaction pipeline.
- **Frontend integration** — React + TypeScript dashboard against the real API (forms, live progress, tables, detail views, downloads).
- **AI integration architecture** — provider abstraction with provenance tagging and graceful degradation.
- **Testing** — 300 backend + 73 frontend tests with recorded coverage.
- **Docker/deployment** — multi-service Compose stack with healthchecks and documented HTTPS path.
- **Export/reporting** — CSV + styled multi-sheet XLSX delivery.

## License

MIT — see [`LICENSE`](LICENSE).
