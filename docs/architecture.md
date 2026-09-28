# Architecture

> Expanded narrative for the diagram and module map in `../DESIGN.md` §1–§2.
> (Full detail arrives with the implementation in Phases 3–10.)

## System overview

LeadForge is a single-backend-service web application:

- **Frontend** (React + TypeScript, Vite) — dashboard, research form, live pipeline view,
  results table, record detail, settings. Talks to the backend over REST/JSON.
- **Backend** (FastAPI, Python 3.12+) — request validation (Pydantic), job lifecycle,
  pipeline orchestration, export engine. SQLite by default; PostgreSQL when `DATABASE_URL`
  is set. Same SQLAlchemy models for both.
- **JobRunner** — in-process asyncio implementation behind an interface, so a Celery/RQ
  worker can replace it later without touching pipeline stages.

## The 8-stage pipeline

`DISCOVER → EXTRACT → NORMALIZE → VALIDATE → DEDUPLICATE → ENRICH → SCORE → STORE`

Each stage is a pure module under `backend/leadforge/pipeline/stages/` with a typed
input/output contract. Stages never touch the database or network directly — the runner
wires them together and persists results via `services/jobs.py`.

## Provider model

`ResearchProvider` (abstract) defines `search_companies`, `get_company_details`,
`extract_contacts`. v1 ships:

- `DemoProvider` — 100 seeded synthetic companies (labeled `is_synthetic`).
- `HttpApiProvider` — skeleton showing where a legitimate external API integration
  attaches. No scraping, no bot evasion.

## AI model

`AIProvider` (abstract) defines `classify_company`, `extract_company_information`,
`summarize_company`. v1 ships:

- `NullAIProvider` (default, `enabled=False`) — rule-based only; the app fully works
  without any LLM key.
- `LLMProvider` — active only when `LEADFORGE_LLM_API_KEY` is set; never invents data
  (returns `None`/`"Unknown"` when unsure); every AI-derived field tagged `ai_derived`.
