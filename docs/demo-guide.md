# Demo Guide

> The canonical end-to-end demo. All data is synthetic (reserved `example.com`
> domains, fictional `555-01XX` phones, role-based emails) and badged SYNTHETIC
> in the UI. It is never presented as real.

## The 60-second walkthrough

1. **Seed:** Settings → *Demo data* → **Seed demo data** — loads the deterministic
   100-company synthetic dataset (idempotent: re-seeding replaces, never duplicates,
   and never touches research-job results). CLI: `make seed-demo`.
2. **Create a job:** *New Research* →
   - Industry: `Jewelry Stores`
   - Country: `United States`
   - Region: `California`
   - Lead count: `100`
   - Demo delay: `120` ms (default; 0–5000, `0` disables — pauses between real
     pipeline stages so progress is visible; only affects the Demo provider)
   - Click **Start Research**.
3. **Watch the pipeline:** the stages (Discover → Normalize → Validate →
   Deduplicate → Score → Store → Done) update live with discovered / processed /
   accepted / duplicates / invalid counters. Progress is a coarse milestone, not
   an exact percentage.
4. **Results:** filterable table — try the search box, sorting by score, and
   pagination. Open a record to see the Synthetic badge, normalized data, derived
   score factors, validation status, and the "validation is not verification" note.
5. **Reset:** Settings → *Demo data* → **Reset demo data** (with confirmation) —
   wipes jobs, results, rejected records, and companies. **Reset + reseed** wipes
   then reloads the 100 synthetic companies. CLI: `make reset-demo`.

## Expected outcome

The walkthrough query above deterministically yields **10 discovered →
10 accepted, 0 duplicates, 0 invalid** (the Demo provider filters the 100-company
seed; only 10 match Jewelry Stores + United States + California).

## Headless version

```bash
make run-demo   # same job, no browser; prints the stage summary
```

## Notes

- **Export** — completed jobs offer CSV and styled XLSX downloads (backend endpoint,
  CLI, and results-page buttons). Safe to demo.
- Tests / headless runs should use demo delay `0` so jobs complete instantly.
- `POST /api/demo/seed` → `{"companies": 100}`; `POST /api/demo/reset`
  (optional `{"reseed": true}`) → deletion counts. See `docs/api.md`.

## Capture checklist

See [`demo/`](demo/) for the screenshot/video shot list.
