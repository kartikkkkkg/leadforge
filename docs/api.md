# API Reference

> Full endpoint behavior lands in Phase 6. Interactive docs: `GET /docs` (Swagger)
> once the backend runs.

Base path: `/api`. Errors are structured as `{"detail": ..., "code": ...}`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/research/jobs` | Create a research job → `202 Accepted` (never blocks) |
| `GET` | `/api/research/jobs` | List jobs (paginated) |
| `GET` | `/api/research/jobs/{id}` | Job detail + live progress counters |
| `GET` | `/api/research/jobs/{id}/results` | Query results: search, filter, sort, paginate |
| `GET` | `/api/research/jobs/{id}/results/{result_id}` | Record detail (explainability view) |
| `DELETE` | `/api/research/jobs/{id}/results/{result_id}` | Delete a record → `204` |
| `POST` | `/api/research/jobs/{id}/export?format=csv\|xlsx` | ⏸ Deferred — not implemented; no export endpoint exists yet |
| `GET` | `/api/research/jobs/{id}/validation-report` | Validation/dedupe summary |
| `GET` | `/api/providers/health` | Provider statuses (Settings page). `ai`: `not_configured` (NullAIProvider default) or `configured` (LLM key set; no probe call is made) |
| `GET` | `/api/health` | Liveness probe |
| `POST` | `/api/demo/seed` | Load synthetic dataset |
| `POST` | `/api/demo/reset` | Wipe demo data |

See `DESIGN.md` §4 for the request/response contract.

## AI enrichment (optional)

`POST /api/research/jobs` accepts `enable_ai: true`. The pipeline then runs an
ENRICH stage (`DISCOVER -> EXTRACT -> NORMALIZE -> VALIDATE -> DEDUPLICATE -> ENRICH -> SCORE -> STORE`).
Without `LEADFORGE_LLM_API_KEY` the disabled `NullAIProvider` is used and ENRICH is a
no-op — jobs complete normally with `ai_enriched: false`.

With a key set, an LLM provider may add `ai_fields` to results, each tagged
`{"value": ..., "ai_derived": true}`. AI never modifies normalized records, scores,
validation, or dedupe, and an AI failure never fails the job. AI-derived fields are
suggestions only — never verified facts.
