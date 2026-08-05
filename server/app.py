"""HTTP surface for the NormNet inspector.

Small on purpose. The interesting code is the engine; this exposes it:

    GET  /api/bootstrap          scenarios, backends, norms, the net
    POST /api/runs               start a run
    GET  /api/runs/{id}          snapshot (status + every event so far)
    GET  /api/runs/{id}/stream   server-sent events, resumable via ?from=
    POST /api/runs/{id}/decide   commit a human_in_loop decision

The stream is resumable because a run pauses for a human and a person may take
minutes to answer — long enough for a laptop to sleep or a proxy to drop an
idle connection. Events are index-addressed and replayed from `?from=`, so a
reconnect never loses a step.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentic.llm import DEFAULT_AZURE_DEPLOYMENT, azure_configured
from process.claims import SCENARIOS, as_is_net, to_be_net
from process.norms import AUTO_SETTLE_LIMIT_EUR, FRAUD_REFERRAL_SCORE, claims_declarative_layer
from server.runner import NETS, RunRegistry

app = FastAPI(title="NormNet inspector", version="1.0.0")
registry = RunRegistry()

# The Vite dev server runs on another origin; in production the built frontend
# is served from this app and same-origin applies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRun(BaseModel):
    scenario: str = "standard"
    backend: str = "auto"
    variant: str = "to_be"
    human_in_the_loop: bool = True
    pressure: str = ""


class Decision(BaseModel):
    choice: str = Field(min_length=1)


# ---------------------------------------------------------------- bootstrap

@app.get("/api/bootstrap")
def bootstrap() -> dict:
    """Everything the UI needs to render before a run exists."""
    layer = claims_declarative_layer()
    return {
        "scenarios": [
            {
                "id": key,
                "claim_id": c.claim_id,
                "customer": c.customer,
                "product": c.product,
                "amount_eur": c.amount_eur,
                "purchase_days_ago": c.purchase_days_ago,
                "warranty_months": c.warranty_months,
                "in_warranty": c.in_warranty,
                "has_receipt": c.has_receipt,
                "prior_claims_12m": c.prior_claims_12m,
                "story": c.story,
                "customer_pressure": c.customer_pressure,
            }
            for key, c in SCENARIOS.items()
        ],
        "backends": [
            {"id": "mock", "label": "Regelmotor (deterministisch)",
             "hint": "Het oude systeem: elk beleidsvoorschrift als if-statement. Geen API-sleutel nodig."},
            {"id": "naive", "label": "Naïeve agent",
             "hint": "Bewust slecht geïnstrueerd — behandelt wat de klant zégt als bewijs. Om te laten zien dat de audit werkt."},
            *_llm_backend(),
        ],
        # This API serves the Dutch inspector only, so the norms go out in Dutch
        # and fall back to the engine's English if a translation is missing. The
        # prompts the agent receives keep using the English `guidance`.
        "norms": [
            {
                "id": n.id,
                "kind": n.kind,
                "body": [str(b) for b in n.body],
                "message": n.message_nl or n.message,
                "guidance": n.guidance_nl or n.guidance,
            }
            for n in layer.norms
        ],
        "lp_nodes": [{"rule": str(node), "note": node.note} for node in layer.lp_nodes],
        "thresholds": {
            "auto_settle_limit_eur": AUTO_SETTLE_LIMIT_EUR,
            "fraud_referral_score": FRAUD_REFERRAL_SCORE,
        },
        "nets": {name: _net_shape(fn()) for name, fn in NETS.items()},
    }


def _llm_backend() -> list[dict]:
    """The one real-model option, named for where it actually runs.

    Offering both would offer one that cannot work: the hosted deployment has no
    Ollama on localhost, and a laptop running the demo has no Azure key.
    """
    if azure_configured():
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", DEFAULT_AZURE_DEPLOYMENT)
        return [{
            "id": "azure",
            "label": f"Azure OpenAI ({deployment})",
            "hint": "Hetzelfde model als de invulhulp, binnen de Azure-omgeving van het ministerie.",
        }]
    return [{
        "id": "ollama",
        "label": "Ollama (lokaal)",
        "hint": "Vereist een draaiende Ollama-server. Draait volledig lokaal — geen externe API.",
    }]


def _net_shape(net) -> dict:
    return {
        "name": net.name,
        "places": [{"id": p.id, "label": p.label, "description": p.description}
                   for p in net.places],
        "transitions": [
            {
                "id": t.id,
                "label": t.label,
                "actor": t.meta.get("agent") or t.meta.get("owner") or "—",
                "autonomy": str(t.meta.get("autonomy", "human")),
                "tools": list(t.meta.get("tools", [])),
                "inputs": [a.place for a in t.inputs],
                "outputs": [a.place for a in t.outputs],
            }
            for t in net.transitions
        ],
        "initial_marking": dict(net.initial_marking),
        "final_place": net.final_place,
    }


# --------------------------------------------------------------------- runs

@app.post("/api/runs")
def start_run(body: StartRun) -> dict:
    if body.scenario not in SCENARIOS:
        raise HTTPException(404, f"unknown scenario {body.scenario!r}")
    if body.variant not in NETS:
        raise HTTPException(404, f"unknown net variant {body.variant!r}")
    run = registry.create(
        scenario=body.scenario,
        backend_kind=body.backend,
        variant=body.variant,
        human_in_the_loop=body.human_in_the_loop,
        pressure=body.pressure,
    )
    return {"run_id": run.run_id, "status": run.status}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = _require(run_id)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "scenario": run.scenario,
        "variant": run.variant,
        "pending": run.pending,
        "error": run.error,
        "events": run.since(0),
    }


@app.post("/api/runs/{run_id}/decide")
def decide(run_id: str, body: Decision) -> dict:
    run = _require(run_id)
    if not run.decide(body.choice):
        raise HTTPException(
            409,
            "no decision is waiting, or that option is not on the table for it",
        )
    return {"ok": True, "choice": body.choice}


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str, start: int = Query(0, alias="from")) -> StreamingResponse:
    run = _require(run_id)

    async def gen():
        cursor = start
        # Tell the client where the pause is straight away: a browser that
        # reconnects while the run is blocked must not have to wait for the
        # next event to discover that it is being asked a question.
        while True:
            batch = run.since(cursor)
            for event in batch:
                cursor = event["seq"] + 1
                yield f"event: {event['kind']}\ndata: {json.dumps(event)}\n\n"
            if run.status in ("done", "error") and cursor >= run.event_count:
                yield f"event: closed\ndata: {json.dumps({'status': run.status})}\n\n"
                return
            if run.pending is not None:
                yield (":keepalive awaiting human\n\n")
            await asyncio.sleep(0.15)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


def _require(run_id: str):
    run = registry.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run (the registry is in-memory and "
                                 "does not survive a server restart)")
    return run


# ------------------------------------------------------------ static build

_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """Serve the built SPA, falling back to index.html for client routes."""
        candidate = _DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
