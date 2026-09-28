# Demo walkthrough (Phase 13)

All assets below were captured from the **working application** — a production
build of the React frontend driven in headless Chromium against the real
FastAPI backend (PostgreSQL). Nothing is mocked or fabricated.

## Canonical walkthrough

| Step | Values |
|---|---|
| Industry | Jewelry Stores |
| Country | United States |
| Region | California |
| Requested leads | 100 |
| Provider | demo (offline, synthetic data) |

**Result:** `10 discovered → 10 accepted → 0 duplicates → 0 invalid`
(status `completed`, stage `DONE`, progress 100%)

The pipeline runs 8 stages — DISCOVER → EXTRACT → NORMALIZE → VALIDATE →
DEDUPLICATE → ENRICH → SCORE → STORE — then DONE. Progress is a coarse
stage milestone, not a time-based estimate; the counters carry exact numbers.

## Assets

- `01-create-job.png` — research form filled with the canonical values
- `02-pipeline-running.png` — pipeline genuinely mid-run (DISCOVER, 12%)
- `03-results-table.png` — results table, 10 records
- `04-filtering.png` — search filter ("Velvet") narrowing to 1 record
- `05-record-detail.png` — record detail (Synthetic badge, normalized + derived sections)
- `06-excel-export.png` — results page with Download CSV / Download Excel
- `demo-60s.gif` — ~66-second walkthrough (form → pipeline → results → filter → detail → export)

## Honest limitations

- **Duplicates/invalid are 0** in this walkthrough because the deterministic
  synthetic seed data is clean by construction. The DEDUPLICATE and VALIDATE
  stages still execute (visible in the pipeline stepper and counters), and the
  validation report explicitly shows the 0 counts — the transparency is real,
  the zeros are honest.
- **All data is synthetic**: every record carries `is_synthetic=true`, uses
  `.example.com` domains and `555-01xx` phone numbers, and the UI labels it
  with a "Synthetic" badge. Nothing is presented as real business data.
- The demo GIF uses a 4-second inter-stage delay (the app's real "Demo delay"
  field) to make the pipeline visible; production runs complete in seconds.

## How to re-capture

- Run the app: `docker compose up` (or `scripts/dev.sh` for local dev).
- Drive the same canonical values through New Research → Start Research.
- Suggested tools: OBS Studio (video), Peek / ScreenToGif (GIF).
- Keep the browser at 1440×900, hide bookmarks bar.
