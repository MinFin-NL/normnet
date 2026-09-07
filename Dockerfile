# One image, one process. Unlike a split frontend/backend deployment, the API
# already serves the built SPA (see the static mount at the bottom of
# server/app.py), so an nginx container in front of it would only add a hop.

# ── stage 1: the Vue bundle ──────────────────────────────────────────────────
FROM node:22-alpine AS web

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── stage 2: the API, serving that bundle ────────────────────────────────────
FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, so a code change doesn't re-resolve the environment.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# The engine and everything on top of it. Copied as whole packages: the module
# lists here change with the code, and a hand-maintained file list would only
# be discovered wrong at import time, inside a crash-looping container.
COPY petrinet/ ./petrinet/
COPY process/ ./process/
COPY agentic/ ./agentic/
COPY audit/ ./audit/
COPY server/ ./server/

# app.py looks for frontend/dist next to the package root.
COPY --from=web /app/frontend/dist ./frontend/dist

EXPOSE 8000

# --no-sync is load-bearing. Plain `uv run` re-syncs the environment before it
# executes, which pulls the dev group back in -- the pytest tree that
# `uv sync --no-dev` above deliberately left out -- and then tries to fetch it
# from PyPI at container start. There is no route to PyPI from
# cae-platform-inno-d: outbound is filtered to Microsoft endpoints, so the
# download fails with "tls handshake eof", uv gives up, and the process exits 1
# before uvicorn ever binds. --no-sync pins the container to the environment
# the image was built with and takes the network out of startup entirely.
CMD ["uv", "run", "--no-sync", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
