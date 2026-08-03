#!/usr/bin/env bash
# Start the NormNet inspector.
#
#   ./run_ui.sh          serve the built frontend from the API on :8000
#   ./run_ui.sh --dev    API on :8000 + Vite dev server on :5173 (hot reload)
#
# The frontend is only rebuilt when it has to be; run_demo.py needs none of this.
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--dev" ]]; then
  echo "→ API      http://127.0.0.1:8000"
  echo "→ frontend http://127.0.0.1:5173  (proxies /api to the API)"
  ( cd frontend && npm install --silent && npm run dev ) &
  exec uvicorn server.app:app --reload --port 8000
fi

if [[ ! -d frontend/dist ]]; then
  echo "→ building the frontend (first run)…"
  ( cd frontend && npm install --silent && npm run build )
fi
echo "→ http://127.0.0.1:8000"
exec uvicorn server.app:app --port 8000
