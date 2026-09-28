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

## [0.1.0] — TBD

- First working release: demo provider, full pipeline, dashboard UI, CSV/XLSX export.
