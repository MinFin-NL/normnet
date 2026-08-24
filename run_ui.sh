#!/usr/bin/env bash
# Serve the NormNet inspector: build the frontend if needed, then hand the
# static bundle to the API on :8000. No Node process stays up.
#
# For hot reload use `npm run dev` from the project root — that starts both the
# API and Vite. This script is the no-Node-process alternative.
#
# The frontend is only rebuilt when it has to be; run_demo.py needs none of this.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d frontend/dist ]]; then
  echo "→ building the frontend (first run)…"
  ( cd frontend && npm install --silent && npm run build )
fi
echo "→ http://127.0.0.1:8000"
exec uv run uvicorn server.app:app --port 8000
