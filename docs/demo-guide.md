# Demo Guide

> The canonical end-to-end demo. Exact counts will be pinned here once the seeded
> generator lands in Phase 5 (seeded RNG → reproducible numbers).

## The 60-second walkthrough

1. **Seed:** `make seed-demo` — loads 100 synthetic companies.
2. **Create a job:** Dashboard → *Create Lead List* →
   - Industry: `Jewelry Stores`
   - Country: `United States`
   - Region: `California`
   - Requested leads: `100`
   - Click **Start Research** (after reviewing the "what we'll collect" panel).
3. **Watch the pipeline:** the 8 stages (Discover → … → Store) update live with
   discovered / processed / accepted / duplicates / invalid counters.
4. **Results:** filterable table — try filtering by state, completeness band, and
   validation status. Open a record to see the score breakdown and validation results.
5. **Export:** download CSV and the styled XLSX (Leads + Research Summary + Parameters).

## Expected outcome (target)

Approximately: **100 discovered → ~90 unique → ~6 duplicates → ~4 invalid → ~90 usable
records**, with completeness spread across High/Medium/Low bands.

## Headless version

```bash
make run-demo   # same job, no browser; prints the stage summary
```

## Capture checklist

See [`demo/`](demo/) for the screenshot/video shot list.
