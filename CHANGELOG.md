# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Phase 1: architecture, data model, API contract, pipeline interfaces (`DESIGN.md`)
- Phase 2: repository skeleton — configs, Docker setup, docs structure, package layout
- Phase 3: backend core — pydantic-settings config, structured logging with secret
  redaction, SQLAlchemy engine/session (SQLite default, PostgreSQL via `DATABASE_URL`),
  models (`ResearchJob`, `Company`, `LeadResearchResult`, `RejectedRecord`), Pydantic schemas
- Phase 4: deterministic pipeline stages — normalization (`normalize.py`), validation
  with stable `UPPER_SNAKE` issue codes (`validate.py`), deduplication with exact +
  fuzzy matching and `needs_review` flagging (`dedupe.py`), transparent completeness
  scoring 0–100 with High/Medium/Low bands (`score.py`); 90 unit tests, 100% stage coverage
- Phase 5: lead discovery providers — `ResearchProvider` abstraction; `DemoProvider`
  (deterministic, offline, 100 synthetic companies labeled `is_synthetic`);
  `HttpApiProvider` skeleton for legitimate external API integrations (no scraping)
- Phase 6: research pipeline orchestration — `PipelineRunner` running all eight
  stages (DISCOVER → EXTRACT → NORMALIZE → VALIDATE → DEDUPLICATE → ENRICH →
  SCORE → STORE) in a single transaction; job lifecycle with live stage/progress
- Phase 7: FastAPI API — research jobs, filterable/sortable/paginated results,
  record detail, validation report, structured `{detail, code}` errors
- Phase 8: React 18 + TypeScript + Vite frontend against the real API — dashboard,
  research form, live pipeline progress, results table, record detail, settings
- Phase 9: demo integration — idempotent seed/reset (`make seed-demo`,
  `make run-demo`, `make reset-demo`), canonical walkthrough in `docs/demo-guide.md`
- Phase 10: optional AI enrichment — `AIProvider` abstraction; `NullAIProvider`
  default (disabled, jobs complete normally); key-gated LLM provider with
  `ai_derived` provenance tagging; AI failures never fail a job
- Phase 11: test hardening — 300 backend tests, 73 frontend tests; coverage
  recorded (98% backend statements, 93.9% frontend statements)
- Phase 12: CSV/XLSX export — export service (UTF-8 BOM CSV; styled XLSX with
  Leads / Research Summary / Parameters sheets), API endpoint, CLI, and UI
  download buttons; Docker stack productionized (backend/frontend images,
  PostgreSQL, healthchecks, `docker compose config` valid)
- Phase 13: end-to-end demo workflow — `docs/demo/` capture assets (6 screenshots
  + 60-second GIF) from the working app with honest-limitations documentation
- Phase 14: 25-point quality audit — full pipeline, providers, scoring, AI safety,
  API contract, persistence, exports, security, Docker/PostgreSQL all verified;
  documentation truthfulness fixes

## [0.1.0] — TBD

- First working release: demo provider, full pipeline, dashboard UI, CSV/XLSX export.
