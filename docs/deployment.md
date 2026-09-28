# Deployment

LeadForge is deployment-ready with a simple architecture: static frontend + one API
service + managed PostgreSQL. No paid tier is required to evaluate the options below.

## Option A — simplest (recommended for portfolio)

| Layer | Service | Notes |
|---|---|---|
| Frontend | Vercel | `frontend/` as a Vite project; set `VITE_API_URL` to the backend URL |
| Backend | Render / Railway / Fly.io | `backend/` Dockerfile; set `DATABASE_URL` |
| Database | Provider-managed PostgreSQL | e.g. Render Postgres, Railway Postgres, Neon, Supabase |

Steps (generic):

1. Create a managed PostgreSQL database; copy its connection string.
2. Deploy `backend/` from its Dockerfile; set `DATABASE_URL` (and optionally
   `LEADFORGE_LLM_API_KEY`).
3. Deploy `frontend/` as a static site; set `VITE_API_URL=https://<backend-host>`.
4. Verify: `GET https://<backend-host>/api/health` → `{"status":"ok"}`.

## Option B — single host via Docker Compose

Any VM with Docker:

```bash
cp .env.example .env   # set POSTGRES_* (or accept defaults for a demo)
docker compose up --build
```

This starts `db` (PostgreSQL), `backend`, `worker`, and `frontend`.

## Notes

- The backend serves the API only; the frontend is static files (nginx in Docker,
  Vercel/Netlify-style hosting elsewhere).
- SQLite is for local development; use PostgreSQL in any deployed environment.
- Never commit `.env` — all secrets come from environment variables.
