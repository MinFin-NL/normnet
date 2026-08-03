"""Run a process in the background and publish what it is doing.

The engine is synchronous and LangGraph drives it to completion in one call, so
a run lives on its own worker thread. Two things flow across that boundary:

* **events out** — every step, decision, prompt and violation, appended to a
  list the HTTP layer replays from. Append-only and index-addressed, so a
  browser that reconnects mid-run resumes exactly where it left off instead of
  silently missing the steps it was disconnected for.
* **a decision in** — when the process reaches a transition the net marks
  ``human_in_loop``, the worker thread *blocks* on an Event until someone
  commits. That is the point: the pause is real. The process is not simulating
  a wait, it genuinely cannot proceed.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from agentic.compile import CompiledProcess
from agentic.llm import get_backend
from process.claims import SCENARIOS, Claim, as_is_net, to_be_net

#: How long a run waits at a human gate before giving up and letting the
#: agent's recommendation stand. Long enough for someone to read the case;
#: short enough that an abandoned browser tab doesn't pin a thread forever.
HUMAN_GATE_TIMEOUT_S = 60 * 60

NETS = {"to_be": to_be_net, "as_is": as_is_net}


@dataclass
class RunSession:
    run_id: str
    scenario: str
    backend_kind: str
    variant: str
    human_in_the_loop: bool
    pressure: str = ""

    events: list[dict] = field(default_factory=list)
    status: str = "starting"        # starting | running | awaiting_human | done | error
    pending: dict | None = None     # the decision currently blocking, if any
    error: str | None = None

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _decided: threading.Event = field(default_factory=threading.Event, repr=False)
    _choice: str | None = field(default=None, repr=False)

    # -- event stream --------------------------------------------------------

    def _emit(self, kind: str, payload: dict) -> None:
        # The payload is nested, not spread. Spreading lets a payload key shadow
        # an envelope key — a `violation` event carries the norm's own `kind`
        # ("prohibition"), which silently overwrote the envelope's `kind` and
        # made violations invisible to every consumer. Nesting makes the two
        # namespaces incapable of colliding.
        with self._lock:
            self.events.append({"seq": len(self.events), "kind": kind, "data": payload})

    def since(self, seq: int) -> list[dict]:
        with self._lock:
            return self.events[seq:]

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self.events)

    # -- the human gate ------------------------------------------------------

    def _gate(self, info: dict) -> str:
        """Block the worker thread until a person decides (or we time out)."""
        with self._lock:
            self.pending = info
            self.status = "awaiting_human"
        self._decided.clear()

        if not self._decided.wait(timeout=HUMAN_GATE_TIMEOUT_S):
            self._emit("human_timeout", {
                "round": info.get("round"),
                "decision_id": info.get("decision_id"),
                "message": (
                    "No decision within the timeout — the agent's recommendation "
                    "was allowed to stand. This run is no longer human-in-the-loop."
                ),
            })
            with self._lock:
                self.pending, self.status = None, "running"
            return info["recommendation"]

        with self._lock:
            chosen = self._choice or info["recommendation"]
            self.pending, self.status = None, "running"
        return chosen

    def decide(self, choice: str) -> bool:
        """Called from the HTTP layer. Returns False if nothing is waiting."""
        with self._lock:
            if self.pending is None:
                return False
            allowed = self.pending.get("options", [])
        if choice not in allowed:
            return False
        self._choice = choice
        self._decided.set()
        return True

    # -- the run -------------------------------------------------------------

    def start(self) -> None:
        threading.Thread(target=self._run, name=f"run-{self.run_id}",
                         daemon=True).start()

    def _run(self) -> None:
        try:
            base = SCENARIOS[self.scenario]
            claim = Claim(**{**base.__dict__, "customer_pressure":
                             self.pressure or base.customer_pressure})
            process = CompiledProcess(
                NETS[self.variant](),
                get_backend(self.backend_kind),
                verbose=False,
                emit=self._emit,
                human_gate=self._gate if self.human_in_the_loop else None,
            )
            with self._lock:
                self.status = "running"
            process.run(claim)
            with self._lock:
                self.status = "done"
        except Exception as exc:  # noqa: BLE001 — surface it to the UI, don't die silently
            self.error = f"{exc.__class__.__name__}: {exc}"
            self._emit("run_error", {"message": self.error})
            with self._lock:
                self.status = "error"


class RunRegistry:
    """In-memory store of runs. Deliberately not persistent — this is a demo
    and a restart should start clean."""

    def __init__(self, limit: int = 50) -> None:
        self._runs: dict[str, RunSession] = {}
        self._order: list[str] = []
        self._limit = limit
        self._lock = threading.Lock()

    def create(self, **kwargs: Any) -> RunSession:
        run = RunSession(run_id=uuid.uuid4().hex[:12], **kwargs)
        with self._lock:
            self._runs[run.run_id] = run
            self._order.append(run.run_id)
            while len(self._order) > self._limit:
                self._runs.pop(self._order.pop(0), None)
        run.start()
        return run

    def get(self, run_id: str) -> RunSession | None:
        return self._runs.get(run_id)
