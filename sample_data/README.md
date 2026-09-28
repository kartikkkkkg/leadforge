# Sample data

This folder documents the synthetic demo dataset.

- The dataset is **generated**, not stored: see `backend/leadforge/seed.py`
  (Phase 5) for the seeded generator.
- 100 companies across ~6 industries and 5 US states, with intentional duplicates,
  near-duplicates, malformed emails/URLs, and missing fields — so deduplication and
  validation are demonstrable.
- All records are synthetic: `example.com` domains, fictional `555-01XX` phones,
  role-based emails only, no real personal names. Never presented as real companies.
