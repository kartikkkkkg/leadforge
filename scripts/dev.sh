#!/usr/bin/env bash
# LeadForge local dev launcher — SQLite, zero setup.
# Starts the FastAPI backend on :8000 and the Vite frontend on :5173.
# Requires: backend/.venv (or backend deps on PATH) and frontend/node_modules.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "${PYTHON_BIN}" ]; then
  if [ -x "${ROOT}/.venv/bin/python" ]; then
    PYTHON_BIN="${ROOT}/.venv/bin/python"
  elif [ -x "${ROOT}/backend/.venv/bin/python" ]; then
    PYTHON_BIN="${ROOT}/backend/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

cleanup() {
  echo "Stopping LeadForge dev servers..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on :${BACKEND_PORT} ..."
cd "${ROOT}/backend"
"${PYTHON_BIN}" -m leadforge serve --port "${BACKEND_PORT}" &
BACKEND_PID=$!

echo "Starting frontend on :${FRONTEND_PORT} ..."
cd "${ROOT}/frontend"
if [ ! -d node_modules ]; then
  echo "frontend/node_modules missing — run 'npm install' in frontend/ first." >&2
  exit 1
fi
npx vite --port "${FRONTEND_PORT}" --strictPort &
FRONTEND_PID=$!

echo ""
echo "LeadForge is running:"
echo "  UI:       http://localhost:${FRONTEND_PORT}"
echo "  API:      http://localhost:${BACKEND_PORT}"
echo "  API docs: http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

wait
