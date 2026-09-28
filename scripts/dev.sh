#!/usr/bin/env bash
# LeadForge local dev launcher — SQLite, zero setup.
# Backend on :8000, frontend on :5173. Implemented in Phase 3+.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "LeadForge dev launcher (Phase 2 skeleton — services start in Phase 3+)."
echo "Backend would run : uvicorn leadforge.main:app --reload --port ${BACKEND_PORT}  (in backend/)"
echo "Frontend would run: npm run dev -- --port ${FRONTEND_PORT}                  (in frontend/)"
echo "Root: ${ROOT}"
