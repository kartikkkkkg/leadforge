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
  per-record explainability view → styled Excel export.
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

## Demo mode

```bash
make seed-demo   # load 100 synthetic companies (clearly labeled SYNTHETIC)
make run-demo    # run the full pipeline headless
make reset-demo  # wipe demo data
```

All synthetic data uses reserved domains (`example.com`), fictional `555-01XX` phone
numbers, and role-based emails only. It is never presented as real.

## Project structure

See [`DESIGN.md`](DESIGN.md) §1 for the full annotated tree.

## License

MIT — see [LICENSE](LICENSE).
